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
class WebConfig:
    port: int = field(default_factory=lambda: _env_int("BACKUP_CAMERA_PORT", 8080))


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config() -> Config:
    return Config()
