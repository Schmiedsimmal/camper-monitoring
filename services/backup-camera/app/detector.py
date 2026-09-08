"""YOLOv8 object detection (COCO pretrained).

Loads the model on first start (download via ultralytics, cached in the
``/app/models`` volume). On the Jetson (CUDA) a TensorRT engine is built
and cached on first start — this speeds up inference significantly
(~5-10x). On subsequent starts the ``.engine`` is loaded directly.

Flow:
  1. Cache the ``.pt`` file in the volume (download if needed).
  2. On CUDA + ``export_engine=true``: build ``.engine`` (if not cached).
  3. Load ``.engine`` if available, otherwise fall back to ``.pt``.
"""
from __future__ import annotations

import logging
import os
import shutil
from typing import Any

import cv2

from .config import DetectorConfig

log = logging.getLogger(__name__)

# COCO class names (80 classes, ultralytics default).
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

# BGR colors for common traffic classes (highlight person in red).
CLASS_COLORS: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 255),    # person -> red
    1: (0, 255, 255),  # bicycle -> yellow
    2: (0, 255, 0),    # car -> green
    3: (0, 165, 255),  # motorcycle -> orange
    5: (255, 0, 0),    # bus -> blue
    7: (255, 255, 0),  # truck -> cyan
}
DEFAULT_COLOR = (200, 200, 200)


class Detector:
    """Wrapper around ultralytics YOLO with TensorRT caching."""

    def __init__(self, cfg: DetectorConfig, models_dir: str = "/app/models") -> None:
        self.cfg = cfg
        self.models_dir = models_dir
        os.makedirs(models_dir, exist_ok=True)
        self._model: Any | None = None
        self._device: str = ""
        self._using_engine: bool = False

    # -- device ---------------------------------------------------------------
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

    # -- path helpers ---------------------------------------------------------
    def _pt_path(self) -> str:
        name = self.cfg.model if self.cfg.model.endswith(".pt") else self.cfg.model + ".pt"
        return os.path.join(self.models_dir, name)

    def _engine_path(self) -> str:
        base = os.path.splitext(os.path.basename(self.cfg.model))[0]
        suffix = "_fp16" if self.cfg.half else "_fp32"
        return os.path.join(self.models_dir, f"{base}{suffix}.engine")

    # -- .pt caching ----------------------------------------------------------
    def _ensure_pt_cached(self) -> str:
        """Ensure the ``.pt`` file exists in the volume; return its path."""
        pt_path = self._pt_path()
        if os.path.exists(pt_path):
            log.info("YOLO .pt from cache: %s", pt_path)
            return pt_path

        from ultralytics import YOLO

        log.info("Downloading YOLO .pt (if needed): %s", self.cfg.model)
        cwd = os.getcwd()
        try:
            os.chdir(self.models_dir)
            YOLO(self.cfg.model)
        finally:
            os.chdir(cwd)

        downloaded = os.path.join(self.models_dir, os.path.basename(self.cfg.model))
        if not os.path.exists(downloaded):
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
            log.info("YOLO .pt copied to %s", pt_path)
        elif not os.path.exists(pt_path):
            log.warning("Could not cache .pt in volume (%s). Using %s.", pt_path, downloaded)
            pt_path = downloaded
        return pt_path

    # -- TensorRT export ------------------------------------------------------
    def _maybe_export_engine(self, pt_path: str) -> str | None:
        """Build a TensorRT engine on CUDA + ``export_engine=true``; cache it."""
        if not self.cfg.export_engine:
            log.info("TensorRT export disabled (YOLO_EXPORT_ENGINE=false).")
            return None
        if not self._is_cuda:
            log.info("No CUDA -> skipping TensorRT export (CPU inference).")
            return None

        engine_path = self._engine_path()
        if os.path.exists(engine_path):
            log.info("TensorRT engine from cache: %s", engine_path)
            return engine_path

        from ultralytics import YOLO

        log.info(
            "Building TensorRT engine (imgsz=%d, half=%s). This takes a few "
            "minutes on first start — the .engine is cached afterwards.",
            self.cfg.img_size, self.cfg.half,
        )
        try:
            pt_model = YOLO(pt_path)
            exported = pt_model.export(
                format="engine",
                imgsz=self.cfg.img_size,
                half=self.cfg.half,
                device=self._device,
                dynamic=False,
                simplify=True,
                workspace=4,
            )
            exported_path = str(exported) if exported else None
            if exported_path and os.path.exists(exported_path):
                if os.path.abspath(exported_path) != os.path.abspath(engine_path):
                    shutil.move(exported_path, engine_path)
                log.info("TensorRT engine built and cached: %s", engine_path)
                return engine_path
            log.warning("TensorRT export produced no engine file.")
            return None
        except Exception as exc:  # noqa: BLE001
            log.warning("TensorRT export failed (%s). Falling back to .pt inference.", exc)
            return None

    # -- load -----------------------------------------------------------------
    def load(self) -> None:
        from ultralytics import YOLO

        self._device = self._resolve_device()
        log.info("YOLO inference device: %s", self._device)

        pt_path = self._ensure_pt_cached()
        engine_path = self._maybe_export_engine(pt_path)

        if engine_path and os.path.exists(engine_path):
            log.info("Loading TensorRT engine: %s", engine_path)
            self._model = YOLO(engine_path)
            self._using_engine = True
        else:
            log.info("Loading PyTorch model: %s", pt_path)
            self._model = YOLO(pt_path)
            self._using_engine = False

        log.info("Model ready (engine=%s, device=%s).", self._using_engine, self._device)

    # -- properties -----------------------------------------------------------
    @property
    def loaded(self) -> bool:
        return self._model is not None

    @property
    def using_engine(self) -> bool:
        return self._using_engine

    @property
    def device(self) -> str:
        return self._device

    # -- inference ------------------------------------------------------------
    def detect(self, frame):
        """Run inference and return the annotated frame + detection list."""
        if self._model is None:
            return frame, []

        classes = self.cfg.classes or None
        predict_kwargs: dict[str, Any] = dict(
            conf=self.cfg.conf_threshold,
            classes=classes,
            device=self._device,
            verbose=False,
        )
        if self._is_cuda and self._using_engine and self.cfg.half:
            predict_kwargs["half"] = True

        results = self._model.predict(frame, **predict_kwargs)
        detections = []
        for r in results:
            for b in r.boxes:
                cls_id = int(b.cls.item())
                conf = float(b.conf.item())
                x1, y1, x2, y2 = (int(v) for v in b.xyxy[0].tolist())
                label = COCO_NAMES[cls_id] if cls_id < len(COCO_NAMES) else str(cls_id)
                detections.append({
                    "class_id": cls_id,
                    "label": label,
                    "conf": conf,
                    "box": (x1, y1, x2, y2),
                })
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
