"""Kamera-Capture: vereinheitlicht RTSP- und USB-Quellen über OpenCV.

Unterstützt CAMERA_SOURCE:
  - "rtsp://..."  → IP-Kamera über RTSP
  - "usb:N"       → lokales V4L2-Device /dev/videoN
  - "N" (int)     → Alias für usb:N
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Iterator

import cv2

from .config import CameraConfig

log = logging.getLogger(__name__)


class CameraError(RuntimeError):
    pass


class CameraSource:
    """Thread-sicherer Frame-Grabber.

    OpenCVs VideoCapture blockiert beim Lesen von RTSP bei Verbindungsabbruch
    gerne. Daher läuft der Grab in einem Hintergrund-Thread und hält immer den
    aktuellsten Frame vor.
    """

    def __init__(self, cfg: CameraConfig) -> None:
        self.cfg = cfg
        self._cap: cv2.VideoCapture | None = None
        self._frame: cv2.typing.MatLike | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._source_index = self._resolve_source(cfg.source)

    @staticmethod
    def _resolve_source(source: str) -> int | str:
        s = source.strip()
        if s.lower().startswith("usb:"):
            return int(s.split(":", 1)[1])
        if s.lower().startswith("rtsp"):
            return s
        # reine Zahl -> USB-Index
        try:
            return int(s)
        except ValueError:
            return s

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._grab_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _open(self) -> None:
        log.info("Öffne Kamera-Quelle: %r", self._source_index)
        cap = cv2.VideoCapture(self._source_index)
        if not cap.isOpened():
            raise CameraError(f"Kamera-Quelle nicht öffnbar: {self._source_index!r}")
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)
        # Bei RTSP: Puffer klein halten für geringe Latenz.
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap

    def _grab_loop(self) -> None:
        backoff = 1.0
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                try:
                    self._open()
                    backoff = 1.0
                except CameraError as e:
                    log.warning("Kamera-Öffnung fehlgeschlagen (%s), retry in %.1fs", e, backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 10.0)
                    continue

            ok, frame = self._cap.read()
            if not ok or frame is None:
                log.warning("Frame-Lesen fehlgeschlagen, reopen.")
                self._cap.release()
                self._cap = None
                time.sleep(0.5)
                continue

            with self._lock:
                self._frame = frame

    def latest_frame(self):
        with self._lock:
            return None if self._frame is None else self._frame.copy()

    def is_open(self) -> bool:
        with self._lock:
            return self._frame is not None

    def frames(self) -> Iterator:
        """Iterator, der den jeweils aktuellsten Frame liefert."""
        while self._running:
            frame = self.latest_frame()
            if frame is None:
                time.sleep(0.05)
                continue
            yield frame
