"""Kalibrierungs-Logik: Klick-Modus (Overlay-Geometrie) + Chessboard-Modus.

Klick-Modus:
  Der Benutzer klickt im Live-Bild auf Punkte, deren reale Abstände er
  kennt (z.B. 1m, 2m, 3m Markierungen auf dem Boden). Aus mindestens 2
  solchen (y_px, distance_m)-Paaren werden camera_height, camera_tilt
  und camera_hfov zurückgerechnet.

  Geometrie (Seitenansicht):
    alpha = atan(h / d)   # Winkel vom Horizont zum Bodenpunkt
    y_norm = 0.5 + (alpha - tilt) / (vfov/2) * 0.5

  Mit 2 Punkten (d1,y1), (d2,y2) lassen sich tilt und h/vfov auflösen.
  Mit 3+ Punkten wird über Least-Squares gefittet.

Chessboard-Modus:
  Klassische OpenCV-calibrateCamera mit Schachbrett-Mustern. Liefert
  Kameramatrix + Verzerrungskoeffizienten.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ---- Klick-Modus: Overlay-Geometrie -----------------------------------------
def fit_overlay_geometry(
    points: list[tuple[float, float]],
    img_w: int,
    img_h: int,
    hfov_deg: float,
) -> dict:
    """Fit camera_height + camera_tilt aus (y_px, distance_m)-Paaren.

    points: Liste von (y_px, distance_m) — Pixel-y und realer Abstand.
    img_w, img_h: Bildgröße.
    hfov_deg: Horizontaler FOV (für vfov-Berechnung).

    Liefert dict mit camera_height, camera_tilt, residuals.
    """
    if len(points) < 2:
        raise ValueError("Mindestens 2 Punkte nötig")

    hfov_rad = math.radians(hfov_deg)
    vfov_rad = 2.0 * math.atan(math.tan(hfov_rad / 2.0) * img_h / img_w)

    # y_norm = 0.5 + (alpha - tilt) / (vfov/2) * 0.5
    # => alpha = tilt + (y_norm - 0.5) * vfov
    # Und: alpha = atan(h / d)
    # => tan(alpha) = h / d
    # => h = d * tan(alpha)
    #
    # Für alle Punkte muss h konstant sein:
    # d_i * tan(tilt + (y_norm_i - 0.5) * vfov) = h
    #
    # Mit 2 Punkten: tan(a1) / tan(a2) = d2 / d1  (h kürzt sich)
    # => a1 = atan(h/d1), a2 = atan(h/d2)
    # tilt = a1 - (y_norm1 - 0.5) * vfov
    # h = d1 * tan(a1)

    # Least-Squares über alle Punkte: Finde tilt, sodass h minimal variiert.
    # Wir probieren tilt im Bereich -45°..45° und finden das Minimum.
    best_tilt = 0.0
    best_var = float("inf")
    best_h = 0.0

    for tilt_try_deg in np.arange(-45, 46, 0.5):
        tilt_try = math.radians(tilt_try_deg)
        hs = []
        for y_px, d in points:
            y_norm = y_px / (img_h - 1)
            alpha = tilt_try + (y_norm - 0.5) * vfov_rad
            if alpha <= 0 or alpha >= math.pi / 2:
                continue
            h = d * math.tan(alpha)
            hs.append(h)
        if len(hs) < 2:
            continue
        var = np.var(hs)
        if var < best_var:
            best_var = var
            best_tilt = tilt_try
            best_h = float(np.mean(hs))

    residuals = []
    for y_px, d in points:
        y_norm = y_px / (img_h - 1)
        alpha = best_tilt + (y_norm - 0.5) * vfov_rad
        h_pred = d * math.tan(alpha)
        residuals.append(abs(h_pred - best_h))

    return {
        "camera_height": round(best_h, 3),
        "camera_tilt": round(math.degrees(best_tilt), 1),
        "camera_hfov": hfov_deg,
        "residuals": [round(r, 4) for r in residuals],
        "mean_residual": round(float(np.mean(residuals)), 4),
        "n_points": len(points),
    }


# ---- Chessboard-Modus: OpenCV calibrateCamera -------------------------------
def detect_chessboard(frame, pattern_size: tuple[int, int]):
    """Sucht Schachbrett-Ecken im Frame. Liefert (corners, gray) oder (None, gray)."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    found, corners = cv2.findChessboardCorners(
        gray, pattern_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
    )
    if not found:
        return None, gray
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
    return corners, gray


def run_chessboard_calibration(
    samples: list, img_size: tuple[int, int], square_mm: float
) -> dict:
    """Führt calibrateCamera durch.

    samples: Liste von (objpoints, imgpoints) — jeweils numpy-Arrays.
    img_size: (width, height).
    Liefert dict mit mtx, dist, rms.
    """
    objpoints = [s[0] for s in samples]
    imgpoints = [s[1] for s in samples]

    objp = np.zeros((len(objpoints[0]), 3), np.float32)
    # Wird von caller gesetzt; hier nur Kalibrierung.
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_size, None, None,
    )
    return {
        "rms": round(ret, 4),
        "mtx": mtx.tolist(),
        "dist": dist.ravel().tolist(),
        "img_size": list(img_size),
    }


# ---- Speichern / Laden ------------------------------------------------------
def save_click_calibration(result: dict, path: Path) -> None:
    """Speichert Klick-Kalibrierungsergebnis als JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"type": "overlay_geometry", **result}, f, indent=2)
    log.info("Overlay-Geometrie gespeichert: %s", path)


def save_chessboard_calibration(result: dict, path: Path) -> None:
    """Speichert Chessboard-Kalibrierungsergebnis als JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump({"type": "chessboard", **result}, f, indent=2)
    log.info("Chessboard-Kalibrierung gespeichert: %s", path)


def load_calibration(path: Path) -> dict | None:
    """Lädt Kalibrierungsergebnis aus JSON oder None."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
