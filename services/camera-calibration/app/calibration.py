"""Calibration logic: click mode (overlay geometry) + chessboard mode.

Click mode:
  The user clicks points in the live image whose real distances are known
  (e.g. 1m, 2m, 3m markers on the ground). From at least 2 such
  (y_px, distance_m) pairs, camera_height, camera_tilt are fitted.

  Geometry (side view):
    alpha = atan(h / d)   # angle from horizon to ground point
    y_norm = 0.5 + (alpha - tilt) / (vfov/2) * 0.5

  With 3+ points a least-squares fit finds the tilt that minimizes
  variance in the implied camera height.

Chessboard mode:
  Classic OpenCV ``calibrateCamera`` with chessboard patterns. Returns
  the camera matrix + distortion coefficients.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


# -- Click mode: overlay geometry --------------------------------------------
def fit_overlay_geometry(
    points: list[tuple[float, float]],
    img_w: int,
    img_h: int,
    hfov_deg: float,
) -> dict:
    """Fit camera_height + camera_tilt from (y_px, distance_m) pairs.

    Args:
        points: list of (y_px, distance_m) — pixel-y and real distance.
        img_w, img_h: image dimensions.
        hfov_deg: horizontal FOV (for vfov calculation).

    Returns:
        dict with camera_height, camera_tilt, camera_hfov, residuals.
    """
    if len(points) < 2:
        raise ValueError("At least 2 points required")

    hfov_rad = math.radians(hfov_deg)
    vfov_rad = 2.0 * math.atan(math.tan(hfov_rad / 2.0) * img_h / img_w)

    # Find the tilt that minimizes variance in implied camera height.
    best_tilt = 0.0
    best_var = float("inf")
    best_h = 0.0

    for tilt_try_deg in np.arange(-45, 46, 0.5):
        tilt_try = math.radians(tilt_try_deg)
        heights = []
        for y_px, d in points:
            y_norm = y_px / (img_h - 1)
            alpha = tilt_try + (y_norm - 0.5) * vfov_rad
            if alpha <= 0 or alpha >= math.pi / 2:
                continue
            heights.append(d * math.tan(alpha))
        if len(heights) < 2:
            continue
        var = np.var(heights)
        if var < best_var:
            best_var = var
            best_tilt = tilt_try
            best_h = float(np.mean(heights))

    residuals = []
    for y_px, d in points:
        y_norm = y_px / (img_h - 1)
        alpha = best_tilt + (y_norm - 0.5) * vfov_rad
        residuals.append(abs(d * math.tan(alpha) - best_h))

    return {
        "camera_height": round(best_h, 3),
        "camera_tilt": round(math.degrees(best_tilt), 1),
        "camera_hfov": hfov_deg,
        "residuals": [round(r, 4) for r in residuals],
        "mean_residual": round(float(np.mean(residuals)), 4),
        "n_points": len(points),
    }


# -- Chessboard mode: OpenCV calibrateCamera ----------------------------------
def detect_chessboard(frame, pattern_size: tuple[int, int]):
    """Detect chessboard corners in *frame*. Returns (corners, gray) or (None, gray)."""
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
    samples: list, img_size: tuple[int, int],
) -> dict:
    """Run ``cv2.calibrateCamera`` on collected samples.

    Args:
        samples: list of (objpoints, imgpoints) — numpy arrays each.
        img_size: (width, height).

    Returns:
        dict with rms, mtx, dist, img_size.
    """
    objpoints = [s[0] for s in samples]
    imgpoints = [s[1] for s in samples]

    ret, mtx, dist, _rvecs, _tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_size, None, None,
    )
    return {
        "rms": round(ret, 4),
        "mtx": mtx.tolist(),
        "dist": dist.ravel().tolist(),
        "img_size": list(img_size),
    }


# -- Save / load --------------------------------------------------------------
def save_json(data: dict, path: Path) -> None:
    """Write *data* as JSON to *path*, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    log.info("Calibration saved: %s", path)


def load_json(path: Path) -> dict | None:
    """Load JSON from *path* or return None if it doesn't exist."""
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)
