"""FastAPI-Web-UI für die Kamerakalibrierung.

Zwei Modi:
  1. Klick-Modus (/click): Live-Stream + Punkte anklicken + Geometrie fitten
  2. Chessboard-Modus (/chessboard): Bilder aufnehmen + calibrateCamera
"""
from __future__ import annotations

import logging
import time
from pathlib import Path

import cv2
import numpy as np
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from .camera import CameraSource
from .calibration import (
    detect_chessboard,
    fit_overlay_geometry,
    load_calibration,
    run_chessboard_calibration,
    save_chessboard_calibration,
    save_click_calibration,
)
from .config import Config

log = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


def build_app(camera: CameraSource, cfg: Config) -> FastAPI:
    app = FastAPI(title="camera-calibration")

    # State für Klick-Modus
    click_points: list[dict] = []  # [{"y_px": int, "distance_m": float}, ...]
    # State für Chessboard-Modus
    chessboard_samples: list = []  # [(objpoints, imgpoints), ...]

    calib_dir = Path(cfg.calib_dir)
    click_file = calib_dir / "overlay_geometry.json"
    chessboard_file = calib_dir / "chessboard.json"

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"status": "ok", "camera_open": camera.is_open()}

    @app.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        html = (TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(html)

    # ---- Live-Stream (MJPEG) ----
    def _generate_mjpeg():
        while True:
            frame = camera.latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            # Aktuelle Klick-Punkte einzeichnen (für visuelles Feedback)
            for i, p in enumerate(click_points):
                y = p["y_px"]
                cv2.line(frame, (0, y), (frame.shape[1] - 1, y), (0, 255, 255), 2)
                cv2.putText(frame, f"{p['distance_m']}m", (12, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")

    @app.get("/stream")
    async def stream() -> StreamingResponse:
        return StreamingResponse(_generate_mjpeg(), media_type="multipart/x-mixed-replace; boundary=frame")

    # ---- Klick-Modus: Punkte hinzufügen / entfernen / fitten ----
    @app.post("/click/add")
    async def click_add(body: dict) -> dict:
        """Fügt einen Punkt hinzu. Body: {"y_px": int, "distance_m": float}."""
        y_px = int(body.get("y_px", -1))
        d = float(body.get("distance_m", 0))
        if y_px < 0 or d <= 0:
            return {"error": "y_px und distance_m müssen positiv sein"}
        click_points.append({"y_px": y_px, "distance_m": d})
        return {"ok": True, "n_points": len(click_points)}

    @app.delete("/click/clear")
    async def click_clear() -> dict:
        click_points.clear()
        return {"ok": True, "n_points": 0}

    @app.post("/click/fit")
    async def click_fit(body: dict) -> dict:
        """Fitet camera_height + camera_tilt aus den gesammelten Punkten.
        Body: {"hfov": float} (optional, default 130)."""
        if len(click_points) < 2:
            return {"error": "Mindestens 2 Punkte nötig"}
        hfov = float(body.get("hfov", 130.0))
        pts = [(p["y_px"], p["distance_m"]) for p in click_points]
        try:
            result = fit_overlay_geometry(pts, cfg.camera_width, cfg.camera_height, hfov)
        except Exception as e:
            return {"error": str(e)}
        save_click_calibration(result, click_file)
        return {"ok": True, "result": result}

    @app.get("/click/points")
    async def click_points_get() -> dict:
        return {"points": click_points, "n_points": len(click_points)}

    # ---- Chessboard-Modus ----
    @app.post("/chessboard/capture")
    async def chessboard_capture() -> dict:
        """Nimmt ein Frame auf und sucht Schachbrett-Ecken."""
        frame = camera.latest_frame()
        if frame is None:
            return {"error": "Kein Kamera-Frame"}
        pattern = (cfg.chessboard_cols, cfg.chessboard_rows)
        corners, _ = detect_chessboard(frame, pattern)
        if corners is None:
            return {"ok": False, "message": "Kein Schachbrett erkannt"}
        # Objektpunkte (3D)
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
        """Führt die Kalibrierung mit allen gesammelten Bildern durch."""
        if len(chessboard_samples) < 5:
            return {"error": f"Mindestens 5 Bilder nötig (aktuell: {len(chessboard_samples)})"}
        img_size = (cfg.camera_width, cfg.camera_height)
        try:
            result = run_chessboard_calibration(chessboard_samples, img_size, cfg.chessboard_square_mm)
        except Exception as e:
            return {"error": str(e)}
        save_chessboard_calibration(result, chessboard_file)
        return {"ok": True, "result": result}

    @app.get("/chessboard/samples")
    async def chessboard_samples_get() -> dict:
        return {"n_samples": len(chessboard_samples)}

    # ---- Status ----
    @app.get("/status")
    async def status() -> dict:
        existing = {}
        click_calib = load_calibration(click_file)
        if click_calib:
            existing["overlay_geometry"] = click_calib
        chess_calib = load_calibration(chessboard_file)
        if chess_calib:
            existing["chessboard"] = chess_calib
        return {
            "camera_open": camera.is_open(),
            "click_points": len(click_points),
            "chessboard_samples": len(chessboard_samples),
            "existing_calibration": existing,
        }

    return app
