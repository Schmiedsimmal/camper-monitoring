"""Rear-view camera overlay: distance lines + vehicle contour.

Projects ground points (in meters behind the vehicle) to image
coordinates using a simple pinhole camera geometry. No calibration
required — the parameters (mount height, tilt, FOV) come from config
and are accurate enough for maneuvering.

Geometry (side view):

    Camera (height h, tilt theta downward)
       |
       |  line of sight
       v
       ---------------- ground
       0m   1m   2m   3m   5m   (distance behind vehicle)

For a ground point at distance d (measured from directly below the
camera) the image pixel-y follows from the angular relationship:

    alpha = atan(h / d)              # angle below horizon
    beta  = alpha - theta            # angle relative to optical axis
    y_norm = 0.5 + (beta / (vfov/2)) * 0.5   # normalized image height

The horizontal position follows from perspective: farther away means
closer to the image center.
"""
from __future__ import annotations

import logging
import math

import cv2

from .config import OverlayConfig

log = logging.getLogger(__name__)


class BackupOverlay:
    """Draws distance lines + vehicle contour onto a frame."""

    # Line colors (BGR).
    COLOR_GREEN = (0, 200, 0)
    COLOR_YELLOW = (0, 220, 220)
    COLOR_RED = (0, 0, 220)
    COLOR_LINE = (255, 255, 255)
    COLOR_HORIZON = (90, 90, 90)

    def __init__(self, cfg: OverlayConfig, img_w: int, img_h: int) -> None:
        self.cfg = cfg
        self.img_w = img_w
        self.img_h = img_h
        hfov_rad = math.radians(cfg.camera_hfov)
        aspect = img_h / img_w
        self.vfov_rad = 2.0 * math.atan(math.tan(hfov_rad / 2.0) * aspect)
        self.tilt_rad = math.radians(cfg.camera_tilt)
        log.info(
            "Overlay initialized: img=%dx%d, hfov=%.1f, vfov=%.1f, tilt=%.1f, h=%.2fm",
            img_w, img_h, cfg.camera_hfov, math.degrees(self.vfov_rad),
            cfg.camera_tilt, cfg.camera_height,
        )

    # -- projection -----------------------------------------------------------
    def _ground_to_image_y(self, distance_m: float) -> float | None:
        """Project a ground point at *distance_m* to normalized image y [0=top, 1=bottom].

        Returns None if the point is outside the field of view.
        """
        if distance_m <= 0:
            return None
        alpha = math.atan(self.cfg.camera_height / distance_m)
        beta = alpha - self.tilt_rad
        y_norm = 0.5 + (beta / (self.vfov_rad / 2.0)) * 0.5
        if y_norm < 0.0 or y_norm > 1.0:
            return None
        return y_norm

    def _ground_to_image_x(self, distance_m: float, lateral_m: float) -> float | None:
        """Project lateral position at *distance_m* to normalized image x [0=left, 1=right]."""
        if distance_m <= 0:
            return None
        hfov_half = math.radians(self.cfg.camera_hfov) / 2.0
        angle = math.atan(lateral_m / distance_m)
        return max(0.0, min(1.0, 0.5 + (angle / hfov_half) * 0.5))

    def _to_px(self, x_norm: float, y_norm: float) -> tuple[int, int]:
        return int(round(x_norm * (self.img_w - 1))), int(round(y_norm * (self.img_h - 1)))

    # -- color coding ---------------------------------------------------------
    def _line_color(self, distance_m: float) -> tuple[int, int, int]:
        cfg = self.cfg
        if distance_m <= cfg.zone_yellow_max:
            return self.COLOR_RED
        if distance_m <= cfg.zone_green_max:
            return self.COLOR_YELLOW
        return self.COLOR_GREEN

    # -- public API -----------------------------------------------------------
    def draw(self, frame) -> None:
        """Draw the overlay in-place onto *frame*."""
        if not self.cfg.enabled:
            return

        self._draw_distance_lines(frame)
        self._draw_vehicle_contour(frame)
        self._draw_horizon(frame)

    def _draw_distance_lines(self, frame) -> None:
        for d in self.cfg.distance_lines:
            y_norm = self._ground_to_image_y(d)
            if y_norm is None:
                continue
            y_px = int(round(y_norm * (self.img_h - 1)))
            color = self._line_color(d)
            overlay = frame.copy()
            cv2.line(overlay, (0, y_px), (self.img_w - 1, y_px), color, 2)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            label = f"{d:g} m"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            tx, ty = 12, max(th + 4, y_px - 6)
            cv2.rectangle(frame, (tx - 2, ty - th - 2), (tx + tw + 4, ty + 2), (0, 0, 0), -1)
            cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)

    def _draw_vehicle_contour(self, frame) -> None:
        """Draw a trapezoid projecting the vehicle width at 1m, 2m, 3m."""
        half_w = self.cfg.vehicle_width / 2.0
        contour_points: list[tuple[int, int]] = []
        for d in (1.0, 2.0, 3.0):
            y_norm = self._ground_to_image_y(d)
            if y_norm is None:
                continue
            for side in (-half_w, half_w):
                x_norm = self._ground_to_image_x(d, side)
                if x_norm is None:
                    continue
                contour_points.append(self._to_px(x_norm, y_norm))

        if len(contour_points) < 4:
            return

        overlay = frame.copy()
        left = contour_points[0::2]
        right = contour_points[1::2]
        for pts in (left, right):
            for i in range(len(pts) - 1):
                cv2.line(overlay, pts[i], pts[i + 1], self.COLOR_LINE, 2)
        for i in range(0, len(contour_points), 2):
            if i + 1 < len(contour_points):
                cv2.line(overlay, contour_points[i], contour_points[i + 1], self.COLOR_LINE, 1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

    def _draw_horizon(self, frame) -> None:
        """Draw a subtle horizon marker (helps with calibration)."""
        y_h = 0.5 - (self.tilt_rad / (self.vfov_rad / 2.0)) * 0.5
        if 0.0 <= y_h <= 1.0:
            y_px = int(round(y_h * (self.img_h - 1)))
            cv2.line(frame, (0, y_px), (self.img_w - 1, y_px), self.COLOR_HORIZON, 1)
