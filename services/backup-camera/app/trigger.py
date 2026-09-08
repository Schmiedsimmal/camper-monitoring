"""GPIO trigger: 12V reversing-light signal via optocoupler.

On the Jetson (aarch64) ``gpiozero`` with the Linux pin backend is used.
On x86 dev machines without GPIO hardware the service falls back to a
``DummyTrigger`` (always active) so the pipeline can be tested.
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
    """Always active — for dev/testing without GPIO hardware."""

    @property
    def available(self) -> bool:
        return False

    @property
    def active(self) -> bool:
        return True


class GpioTrigger:
    """gpiozero-based trigger on the Jetson.

    active_low=True (default for PC817 circuit): the pin is pulled to GND
    when the 12V signal is active; ``gpiozero`` with ``active_state=False``
    reports ``is_active=True`` in that case.
    """

    def __init__(self, cfg: TriggerConfig) -> None:
        self.cfg = cfg
        # Lazy import so the module stays importable on non-Jetson hosts.
        from gpiozero import Button  # type: ignore

        pull_up = True
        active_state = not cfg.active_low
        self._btn = Button(
            cfg.gpio_pin,
            pull_up=pull_up,
            active_state=active_state,
            bounce_time=0.05,
        )
        log.info(
            "GpioTrigger initialized: pin BCM %d, active_low=%s",
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
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "GPIO trigger not available (%s). Using DummyTrigger (always active). "
            "Expected on x86 dev machines.", exc,
        )
        return DummyTrigger()
