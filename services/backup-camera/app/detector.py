"""YOLOv8-Objekterkennung (COCO-vortrainiert).

Lädt das Modell beim ersten Start (Download via ultralytics, gecacht im
Volume /app/models). Auf dem Jetson (CUDA) wird beim ersten Start zusätzlich
eine TensorRT-Engine gebaut und gecacht — das beschleunigt die Inferenz
deutlich (~5-10x). Bei Folgestarts wird die .engine direkt geladen.

Ablauf:
  1. .pt-Datei sicher ins Volume cachen (Download falls nötig).
  2. Auf CUDA + export_engine=true: .engine bauen (falls noch nicht vorhanden).
  3. .engine laden wenn vorhanden, sonst .pt.
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import Any

import cv2

from .config import DetectorConfig

log = logging.getLogger(__name__)

# COCO-Klassennamen (80 Klassen, ultralytics-Default).
COCO_NAMES: list[str] = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag",
    "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball", "kite",
    "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon",
    "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot",
    "hot dog", "pizza", "donut", "cake", "chair", "couch", "potted plant",
    "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote",
    "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]

# BGR-Farben für häufige Verkehrsklassen (rot hervorheben).
CLASS_COLORS: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 255),    # person -> rot
    1: (0, 255, 255),  # bicycle -> gelb
    2: (0, 255, 0),    # car -> grün
    3: (0, 165, 255),  # motorcycle -> orange
    5: (255, 0, 0),    # bus -> blau
    7: (255, 255, 0),  # truck -> cyan
}
DEFAULT_COLOR = (200, 200, 200)


def _is_engine(path: str) -> bool:
    return path.lower().endswith((".engine", ".trt"))


class Detector:
    """Wrapper um ultralytics YOLO mit TensorRT-Caching."""

    def __init__(self, cfg: DetectorConfig, models_dir: str = "/app/models") -> None:
        self.cfg = cfg
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self._model: Any | None = None
        self._device: str = ""
        self._using_engine: bool = False

    # ---- Device -------------------------------------------------------------
    def _resolve_device(self) -> str:
        if self.cfg.device and self.cfg.device.lower() != "auto":
            return self.cfg.device
        try:
            import torch
            return "cuda:0" if torch.cuda.is_available() else "cpu"
        except Exception:  # noqa: BLE001
            return "cpu"

    @property
    def _is_cuda(self) -> bool:
        return self._device.startswith("cuda")

    # ---- Pfad-Helfer --------------------------------------------------------
    def _pt_path(self) -> str:
        """Pfad zur .pt-Datei im Volume."""
        name = self.cfg.model
        if not name.endswith(".pt"):
            name = name + ".pt"
        return os.path.join(self.models_dir, name)

    def _engine_path(self) -> str:
        """Pfad zur TensorRT-Engine im Volume (abgeleitet aus dem Modellnamen)."""
        base = os.path.splitext(os.path.basename(self.cfg.model))[0]
        suffix = f"_fp16" if self.cfg.half else "_fp32"
        return os.path.join(self.models_dir, f"{base}{suffix}.engine")

    # ---- .pt cachen ---------------------------------------------------------
    def _ensure_pt_cached(self) -> str:
        """Stellt sicher, dass die .pt-Datei im Volume liegt. Gibt den Pfad zurück.

        Falls die Datei im Volume fehlt, wird sie via ultralytics heruntergeladen
        und dann aus dem ultralytics-Cache ins Volume kopiert.
        """
        pt_path = self._pt_path()
        if os.path.exists(pt_path):
            log.info("YOLO .pt aus Cache: %s", pt_path)
            return pt_path

        # ultralytics herunterladen lassen. Ultralytics legt die Datei im CWD
        # oder im ultralytics-Settings-Dir ab. Wir rufen YOLO mit dem nackten
        # Namen auf und suchen dann die Datei.
        from ultralytics import YOLO

        log.info("Lade YOLO .pt (Download falls noetig): %s", self.cfg.model)
        # Ins models_dir wechseln, damit der Download dort landet.
        cwd = os.getcwd()
        try:
            os.chdir(self.models_dir)
            model = YOLO(self.cfg.model)
        finally:
            os.chdir(cwd)

        # ultralytics speichert die Datei typischerweise im CWD (hier models_dir)
        # unter dem Originalnamen.
        downloaded = os.path.join(self.models_dir, os.path.basename(self.cfg.model))
        if not os.path.exists(downloaded):
            # Fallback: ultralytics-Default-Verzeichnis durchsuchen.
            for cand in (
                os.path.expanduser("~/.config/Ultralytics"),
                os.path.expanduser("~/.cache/ultralytics"),
            ):
                if os.path.isdir(cand):
                    for root, _dirs, files in os.walk(cand):
                        for f in files:
                            if f == os.path.basename(self.cfg.model):
                                downloaded = os.path.join(root, f)
                                break
        if os.path.exists(downloaded) and os.path.abspath(downloaded) != os.path.abspath(pt_path):
            shutil.copy(downloaded, pt_path)
            log.info("YOLO .pt nach %s kopiert.", pt_path)
        elif os.path.exists(pt_path):
            pass  # schon am Zielort
        else:
            log.warning(
                "Konnte .pt nicht im Volume cachen (%s). Nutze Download-Pfad %s.",
                pt_path, downloaded,
            )
            pt_path = downloaded
        return pt_path

    # ---- TensorRT-Export ----------------------------------------------------
    def _maybe_export_engine(self, pt_path: str) -> str | None:
        """Baut bei CUDA + export_engine eine TensorRT-Engine und cacht sie.

        Gibt den Engine-Pfad zurück falls erfolgreich, sonst None.
        """
        if not self.cfg.export_engine:
            log.info("TensorRT-Export deaktiviert (YOLO_EXPORT_ENGINE=false).")
            return None
        if not self._is_cuda:
            log.info("Kein CUDA -> TensorRT-Export übersprungen (CPU-Inferenz).")
            return None

        engine_path = self._engine_path()
        if os.path.exists(engine_path):
            log.info("TensorRT-Engine aus Cache: %s", engine_path)
            return engine_path

        from ultralytics import YOLO

        log.info(
            "Baue TensorRT-Engine (imgsz=%d, half=%s). Das dauert beim ersten "
            "Start einige Minuten - danach wird die .engine gecacht.",
            self.cfg.img_size, self.cfg.half,
        )
        try:
            pt_model = YOLO(pt_path)
            exported = pt_model.export(
                format="engine",
                imgsz=self.cfg.img_size,
                half=self.cfg.half,
                device=self._device,
                dynamic=False,  # statische Input-Shape = schneller auf Jetson
                simplify=True,
                workspace=4,    # GB Workspace für TensorRT
            )
            # ultralytics schreibt die .engine typischerweise neben die .pt.
            exported_path = str(exported) if exported else None
            if exported_path and os.path.exists(exported_path):
                if os.path.abspath(exported_path) != os.path.abspath(engine_path):
                    shutil.move(exported_path, engine_path)
                log.info("TensorRT-Engine gebaut und gecacht: %s", engine_path)
                return engine_path
            log.warning("TensorRT-Export lieferte keine Engine-Datei.")
            return None
        except Exception as e:  # noqa: BLE001
            log.warning(
                "TensorRT-Export fehlgeschlagen (%s). Fallback auf .pt-Inferenz.", e,
            )
            return None

    # ---- Load ---------------------------------------------------------------
    def load(self) -> None:
        from ultralytics import YOLO

        self._device = self._resolve_device()
        log.info("YOLO-Inferenz-Device: %s", self._device)

        # 1) .pt sicher im Volume cachen.
        pt_path = self._ensure_pt_cached()

        # 2) Auf CUDA: optional .engine bauen/cachen.
        engine_path = self._maybe_export_engine(pt_path)

        # 3) .engine bevorzugen, sonst .pt.
        if engine_path and os.path.exists(engine_path):
            log.info("Lade TensorRT-Engine: %s", engine_path)
            self._model = YOLO(engine_path)
            self._using_engine = True
        else:
            log.info("Lade PyTorch-Modell: %s", pt_path)
            self._model = YOLO(pt_path)
            self._using_engine = False

        log.info(
            "Modell bereit (engine=%s, device=%s).",
            self._using_engine, self._device,
        )

    # ---- Properties ---------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def using_engine(self) -> bool:
        return self._using_engine

    @property
    def device(self) -> str:
        return self._device

    # ---- Inferenz -----------------------------------------------------------
    def detect(self, frame):
        """Führt Inferenz aus und gibt das annotierte Frame + Metriken zurück."""
        if self._model is None:
            return frame, []

        classes = self.cfg.classes if self.cfg.classes else None
        # Bei TensorRT-Engine ist die Input-Size fix (img_size). ultralytics
        # skaliert automatisch; wir müssen imgsz nur beim Export setzen.
        predict_kwargs: dict[str, Any] = dict(
            conf=self.cfg.conf_threshold,
            classes=classes,
            device=self._device,
            verbose=False,
        )
        # Auf CUDA mit FP16-Engine: half=True beschleunigt weiter.
        if self._is_cuda and self._using_engine and self.cfg.half:
            predict_kwargs["half"] = True

        results = self._model.predict(frame, **predict_kwargs)
        detections = []
        for r in results:
            boxes = r.boxes
            for b in boxes:
                cls_id = int(b.cls.item())
                conf = float(b.conf.item())
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
                detections.append(
                    {
                        "class_id": cls_id,
                        "label": COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id),
                        "conf": conf,
                        "box": (x1, y1, x2, y2),
                    }
                )
                self._draw_box(frame, x1, y1, x2, y2, cls_id, conf)
        return frame, detections

    @staticmethod
    def _draw_box(frame, x1, y1, x2, y2, cls_id, conf) -> None:
        color = CLASS_COLORS.get(cls_id, DEFAULT_COLOR)
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        label = f"{COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else cls_id} {conf:.2f}"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(frame, (x1, max(0, y1 - th - 4)), (x1 + tw + 4, y1), color, -1)
        cv2.putText(
            frame, label, (x1 + 2, max(th, y1 - 2)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA,
        )
