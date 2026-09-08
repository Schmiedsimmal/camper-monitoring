"""Configuration for the backup-camera service.

All values come from environment variables (root ``.env`` file via
docker compose ``env_file``). No hardcoded defaults in modules —
everything goes through this config.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from shared.env import env_bool, env_float, env_float_list, env_int, env_int_list, env_str


@dataclass
class CameraConfig:
    source: str = field(default_factory=lambda: env_str("CAMERA_SOURCE", "usb:0"))
    width: int = field(default_factory=lambda: env_int("CAMERA_WIDTH", 1280))
    height: int = field(default_factory=lambda: env_int("CAMERA_HEIGHT", 720))
    fps: int = field(default_factory=lambda: env_int("CAMERA_FPS", 15))


@dataclass
class DetectorConfig:
    model: str = field(default_factory=lambda: env_str("YOLO_MODEL", "yolov8n.pt"))
    conf_threshold: float = field(
        default_factory=lambda: env_float("YOLO_CONF_THRESHOLD", 0.4)
    )
    classes: list[int] = field(
        default_factory=lambda: env_int_list("YOLO_CLASSES", "0,1,2,3,5,7")
    )
    # Device: "auto" detects CUDA, otherwise "cpu". Explicit e.g. "cuda:0".
    device: str = field(default_factory=lambda: env_str("YOLO_DEVICE", "auto"))
    # Build a TensorRT engine on first CUDA start and cache it.
    # Speeds up inference on the Jetson significantly (~5-10x).
    # Automatically disabled on CPU-only hosts.
    export_engine: bool = field(
        default_factory=lambda: env_bool("YOLO_EXPORT_ENGINE", True)
    )
    # Input size for TensorRT export (fixed, square).
    # 640 is the YOLO default; 416/320 are faster but less accurate.
    img_size: int = field(default_factory=lambda: env_int("YOLO_IMG_SIZE", 640))
    # TensorRT half precision (FP16). Supported on Jetson Nano.
    half: bool = field(default_factory=lambda: env_bool("YOLO_HALF", True))


@dataclass
class TriggerConfig:
    gpio_pin: int = field(default_factory=lambda: env_int("TRIGGER_GPIO_PIN", 24))
    gated: bool = field(default_factory=lambda: env_bool("TRIGGER_GATED", True))
    # active_low=True: GPIO is pulled to GND when the 12V signal is active
    # (PC817 optocoupler circuit).
    active_low: bool = field(
        default_factory=lambda: env_bool("TRIGGER_ACTIVE_LOW", True)
    )


@dataclass
class OverlayConfig:
    """Rear-view overlay: distance lines + vehicle contour."""

    enabled: bool = field(default_factory=lambda: env_bool("OVERLAY_ENABLED", True))
    # Camera mount height above ground [m]. Typical camper rear: 1.0-1.5m.
    camera_height: float = field(
        default_factory=lambda: env_float("OVERLAY_CAMERA_HEIGHT", 1.2)
    )
    # Camera tilt angle downward [degrees]. 0 = horizontal, 90 = straight down.
    # Typical rear-view camera: 5-15 degrees.
    camera_tilt: float = field(
        default_factory=lambda: env_float("OVERLAY_CAMERA_TILT", 10.0)
    )
    # Horizontal field of view [degrees].
    # IMX291 with 3.6mm M12: ~87deg. With 2.8mm: ~110deg. Fisheye: 130-150deg.
    camera_hfov: float = field(
        default_factory=lambda: env_float("OVERLAY_CAMERA_HFOV", 130.0)
    )
    # Vehicle width [m] for the projected vehicle contour.
    # Iveco Daily IV 35S12: 1996mm -> 2.0m.
    vehicle_width: float = field(
        default_factory=lambda: env_float("OVERLAY_VEHICLE_WIDTH", 2.0)
    )
    # Distances of horizontal lines behind the vehicle [m], comma-separated.
    distance_lines: list[float] = field(
        default_factory=lambda: env_float_list("OVERLAY_DISTANCE_LINES", "1,2,3,5")
    )
    # Zone boundaries [m] for color coding.
    zone_green_max: float = 2.0   # <= zone_green_max -> green
    zone_yellow_max: float = 0.5  # <= zone_yellow_max -> yellow, below -> red


@dataclass
class WebConfig:
    port: int = field(default_factory=lambda: env_int("BACKUP_CAMERA_PORT", 8080))


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    detector: DetectorConfig = field(default_factory=DetectorConfig)
    trigger: TriggerConfig = field(default_factory=TriggerConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    web: WebConfig = field(default_factory=WebConfig)


def load_config() -> Config:
    return Config()
