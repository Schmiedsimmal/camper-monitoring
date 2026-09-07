"""FastAPI-Web-UI: MJPEG-Livestream + Status-Endpoints."""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .camera import CameraSource
from .detector import Detector
from .trigger import Trigger

log = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def build_app(camera: CameraSource, detector: Detector, trigger: Trigger) -> FastAPI:
    app = FastAPI(title="backup-camera")

    state = {"fps": 0.0, "detections": 0, "last_detect_ts": 0.0}

    @app.get("/healthz")
    async def healthz() -> dict:
        return {
            "status": "ok",
            "camera_open": camera.is_open(),
            "detector_loaded": detector.loaded,
            "trigger_available": trigger.available,
        }

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

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    def _generate_mjpeg():
        """Endlosschleife, die annotierte JPEG-Frames als MJPEG liefert."""
        last_ts = time.time()
        frames_in_window = 0
        window_start = time.time()
        while True:
            frame = camera.latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue

            # Trigger-Gating: wenn gated und Trigger inaktiv -> Standbild mit
            # Hinweis, keine Inferenz (spart GPU).
            from . import _runtime  # noqa: WPS433  (Runtime-Flags aus main)
            gated = _runtime.GATED
            trigger_active = trigger.active
            if gated and not trigger_active:
                cv2.putText(
                    frame, "Rueckfahrlicht inaktiv - kein Stream",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2,
                )
            else:
                frame, dets = detector.detect(frame)
                state["detections"] = len(dets)
                state["last_detect_ts"] = time.time()

            # FPS-Messung
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
