"""Rückfahrkamera-Overlay: Abstandslinien + Fahrzeug-Kontur.

Projiziert Bodenpunkte (in Metern hinter dem Fahrzeug) in Bildkoordinaten
mittels einer einfachen Pinhole-Kamerageometrie. Keine Kalibrierung nötig —
die Parameter (Montagehöhe, Neigung, FOV) kommen aus der Config und sind
groß genug für das Rangieren.

Geometrie (Seitenansicht):

    Kamera (Höhe h, Neigung θ nach unten)
       │
       │  Sichtstrahl
       ▼
       ──────────────── Boden
       0m   1m   2m   3m   5m   (Abstand hinter Fahrzeug)

Für einen Bodenpunkt im Abstand d (gemessen ab dem Punkt direkt unter der
Kamera) ergibt sich der Bild-pixel-y aus der Winkelbeziehung:

    α = atan(d / h)              # Winkel unten vom Horizont
    β = α - θ                    # Winkel im Bild (relativ zur Optikachse)
    y_norm = 0.5 + (β / (vfov/2))  # normalisierte Bildhöhe (0=oben, 1=unten)

Die horizontale Position (x) ergibt sich aus der Perspektive: weiter weg
bedeutet näher an der Bildmitte.
"""
from __future__ import annotations

import logging
import math
from typing import Sequence

import cv2
import numpy as np

from .config import OverlayConfig

log = logging.getLogger(__name__)


