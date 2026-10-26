"""The Bridge: polls the Controller on a schedule and publishes its values."""

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

from luxtronik2mqtt.config import Settings
from luxtronik2mqtt.controller import Unreachable
from luxtronik2mqtt.formatting import payload
from luxtronik2mqtt.publishing import Publisher
from luxtronik2mqtt.selection import Selection

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

    def read_parameters(self) -> Any: ...

    def read_visibilities(self) -> Any: ...

    def read_inputs(self) -> Any: ...

    def read_holdings(self) -> Any: ...


class _Job:
    """Something the Bridge does on an interval, a poll or the republish, and when it is next due."""

    def __init__(self, interval: float, run: Callable[[], None], first_after: float = 0.0) -> None:
        self.interval = interval
        self.run = run
        self.due = float("-inf")
        # Counted from the first `run_pending`, so every job keeps the same time base.
        self._first_after: float | None = first_after

    def run_if_due(self, now: float) -> None:
        """Run if due now, and work out when it is next due."""
        if self._first_after is not None:
            self.due, self._first_after = now + self._first_after, None
        if now < self.due:
            return
        due = self.due + self.interval
        # After a run that was late, or the first one, keep the interval from now instead of catching up.
        self.due = due if due > now else now + self.interval
        self.run()


class Bridge:
    """Polls the CFI and the SHI, each on its own interval, and publishes the selected values that changed.

    On the republish interval it publishes every value again, changed or not.

    Time comes from the clock, so tests drive the schedule with `run_pending`.
    """

    def __init__(self, settings: Settings, controller: ControllerReader, clock: Clock | None = None) -> None:
        self._settings = settings
        self._controller = controller
        self._clock = clock or SystemClock()
        self._publisher = Publisher(settings)
        self._selection = Selection(settings.include, settings.exclude)
        # A CFI vector is read only when the defaults or an include can select some of its values,
        # so Parameters and Visibilities are left alone unless included.
        cfi_vectors = (
            ("cfi/calculations", controller.read_calculations),
            ("cfi/parameters", controller.read_parameters),
            ("cfi/visibilities", controller.read_visibilities),
        )
        self._cfi_vectors = [(path, read) for path, read in cfi_vectors if self._selection.reaches(path)]
        # Paths published in the current `run_pending`, so a republish due at the same time doesn't repeat them.
        self._just_published: set[str] = set()
        # Interfaces whose last poll found them unreachable: their last values are stale, so not republished.
        self._unreachable: set[str] = set()
        self._polls = (
            _Job(settings.cfi_poll_interval, lambda: self._publish_changes(self._read_cfi())),
            _Job(settings.shi_poll_interval, lambda: self._publish_changes(self._read_shi())),
        )
        self._republish = _Job(
            settings.republish_interval, self._republish_fresh, first_after=settings.republish_interval
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
        """Run every poll, and the republish, that is due now. Returns the seconds until the next one is due."""
        now = self._clock.monotonic()
        self._just_published.clear()
        for poll in self._polls:
            poll.run_if_due(now)
        # After the polls, so it republishes what they just read.
        self._republish.run_if_due(now)
        now = self._clock.monotonic()
        return max(min(job.due for job in (*self._polls, self._republish)) - now, 0.0)

    def _publish_changes(self, payloads: Payloads | None) -> None:
        """Publish what a poll read, if its interface answered."""
        if payloads is not None:
            self._just_published |= self._publisher.publish_changes(payloads)

    def _republish_fresh(self) -> None:
        """Republish every value, except those a poll just published and those of an unreachable interface."""
        self._publisher.republish(
            lambda path: path not in self._just_published and path.split("/", 1)[0] not in self._unreachable
        )

    def _read_cfi(self) -> Payloads | None:
        payloads: Payloads = {}
        try:
            for vector_path, read in self._cfi_vectors:
                payloads |= self._payloads(vector_path, read())
        except Unreachable as error:
            LOGGER.warning("%s", error)
            self._unreachable.add("cfi")
            return None
        self._unreachable.discard("cfi")
        return payloads

    def _read_shi(self) -> Payloads | None:
        try:
            inputs = self._controller.read_inputs()
            holdings = self._controller.read_holdings()
        except Unreachable as error:
            LOGGER.warning("%s", error)
            self._unreachable.add("shi")
            return None
        self._unreachable.discard("shi")
        return self._payloads("shi/inputs", inputs) | self._payloads("shi/holdings", holdings)

    def _payloads(self, vector_path: str, vector: Any) -> Payloads:
        """The payload of each selected field in this vector."""
        payloads = {}
        for _, field in vector.items():
            path = f"{vector_path}/{field.name}"
            if self._selection.selected(path):
                payloads[path] = payload(field)
        return payloads
