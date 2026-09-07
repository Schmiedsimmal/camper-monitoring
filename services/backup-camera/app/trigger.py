"""GPIO-Trigger: 12V-Rückfahrlichtsignal über Optokoppler.

Auf dem Jetson (aarch64) wird gpiozero mit dem Linux-Pin-Backend verwendet.
Auf x86-Dev-Maschen ohne GPIO-Hardware fällt der Service auf einen
DummyTrigger zurück (immer aktiv), damit die Pipeline getestet werden kann.
"""
from __future__ import annotations

import logging
from typing import Protocol

from .config import TriggerConfig

log = logging.getLogger(__name__)


class Trigger(Protocol):
    @property
    def available(self) -> bool: ...

    @property
    def active(self) -> bool: ...


class DummyTrigger:
    """Immer aktiv — für Dev/Tests ohne GPIO-Hardware."""

    @property
    def available(self) -> bool:
        return False

    @property
    def active(self) -> bool:
        return True


class GpioTrigger:
    """gpiozero-basierter Trigger am Jetson.

    active_low=true (Default für PC817-Schaltung): Pin liegt bei aktivem
    12V-Signal auf GND, gpiozero.inverted=True liefert dann active=True.
    """

    def __init__(self, cfg: TriggerConfig) -> None:
        self.cfg = cfg
        # Lazy import, damit das Modul auf Nicht-Jetson-Hosts importierbar bleibt.
        from gpiozero import Button  # type: ignore

        # pull_up=True hält den Pin intern auf High, der Optokoppler zieht
        # ihn auf Low -> active_state=False entspricht "aktiv".
        pull_up = True
        active_state = False if cfg.active_low else True
        self._btn = Button(
            cfg.gpio_pin,
            pull_up=pull_up,
            active_state=active_state,
            bounce_time=0.05,
        )
        log.info(
            "GpioTrigger initialisiert: Pin BCM %d, active_low=%s",
            cfg.gpio_pin, cfg.active_low,
        )

    @property
    def available(self) -> bool:
        return True

    @property
    def active(self) -> bool:
        return bool(self._btn.is_active)


def make_trigger(cfg: TriggerConfig) -> Trigger:
    try:
        return GpioTrigger(cfg)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "GPIO-Trigger nicht verfügbar (%s). Verwende DummyTrigger (immer aktiv). "
            "Auf x86-Dev-Maschen ist das erwartet.", e,
        )
        return DummyTrigger()