class BackupOverlay:
    """Zeichnet Abstandslinien + Fahrzeug-Kontur in ein Bild."""

    def __init__(self, cfg: OverlayConfig, img_w: int, img_h: int) -> None:
        self.cfg = cfg
        self.img_w = img_w
        self.img_h = img_h
        # Vertikaler FOV aus horizontalem FOV + Bildseitenverhältnis.
        hfov_rad = math.radians(cfg.camera_hfov)
        aspect = img_h / img_w
        self.vfov_rad = 2.0 * math.atan(math.tan(hfov_rad / 2.0) * aspect)
        self.tilt_rad = math.radians(cfg.camera_tilt)
        log.info(
            "Overlay initialisiert: img=%dx%d, hfov=%.1f°, vfov=%.1f°, tilt=%.1f°, h=%.2fm",
            img_w, img_h, cfg.camera_hfov, math.degrees(self.vfov_rad),
            cfg.camera_tilt, cfg.camera_height,
        )

    # ---- Projektion ---------------------------------------------------------
    def _ground_to_image_y(self, distance_m: float) -> float | None:
        """Projiziert einen Bodenpunkt im Abstand distance_m (ab Punkt direkt
        unter der Kamera) auf die normierte Bild-y-Koordinate [0=oben, 1=unten].

        Geometrie (Seitenansicht, Kamera in Höhe h, Optikachse um tilt nach
        unten geneigt):

            Horizont ─────────────────────────────
                       ╲  alpha = atan(h/d)  (Winkel unter dem Horizont)
                        ╲
                         ╲  Optikachse (tilt)
                          ╲
                           ● Kamera (Höhe h)
                           │
                           │ h
                           │
            ───────●─────── Boden
                   d (Abstand hinter Fahrzeug)

        - d klein (nah)  -> alpha groß  -> Punkt weit unten im Bild
        - d groß  (weit) -> alpha klein -> Punkt nah am Horizont (oben)

        Liefert None, wenn der Punkt außerhalb des Sichtfelds liegt.
        """
        h = self.cfg.camera_height
        if distance_m <= 0:
            return None
        # Winkel vom Horizont (nach unten) zum Bodenpunkt.
        alpha = math.atan(h / distance_m)
        # Winkel relativ zur Optikachse (tilt = Neigung der Optikachse unter den Horizont).
        beta = alpha - self.tilt_rad
        # beta>0 -> Punkt unterhalb der Optikachse -> weiter unten im Bild
        # beta<0 -> Punkt oberhalb der Optikachse -> weiter oben (Richtung Horizont)
        y_norm = 0.5 + (beta / (self.vfov_rad / 2.0)) * 0.5
        if y_norm < 0.0 or y_norm > 1.0:
            return None
        return y_norm

    def _ground_to_image_x(self, distance_m: float, lateral_m: float) -> float | None:
        """Projiziert die laterale Position (lateral_m, 0=Mitte) im Abstand
        distance_m auf die normierte Bild-x-Koordinate [0=links, 1=rechts]."""
        if distance_m <= 0:
            return None
        hfov_half = math.radians(self.cfg.camera_hfov) / 2.0
        # Winkel zur lateralen Position
        angle = math.atan(lateral_m / distance_m)
        x_norm = 0.5 + (angle / hfov_half) * 0.5
        # Auf Bild begrenzen (Punkte außerhalb werden geclippt)
        return max(0.0, min(1.0, x_norm))

    def _to_px(self, x_norm: float, y_norm: float) -> tuple[int, int]:
        return int(round(x_norm * (self.img_w - 1))), int(round(y_norm * (self.img_h - 1)))

    # ---- Farb-Coding --------------------------------------------------------
    def _line_color(self, distance_m: float) -> tuple[int, int, int]:
        cfg = self.cfg
        if distance_m <= cfg.zone_yellow_max:
            return cfg.color_red
        if distance_m <= cfg.zone_green_max:
            return cfg.color_yellow
        return cfg.color_green

    # ---- Öffentliche API ----------------------------------------------------
    def draw(self, frame) -> None:
        """Zeichnet das Overlay inline in das frame (in-place)."""
        if not self.cfg.enabled:
            return

        # 1) Horizontale Abstandslinien
        for d in self.cfg.distance_lines:
            y_norm = self._ground_to_image_y(d)
            if y_norm is None:
                continue
            y_px = int(round(y_norm * (self.img_h - 1)))
            color = self._line_color(d)
            # Halbdurchsichtige Linie: Overlay auf Kopie, dann mischen.
            overlay = frame.copy()
            cv2.line(overlay, (0, y_px), (self.img_w - 1, y_px), color, 2)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
            # Beschriftung
            label = f"{d:g} m"
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            tx, ty = 12, max(th + 4, y_px - 6)
            cv2.rectangle(frame, (tx - 2, ty - th - 2), (tx + tw + 4, ty + 2), (0, 0, 0), -1)
            cv2.putText(frame, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 1, cv2.LINE_AA)

        # 2) Fahrzeug-Kontur (Trapez, das die Fahrzeugbreite in den
        #    Abständen 1m, 2m, 3m projiziert). Verbunden als Linien.
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

        # Linke und rechte Fahrzeug-Kante als durchgehende Linien zeichnen
        # (Punkte in Reihenfolge: für d=1: links,rechts; d=2: links,rechts; ...)
        if len(contour_points) >= 4:
            overlay = frame.copy()
            # Linke Kante: Punkte 0, 2, 4, ...
            left = contour_points[0::2]
            # Rechte Kante: Punkte 1, 3, 5, ...
            right = contour_points[1::2]
            for pts in (left, right):
                for i in range(len(pts) - 1):
                    cv2.line(overlay, pts[i], pts[i + 1], self.cfg.color_line, 2)
            # Querverbindungen auf gleicher Distanz
            for i in range(0, len(contour_points), 2):
                if i + 1 < len(contour_points):
                    cv2.line(overlay, contour_points[i], contour_points[i + 1], self.cfg.color_line, 1)
            cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # 3) Horizont-Marker (dezenter Hinweis, wo der waagerechte Sichtstrahl
        #    trifft — hilft beim Kalibrieren). Der Horizont (d->∞) liegt bei
        #    alpha=0, also beta=-tilt -> y_norm = 0.5 - tilt/(vfov/2)*0.5.
        y_h = 0.5 - (self.tilt_rad / (self.vfov_rad / 2.0)) * 0.5
        if 0.0 <= y_h <= 1.0:
            y_px = int(round(y_h * (self.img_h - 1)))
            cv2.line(frame, (0, y_px), (self.img_w - 1, y_px), (90, 90, 90), 1)
