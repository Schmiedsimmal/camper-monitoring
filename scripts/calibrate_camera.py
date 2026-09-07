#!/usr/bin/env python3
"""Chessboard-Kamerakalibrierung für den backup-camera-Service.

Speichert Kameramatrix + Verzerrungskoeffizienten in einer .npz-Datei, die
später vom Overlay zur verzerrungsfreien Linien-Projektion verwendet werden
kann (aktuell vorbereitet, noch nicht automatisch in die Pipeline eingebunden).

Verwendung:
    # 1) Ein Schachbrett-Muster ausdrucken (z.B. 9x6 innere Ecken, 25mm Quadrate)
    #    Siehe: https://github.com/opencv/opencv/blob/4.x/doc/pattern.png
    # 2) Kamera an Jetson anschließen (/dev/video0)
    # 3) Skript starten und ~15-20 Bilder aus verschiedenen Winkeln aufnehmen:

    python scripts/calibrate_camera.py --device 0 --output camera_params.npz

    # Alternativ: Bilder aus einem Ordner kalibrieren (ohne Live-Kamera):
    python scripts/calibrate_camera.py --images ./calib_images/ --output camera_params.npz

Die ausgegebene .npz enthält:
    - mtx:        Kameramatrix (3x3)
    - dist:       Verzerrungskoeffizienten (k1, k2, p1, p2, k3)
    - rvecs:      Rotationsvektoren pro Bild
    - tvecs:      Translationsvektoren pro Bild
    - img_size:   Bildgröße (w, h)
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger("calibrate")

# Schachbrett-Parameter (an das gedruckte Muster anpassen).
DEFAULT_CHESSBOARD = (9, 6)      # innere Ecken (Spalten, Zeilen)
DEFAULT_SQUARE_MM = 25.0         # Kantenlänge eines Quadrats in mm


def find_corners(img_gray, pattern_size):
    """Sucht Schachbrett-Ecken im Bild. Liefert die 2D-Punkte oder None."""
    found, corners = cv2.findChessboardCorners(
        img_gray, pattern_size,
        cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE,
    )
    if not found:
        return None
    # Subpixel-Verfeinerung
    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-3)
    corners = cv2.cornerSubPix(img_gray, corners, (11, 11), (-1, -1), criteria)
    return corners


def collect_from_camera(device: int, pattern_size, n_images: int) -> tuple[list, tuple[int, int]]:
    """Sammelt Kalibrierungsbilder von der Live-Kamera."""
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        raise RuntimeError(f"Kamera {device} nicht öffnbar")
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Kamera {device} geöffnet: {w}x{h}")
    print(f"Bitte {n_images} Bilder des Schachbretts aus verschiedenen Winkeln aufnehmen.")
    print("Tasten: [Leertaste] = Aufnehmen, [q] = Beenden\n")

    objpoints: list[np.ndarray] = []
    imgpoints: list[np.ndarray] = []
    captured = 0

    # Objektpunkte (3D) im realen Raum, z=0 für alle.
    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)

    while captured < n_images:
        ok, frame = cap.read()
        if not ok:
            continue
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        corners = find_corners(gray, pattern_size)
        display = frame.copy()
        if corners is not None:
            cv2.drawChessboardCorners(display, pattern_size, corners, True)
        cv2.putText(display, f"Captured: {captured}/{n_images}  (SPACE=save, q=quit)",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("calibrate", display)
        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            break
        if key == ord(" ") and corners is not None:
            objpoints.append(objp)
            imgpoints.append(corners)
            captured += 1
            print(f"  Bild {captured}/{n_images} aufgenommen.")

    cap.release()
    cv2.destroyAllWindows()
    if captured < 5:
        raise RuntimeError(f"Zu wenige Bilder ({captured}). Mindestens 5 nötig.")
    return list(zip(objpoints, imgpoints)), (w, h)


def collect_from_images(folder: Path, pattern_size) -> tuple[list, tuple[int, int]]:
    """Sammelt Kalibrierungsbilder aus einem Ordner."""
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    files = sorted(f for f in folder.iterdir() if f.suffix.lower() in exts)
    if not files:
        raise RuntimeError(f"Keine Bilder in {folder} gefunden")

    objp = np.zeros((pattern_size[0] * pattern_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:pattern_size[0], 0:pattern_size[1]].T.reshape(-1, 2)

    objpoints: list[np.ndarray] = []
    imgpoints: list[np.ndarray] = []
    img_size = None

    for f in files:
        img = cv2.imread(str(f))
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        if img_size is None:
            img_size = (gray.shape[1], gray.shape[0])
        corners = find_corners(gray, pattern_size)
        if corners is not None:
            objpoints.append(objp)
            imgpoints.append(corners)
            print(f"  {f.name}: Ecken gefunden")
        else:
            print(f"  {f.name}: keine Ecken (übersprungen)")

    if len(objpoints) < 5:
        raise RuntimeError(f"Zu wenige brauchbare Bilder ({len(objpoints)}). Mindestens 5 nötig.")
    return list(zip(objpoints, imgpoints)), img_size


def calibrate(samples, img_size, square_mm: float):
    """Führt die Kalibrierung durch. Liefert (mtx, dist, rvecs, tvecs)."""
    objpoints = [s[0] for s in samples]
    imgpoints = [s[1] for s in samples]
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, img_size, None, None,
    )
    print(f"\nKalibrierung abgeschlossen. RMS-Reprojektionsfehler: {ret:.4f}")
    print(f"Kameramatrix:\n{mtx}")
    print(f"Verzerrungskoeffizienten: {dist.ravel()}")
    return mtx, dist, rvecs, tvecs


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    p = argparse.ArgumentParser(description="Chessboard-Kamerakalibrierung")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--device", type=int, help="USB-Kamera-Index (z.B. 0)")
    src.add_argument("--images", type=Path, help="Ordner mit Kalibrierungsbildern")
    p.add_argument("--output", type=Path, default=Path("camera_params.npz"),
                   help="Ausgabe-Datei (Default: camera_params.npz)")
    p.add_argument("--pattern", type=int, nargs=2, default=list(DEFAULT_CHESSBOARD),
                   metavar=("COLS", "ROWS"), help="Innere Ecken des Schachbretts")
    p.add_argument("--square-mm", type=float, default=DEFAULT_SQUARE_MM,
                   help="Kantenlänge eines Schachbrett-Quadrats in mm")
    p.add_argument("--n-images", type=int, default=15,
                   help="Anzahl Bilder (nur --device)")
    args = p.parse_args()

    pattern_size = tuple(args.pattern)

    if args.device is not None:
        samples, img_size = collect_from_camera(args.device, pattern_size, args.n_images)
    else:
        samples, img_size = collect_from_images(args.images, pattern_size)

    mtx, dist, rvecs, tvecs = calibrate(samples, img_size, args.square_mm)

    np.savez(
        args.output,
        mtx=mtx, dist=dist, rvecs=np.array(rvecs), tvecs=np.array(tvecs),
        img_size=np.array(img_size),
    )
    print(f"\nParameter gespeichert: {args.output}")
    print("Im .env dann OVERLAY_CALIB_FILE=<pfad> setzen (Feature folgt).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
