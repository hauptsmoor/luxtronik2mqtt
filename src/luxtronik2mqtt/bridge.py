"""The Bridge: polls the Controller on a schedule and publishes its values."""

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from luxtronik2mqtt.config import Settings
from luxtronik2mqtt.controller import Unreachable
from luxtronik2mqtt.formatting import payload
from luxtronik2mqtt.publishing import Publisher
from luxtronik2mqtt.selection import selected

LOGGER = logging.getLogger(__name__)

# Payloads by topic path after the prefix. None is a field without a value.
Payloads = dict[str, str | None]


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

    def read_inputs(self) -> Any: ...

    def read_holdings(self) -> Any: ...


class _Poll:
    """One interface's poll and when it is next due."""

    def __init__(self, interval: float, read: Callable[[], Payloads | None]) -> None:
        self.interval = interval
        self.read = read
        # Due straight away when the Bridge starts.
        self.due = float("-inf")

    def run_if_due(self, now: float) -> Payloads | None:
        """The payloads if the poll was due and the interface answered, else None."""
        if now < self.due:
            return None
        due = self.due + self.interval
        # After a poll that ran late, or the first one, keep the interval from now instead of catching up.
        self.due = due if due > now else now + self.interval
        return self.read()


class Bridge:
    """Polls the CFI and the SHI, each on its own interval, and publishes the selected values that changed.

    Time comes from the clock, so tests drive the schedule with `run_pending`.
    """

    def __init__(self, settings: Settings, controller: ControllerReader, clock: Clock | None = None) -> None:
        self._settings = settings
        self._controller = controller
        self._clock = clock or SystemClock()
        self._publisher = Publisher(settings)
        self._polls = (
            _Poll(settings.cfi_poll_interval, self._read_cfi),
            _Poll(settings.shi_poll_interval, self._read_shi),
        )

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
        for poll in self._polls:
            payloads = poll.run_if_due(now)
            if payloads is not None:
                self._publisher.publish_changes(payloads)
        now = self._clock.monotonic()
        return max(min(poll.due for poll in self._polls) - now, 0.0)

    def _read_cfi(self) -> Payloads | None:
        try:
            calculations = self._controller.read_calculations()
        except Unreachable as error:
            LOGGER.warning("%s", error)
            return None
        return _payloads("cfi/calculations", calculations)

    def _read_shi(self) -> Payloads | None:
        try:
            inputs = self._controller.read_inputs()
            holdings = self._controller.read_holdings()
        except Unreachable as error:
            LOGGER.warning("%s", error)
            return None
        return _payloads("shi/inputs", inputs) | _payloads("shi/holdings", holdings)


def _payloads(vector_path: str, vector: Any) -> Payloads:
    """The payload of each selected field in this vector."""
    payloads = {}
    for _, field in vector.items():
        path = f"{vector_path}/{field.name}"
        if selected(path):
            payloads[path] = payload(field)
    return payloads
