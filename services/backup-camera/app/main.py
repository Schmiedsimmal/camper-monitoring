"""backup-camera service entry point.

Orchestrates camera, detector, trigger and web server.
"""
from __future__ import annotations

import logging
import os

import uvicorn

from shared.camera import CameraSource

from .config import load_config
from .detector import Detector
from .overlay import BackupOverlay
from .trigger import make_trigger
from .web import build_app

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("backup-camera")


def main() -> None:
    cfg = load_config()

    camera = CameraSource(
        cfg.camera.source, cfg.camera.width, cfg.camera.height, cfg.camera.fps,
    )
    camera.start()
    log.info("Camera source started: %s", cfg.camera.source)

    detector = Detector(cfg.detector)
    try:
        detector.load()
    except Exception as exc:  # noqa: BLE001
        log.error("Model load failed: %s. Service runs without inference.", exc)

    trigger = make_trigger(cfg.trigger)
    log.info(
        "Trigger ready: available=%s, gated=%s",
        trigger.available, cfg.trigger.gated,
    )

    overlay = BackupOverlay(cfg.overlay, cfg.camera.width, cfg.camera.height)
    log.info("Overlay ready: enabled=%s", cfg.overlay.enabled)

    app = build_app(camera, detector, trigger, overlay, gated=cfg.trigger.gated)
    uvicorn.run(app, host="0.0.0.0", port=cfg.web.port, log_level="info")


if __name__ == "__main__":
    main()
