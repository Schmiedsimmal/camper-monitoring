"""Zentrale Config-Auslesung aus Umgebungsvariablen.

Alle Werte kommen über das Root-.env-File (docker compose env_file) herein.
Keine hartkodierten Defaults in den Modulen — alles geht über diese Klasse.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_list(name: str, default: str) -> list[int]:
    raw = _env(name, default)
    if not raw.strip():
        return []
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def _env_float_list(name: str, default: str) -> list[float]:
    raw = _env(name, default)
    if not raw.strip():
        return []
    out = []
    for x in raw.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(float(x))
        except ValueError:
            continue
    return out


@dataclass
class CameraConfig:
    source: str = field(default_factory=lambda: _env("CAMERA_SOURCE", "usb:0"))
    width: int = field(default_factory=lambda: _env_int("CAMERA_WIDTH", 1280))
    height: int = field(default_factory=lambda: _env_int("CAMERA_HEIGHT", 720))
    fps: int = field(default_factory=lambda: _env_int("CAMERA_FPS", 15))


@dataclass
class DetectorConfig:
    model: str = field(default_factory=lambda: _env("YOLO_MODEL", "yolov8n.pt"))
    conf_threshold: float = field(
        default_factory=lambda: _env_float("YOLO_CONF_THRESHOLD", 0.4)
    )
    classes: list[int] = field(
        default_factory=lambda: _env_list("YOLO_CLASSES", "0,1,2,3,5,7")
    )
    # Device: "auto" erkennt CUDA, sonst "cpu". Explizit z.B. "cuda:0".
    device: str = field(default_factory=lambda: _env("YOLO_DEVICE", "auto"))
    # TensorRT-Engine beim ersten Start auf CUDA bauen und cachen.
    # Beschleunigt die Inferenz auf dem Jetson deutlich (~5-10x).
    # Auf CPU-Hosts automatisch deaktiviert.
    export_engine: bool = field(
        default_factory=lambda: _env("YOLO_EXPORT_ENGINE", "true").lower() == "true"
    )
    # Input-Größe für den TensorRT-Export (fix, quadratisch).
    # 640 ist der YOLO-Default; 416/320 sind schneller aber ungenauer.
    img_size: int = field(default_factory=lambda: _env_int("YOLO_IMG_SIZE", 640))
    # TensorRT-Half-Precision (FP16). Auf dem Jetson Nano unterstützt.
    half: bool = field(
        default_factory=lambda: _env("YOLO_HALF", "true").lower() == "true"
    )


@dataclass
class TriggerConfig:
    gpio_pin: int = field(default_factory=lambda: _env_int("TRIGGER_GPIO_PIN", 24))
    gated: bool = field(default_factory=lambda: _env("TRIGGER_GATED", "true").lower() == "true")
    # active_low=true: GPIO liegt bei aktivem Trigger auf GND (PC817-Schaltung).
    active_low: bool = field(
        default_factory=lambda: _env("TRIGGER_ACTIVE_LOW", "true").lower() == "true"
    )


@dataclass
class OverlayConfig:
    # Overlay (Abstandslinien + Fahrzeug-Kontur) ein-/ausschalten.
    enabled: bool = field(
        default_factory=lambda: _env("OVERLAY_ENABLED", "true").lower() == "true"
    )
    # Kamera-Montagehöhe über dem Boden [m]. Typisch Camper-Heck: 1.0-1.5m.
    camera_height: float = field(
        default_factory=lambda: _env_float("OVERLAY_CAMERA_HEIGHT", 1.2)
    )
    # Neigungswinkel der Kamera nach unten [Grad]. 0 = waagerecht, 90 = senkrecht nach unten.
    # Typisch Rückfahrkamera: 5-15°.
    camera_tilt: float = field(
        default_factory=lambda: _env_float("OVERLAY_CAMERA_TILT", 10.0)
    )
    # Horizontaler Sichtwinkel (FOV) der Kamera [Grad].
    # IMX291 mit 3.6mm M12: ~87° H. Mit 2.8mm: ~110°. Fisheye: 130-150°.
    # Breiterer FOV = mehr Boden sichtbar = Linien weiter reichend.
    camera_hfov: float = field(
        default_factory=lambda: _env_float("OVERLAY_CAMERA_HFOV", 130.0)
    )
    # Fahrzeugbreite [m] — für die projizierte Fahrzeug-Kontur.
    # Iveco Daily IV 35S12: 1996 mm -> 2.0 m.
    vehicle_width: float = field(
        default_factory=lambda: _env_float("OVERLAY_VEHICLE_WIDTH", 2.0)
    )
    # Abstände der horizontalen Linien hinter dem Fahrzeug [m], komma-separiert.
    # Bei 1.2m Höhe + 10° Neigung + 130° FOV sind 1/2/3/5m gut sichtbar.
    distance_lines: list[float] = field(
        default_factory=lambda: _env_float_list("OVERLAY_DISTANCE_LINES", "1,2,3,5")
    )
    # Linien-Farben (BGR). Reihenfolge: grün/gelb/rot für die Zonen.
    # Standard: grün = sicher, gelb = Vorsicht, rot = STOP.
    color_green: tuple[int, int, int] = (0, 200, 0)
    color_yellow: tuple[int, int, int] = (0, 220, 220)
    color_red: tuple[int, int, int] = (0, 0, 220)
    color_line: tuple[int, int, int] = (255, 255, 255)
    color_text: tuple[int, int, int] = (255, 255, 255)
    # Zonen-Grenzen [m] für Farb-Coding der Linien.
    zone_green_max: float = 2.0   # < zone_green_max -> grün
    zone_yellow_max: float = 0.5  # < zone_yellow_max -> gelb, darunter rot


@dataclass
class WebConfig:
    port: int = field(default_factory=lambda: _env_int("BACKUP_CAMERA_PORT", 8080))


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config() -> Config:
    return Config()
