"""camera-calibration service entry point."""
from __future__ import annotations

import logging
import os

import uvicorn

from shared.camera import CameraSource

from .config import load_config
from .web import build_app

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("camera-calibration")


def main() -> None:
    cfg = load_config()

    camera = CameraSource(
        cfg.camera_source, cfg.camera_width, cfg.camera_height, cfg.camera_fps,
    )
    camera.start()
    log.info("Camera source started: %s", cfg.camera_source)

    app = build_app(camera, cfg)
    uvicorn.run(app, host="0.0.0.0", port=cfg.port, log_level="info")


if __name__ == "__main__":
    main()
