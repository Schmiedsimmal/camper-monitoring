"""Kamera-Source für den Kalibrierungs-Service.

Öffnet eine USB-Kamera via OpenCV und liefert Frames an die Web-UI.
"""
from __future__ import annotations

import logging
import threading
import time

import cv2

log = logging.getLogger(__name__)


class CameraSource:
    def __init__(self, source: str, width: int, height: int, fps: int) -> None:
        # source Format: "usb:0" oder "0" oder "/dev/video0"
        if source.startswith("usb:"):
            index = int(source.split(":", 1)[1])
        elif source.startswith("/dev/video"):
            index = source
        else:
            index = int(source)
        self._index = index
        self._width = width
        self._height = height
        self._fps = fps
        self._cap: cv2.VideoCapture | None = None
        self._thread: threading.Thread | None = None
        self._running = False
        self._frame: bytes | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        self._cap = cv2.VideoCapture(self._index)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_FPS, self._fps)
        if not self._cap.isOpened():
            log.error("Kamera %s nicht öffnbar", self._index)
            self._cap = None
            return
        log.info("Kamera geöffnet: %s (%dx%d@%d)", self._index, self._width, self._height, self._fps)
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
            self._cap = None

    def is_open(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def _capture_loop(self) -> None:
        while self._running and self._cap:
            ok, frame = self._cap.read()
            if not ok:
                time.sleep(0.05)
                continue
            with self._lock:
                self._frame = frame
        time.sleep(0.01)

    def latest_frame(self):
        """Liefert den neuesten Frame als numpy-Array (BGR) oder None."""
        with self._lock:
            return self._frame.copy() if self._frame is not None else None
