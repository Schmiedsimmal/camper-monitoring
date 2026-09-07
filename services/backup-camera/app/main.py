"""backup-camera Service-Entry-Point.

Orchestriert Kamera, Detector, Trigger und Web-Server.
"""
from __future__ import annotations

import logging
import os

from . import _runtime
from .camera import CameraSource
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

    # Runtime-Flags für Web-Modul (vermeidet zirkuläre Imports).
    _runtime.GATED = cfg.trigger.gated

    camera = CameraSource(cfg.camera)
    camera.start()
    log.info("Kamera-Source gestartet: %s", cfg.camera.source)

    detector = Detector(cfg.detector)
    try:
        detector.load()
    except Exception as e:  # noqa: BLE001
        log.error("Modell-Laden fehlgeschlagen: %s. Service läuft ohne Inferenz.", e)

    trigger = make_trigger(cfg.trigger)
    log.info(
        "Trigger bereit: available=%s, gated=%s",
        trigger.available, cfg.trigger.gated,
    )

    overlay = BackupOverlay(cfg.overlay, cfg.camera.width, cfg.camera.height)
    log.info("Overlay bereit: enabled=%s", cfg.overlay.enabled)

    app = build_app(camera, detector, trigger, overlay)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=cfg.web.port, log_level="info")


if __name__ == "__main__":
    main()
