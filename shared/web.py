"""MJPEG streaming + FastAPI helpers shared across services.

Provides a reusable MJPEG generator and a ``serve_template`` helper
so services don't duplicate the same streaming boilerplate.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import cv2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

from .camera import CameraSource


def mjpeg_generator(
    camera: CameraSource,
    annotate: Callable[[object], None] | None = None,
    jpeg_quality: int = 80,
):
    """Yield MJPEG multipart frames from *camera*.

    If *annotate* is given, it is called with each frame before encoding
    (e.g. to draw bounding boxes or overlay lines).
    """
    while True:
        frame = camera.latest_frame()
        if frame is None:
            time.sleep(0.05)
            continue
        if annotate is not None:
            annotate(frame)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality])
        if not ok:
            continue
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
        )


def add_stream_route(app: FastAPI, camera: CameraSource, annotate=None) -> None:
    """Register ``GET /stream`` (MJPEG) on *app*."""
    def _gen():
        yield from mjpeg_generator(camera, annotate)
    app.add_api_route(
        "/stream",
        lambda: StreamingResponse(_gen(), media_type="multipart/x-mixed-replace; boundary=frame"),
        methods=["GET"],
    )


def add_index_route(app: FastAPI, templates_dir: Path, filename: str = "index.html") -> None:
    """Register ``GET /`` serving a static HTML template."""
    def _index() -> HTMLResponse:
        html = (templates_dir / filename).read_text(encoding="utf-8")
        return HTMLResponse(html)
    app.add_api_route("/", _index, methods=["GET"], response_class=HTMLResponse)


def add_health_route(app: FastAPI, extra: Callable[[], dict] | None = None) -> None:
    """Register ``GET /healthz``."""
    def _healthz() -> dict:
        base = {"status": "ok"}
        if extra is not None:
            base.update(extra())
        return base
    app.add_api_route("/healthz", _healthz, methods=["GET"])
