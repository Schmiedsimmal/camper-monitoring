"""Config für den camera-calibration-Service."""
from __future__ import annotations

import os


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


class Config:
    # USB-Kamera (gleiche Quelle wie backup-camera).
    camera_source: str = _env("CAMERA_SOURCE", "usb:0")
    camera_width: int = _env_int("CAMERA_WIDTH", 1280)
    camera_height: int = _env_int("CAMERA_HEIGHT", 720)
    camera_fps: int = _env_int("CAMERA_FPS", 15)

    # Web-Port.
    port: int = _env_int("CAMERA_CALIBRATION_PORT", 8080)

    # Ausgabe-Verzeichnis für Kalibrierungsergebnisse (Shared-Volume).
    calib_dir: str = _env("CALIB_DIR", "/app/calib")

    # Chessboard-Parameter.
    chessboard_cols: int = _env_int("CHESSBOARD_COLS", 9)
    chessboard_rows: int = _env_int("CHESSBOARD_ROWS", 6)
    chessboard_square_mm: float = _env_float("CHESSBOARD_SQUARE_MM", 25.0)
