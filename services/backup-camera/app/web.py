"""FastAPI web UI: MJPEG live stream + status endpoints."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from shared.camera import CameraSource
from shared.web import add_index_route, add_health_route

from .detector import Detector
from .overlay import BackupOverlay
from .trigger import Trigger

log = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def build_app(
    camera: CameraSource,
    detector: Detector,
    trigger: Trigger,
    overlay: BackupOverlay,
    gated: bool,
) -> FastAPI:
    """Build the FastAPI app.

    *gated* is passed explicitly (instead of via a runtime module) to
    avoid circular imports between main.py and web.py.
    """
    app = FastAPI(title="backup-camera")
    state = {"fps": 0.0, "detections": 0}

    add_index_route(app, TEMPLATES_DIR)
    add_health_route(app, lambda: {
        "camera_open": camera.is_open(),
        "detector_loaded": detector.loaded,
        "trigger_available": trigger.available,
    })

    @app.get("/status")
    async def status() -> dict:
        return {
            "trigger_active": trigger.active,
            "trigger_available": trigger.available,
            "camera_open": camera.is_open(),
            "detector_loaded": detector.loaded,
            "using_engine": detector.using_engine,
            "device": detector.device,
            "fps": round(state["fps"], 1),
            "detections": state["detections"],
        }

    def _annotate(frame) -> None:
        trigger_active = trigger.active
        if gated and not trigger_active:
            cv2.putText(
                frame, "Reversing light inactive - no stream",
                (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
            )
            return
        _, dets = detector.detect(frame)
        state["detections"] = len(dets)
        overlay.draw(frame)

    def _generate_mjpeg():
        frames_in_window = 0
        window_start = time.time()
        for frame in camera.frames():
            _annotate(frame)
            frames_in_window += 1
            now = time.time()
            if now - window_start >= 1.0:
                state["fps"] = frames_in_window / (now - window_start)
                frames_in_window = 0
                window_start = now
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                continue
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            )

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(
            _generate_mjpeg(),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    return app
