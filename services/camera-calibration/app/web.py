"""FastAPI web UI for camera calibration.

Two modes:
  1. Click mode (/click): live stream + click points + fit geometry
  2. Chessboard mode (/chessboard): capture images + calibrateCamera
"""
from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from shared.camera import CameraSource
from shared.web import add_health_route, add_index_route

from .calibration import (
    detect_chessboard,
    fit_overlay_geometry,
    load_json,
    run_chessboard_calibration,
    save_json,
)
from .config import Config

log = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def build_app(camera: CameraSource, cfg: Config) -> FastAPI:
    app = FastAPI(title="camera-calibration")

    # State for click mode.
    click_points: list[dict] = []
    # State for chessboard mode.
    chessboard_samples: list = []

    calib_dir = Path(cfg.calib_dir)
    click_file = calib_dir / "overlay_geometry.json"
    chessboard_file = calib_dir / "chessboard.json"

    add_index_route(app, TEMPLATES_DIR)
    add_health_route(app, lambda: {"camera_open": camera.is_open()})

    # -- Live stream (MJPEG) --------------------------------------------------
    def _annotate_click_points(frame) -> None:
        for p in click_points:
            y = p["y_px"]
            cv2.line(frame, (0, y), (frame.shape[1] - 1, y), (0, 255, 255), 2)
            cv2.putText(
                frame, f"{p['distance_m']}m", (12, y - 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2,
            )

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        from shared.web import mjpeg_generator
        return StreamingResponse(
            mjpeg_generator(camera, _annotate_click_points, jpeg_quality=85),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    # -- Click mode -----------------------------------------------------------
    @app.post("/click/add")
    async def click_add(body: dict) -> dict:
        y_px = int(body.get("y_px", -1))
        d = float(body.get("distance_m", 0))
        if y_px < 0 or d <= 0:
            return {"error": "y_px and distance_m must be positive"}
        click_points.append({"y_px": y_px, "distance_m": d})
        return {"ok": True, "n_points": len(click_points)}

    @app.delete("/click/clear")
    async def click_clear() -> dict:
        click_points.clear()
        return {"ok": True, "n_points": 0}

    @app.post("/click/fit")
    async def click_fit(body: dict) -> dict:
        if len(click_points) < 2:
            return {"error": "At least 2 points required"}
        hfov = float(body.get("hfov", 130.0))
        pts = [(p["y_px"], p["distance_m"]) for p in click_points]
        try:
            result = fit_overlay_geometry(pts, cfg.camera_width, cfg.camera_height, hfov)
        except Exception as exc:
            return {"error": str(exc)}
        save_json({"type": "overlay_geometry", **result}, click_file)
        return {"ok": True, "result": result}

    @app.get("/click/points")
    async def click_points_get() -> dict:
        return {"points": click_points, "n_points": len(click_points)}

    # -- Chessboard mode ------------------------------------------------------
    @app.post("/chessboard/capture")
    async def chessboard_capture() -> dict:
        frame = camera.latest_frame()
        if frame is None:
            return {"error": "No camera frame available"}
        pattern = (cfg.chessboard_cols, cfg.chessboard_rows)
        corners, _ = detect_chessboard(frame, pattern)
        if corners is None:
            return {"ok": False, "message": "No chessboard detected"}
        objp = np.zeros((pattern[0] * pattern[1], 3), np.float32)
        objp[:, :2] = np.mgrid[0:pattern[0], 0:pattern[1]].T.reshape(-1, 2)
        chessboard_samples.append((objp, corners))
        return {"ok": True, "n_samples": len(chessboard_samples)}

    @app.delete("/chessboard/clear")
    async def chessboard_clear() -> dict:
        chessboard_samples.clear()
        return {"ok": True, "n_samples": 0}

    @app.post("/chessboard/calibrate")
    async def chessboard_calibrate() -> dict:
        if len(chessboard_samples) < 5:
            return {"error": f"At least 5 images required (current: {len(chessboard_samples)})"}
        img_size = (cfg.camera_width, cfg.camera_height)
        try:
            result = run_chessboard_calibration(chessboard_samples, img_size)
        except Exception as exc:
            return {"error": str(exc)}
        save_json({"type": "chessboard", **result}, chessboard_file)
        return {"ok": True, "result": result}

    @app.get("/chessboard/samples")
    async def chessboard_samples_get() -> dict:
        return {"n_samples": len(chessboard_samples)}

    # -- Status ---------------------------------------------------------------
    @app.get("/status")
    async def status() -> dict:
        existing = {}
        click_calib = load_json(click_file)
        if click_calib:
            existing["overlay_geometry"] = click_calib
        chess_calib = load_json(chessboard_file)
        if chess_calib:
            existing["chessboard"] = chess_calib
        return {
            "camera_open": camera.is_open(),
            "click_points": len(click_points),
            "chessboard_samples": len(chessboard_samples),
            "existing_calibration": existing,
        }

    return app
