"""Configuration for the camera-calibration service."""
from __future__ import annotations

from dataclasses import dataclass, field

from shared.env import env_float, env_int, env_str


@dataclass
class Config:
    # Camera (same source as backup-camera).
    camera_source: str = field(default_factory=lambda: env_str("CAMERA_SOURCE", "usb:0"))
    camera_width: int = field(default_factory=lambda: env_int("CAMERA_WIDTH", 1280))
    camera_height: int = field(default_factory=lambda: env_int("CAMERA_HEIGHT", 720))
    camera_fps: int = field(default_factory=lambda: env_int("CAMERA_FPS", 15))

    # Web port.
    port: int = field(default_factory=lambda: env_int("CAMERA_CALIBRATION_PORT", 8080))

    # Output directory for calibration results (shared volume).
    calib_dir: str = field(default_factory=lambda: env_str("CALIB_DIR", "/app/calib"))

    # Chessboard parameters.
    chessboard_cols: int = field(default_factory=lambda: env_int("CHESSBOARD_COLS", 9))
    chessboard_rows: int = field(default_factory=lambda: env_int("CHESSBOARD_ROWS", 6))
    chessboard_square_mm: float = field(
        default_factory=lambda: env_float("CHESSBOARD_SQUARE_MM", 25.0)
    )


def load_config() -> Config:
    return Config()
