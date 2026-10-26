"""The Bridge: polls the Controller on a schedule and publishes its values."""

import logging
import time
from typing import Any, Protocol

from luxtronik2mqtt.config import Settings
from luxtronik2mqtt.controller import Unreachable
from luxtronik2mqtt.formatting import payload
from luxtronik2mqtt.publishing import Publisher
from luxtronik2mqtt.selection import selected

LOGGER = logging.getLogger(__name__)


class Clock(Protocol):
    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class ControllerReader(Protocol):
    """What the Bridge needs from the Controller adapter, or from a fake one in tests."""

    def read_calculations(self) -> Any: ...


class Bridge:
    """Polls the CFI every poll interval and publishes the selected values that changed.

    Time comes from the clock, so tests drive the schedule with `run_pending`.
    """

    def __init__(self, settings: Settings, controller: ControllerReader, clock: Clock | None = None) -> None:
        self._settings = settings
        self._controller = controller
        self._clock = clock or SystemClock()
        self._publisher = Publisher(settings)
        self._next_cfi_poll: float | None = None

    def start(self) -> None:
        self._publisher.connect()

    def stop(self) -> None:
        self._publisher.disconnect()

    def run(self) -> None:
        """Poll on schedule until interrupted."""
        while True:
            self._clock.sleep(self.run_pending())

    def run_pending(self) -> float:
        """Run every poll that is due now. Returns the seconds until the next one is due."""
        now = self._clock.monotonic()
        if self._next_cfi_poll is None or now >= self._next_cfi_poll:
            self._poll_cfi()
            due = (now if self._next_cfi_poll is None else self._next_cfi_poll) + self._settings.cfi_poll_interval
            # After a poll that ran late, keep the interval from now instead of catching up.
            self._next_cfi_poll = due if due > now else now + self._settings.cfi_poll_interval
        return max(self._next_cfi_poll - self._clock.monotonic(), 0.0)

    def _poll_cfi(self) -> None:
        try:
            calculations = self._controller.read_calculations()
        except Unreachable as error:
            LOGGER.warning("%s", error)
            return
        payloads = {}
        for _, field in calculations.items():
            path = f"cfi/calculations/{field.name}"
            text = payload(field)
            if text is not None and selected(path):
                payloads[path] = text
        self._publisher.publish_changes(payloads)
