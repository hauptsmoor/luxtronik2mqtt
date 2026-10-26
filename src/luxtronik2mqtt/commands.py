"""Commands: set SHI Holdings on request over MQTT, checked, written and read back (ADR 0001)."""

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

from luxtronik2mqtt.config import Settings
from luxtronik2mqtt.controller import Unreachable
from luxtronik2mqtt.formatting import payload
from luxtronik2mqtt.publishing import Publisher, Received

LOGGER = logging.getLogger(__name__)

# Topic paths after the prefix: a Command for a Holding, and the error it may get.
SET = "shi/holdings/+/set"
ERROR = "shi/holdings/{name}/error"


class HoldingWriter(Protocol):
    def write_holding(self, name: str, value: object) -> Any: ...


class Commands:
    """Takes each Command from `shi/holdings/<name>/set` and runs it, one at a time, in a thread of its own.

    A Command that breaks a rule, or that doesn't take effect, gets a short error on
    `shi/holdings/<name>/error`. A Command is never retried.

    Under MQTT 3.1.1 the broker marks a message retained only when it sends it because
    the Bridge (re)subscribed, so that is the retained Command rejected: one left at the
    broker from earlier.
    """

    def __init__(
        self,
        settings: Settings,
        controller: HoldingWriter,
        publisher: Publisher,
        shi_lock: threading.Lock,
        holdings: Callable[[], Any],
        publish_holding: Callable[[Any], None],
    ) -> None:
        """`shi_lock` is held while a Command runs, so no SHI poll publishes in between.
        `holdings` returns the Holdings the last SHI poll read, or None while the SHI isn't answering.
        `publish_holding` publishes a Holding field read back from the Controller.
        """
        self._settings = settings
        self._controller = controller
        self._publisher = publisher
        self._shi_lock = shi_lock
        self._holdings = holdings
        self._publish_holding = publish_holding
        self._queue: queue.Queue[Received | None] = queue.Queue()
        self._thread = threading.Thread(target=self._run, name="commands", daemon=True)
        publisher.subscribe(SET, self._queue.put)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        """Run the Commands already received, then stop."""
        self._queue.put(None)
        self._thread.join()

    def _run(self) -> None:
        while (command := self._queue.get()) is not None:
            try:
                self._handle(command)
            except Exception:
                # The next Command still runs.
                LOGGER.exception("Command for %s failed", command.path)

    def _handle(self, command: Received) -> None:
        name = command.path.split("/")[2]
        # An empty message is how a client clears a retained Command at the broker, not a Command.
        if not command.payload:
            return
        # A retained Command could be one left at the broker long ago, run again by every (re)connect.
        if command.retained:
            self._error(name, "rejected: a retained Command isn't run")
            return
        if not self._settings.shi_write:
            self._error(name, "rejected: Commands are switched off (LUX_SHI_WRITE)")
            return
        with self._shi_lock:
            holdings = self._holdings()
            if holdings is None:
                self._error(name, "rejected: the SHI is unreachable")
                return
            # Only by its canonical name, the one it's published under.
            try:
                field = holdings.get(name)
            except KeyError:  # the library's answer for a name it has retired
                field = None
            if field is None or field.name != name or not field.writeable:
                self._error(name, f"rejected: {name} isn't a writable Holding")
                return
            if field.value is None:
                self._error(name, f"rejected: {name} has no value on this Controller")
                return
            try:
                written = self._controller.write_holding(name, command.payload)
            except ValueError as error:
                self._error(name, f"rejected: {error}")
                return
            except Unreachable:
                self._error(name, "failed: the SHI is unreachable")
                return
            self._publish_holding(written.read_back)
        requested, read_back = payload(written.requested), payload(written.read_back)
        if not written.accepted:
            self._error(name, "failed: the Controller refused the write")
        elif read_back != requested:
            self._error(name, f"failed: the Controller applied {read_back} instead of {requested}")
        else:
            LOGGER.info("Command for %s applied %s", name, read_back)

    def _error(self, name: str, reason: str) -> None:
        LOGGER.info("Command for %s %s", name, reason)
        self._publisher.publish_once(ERROR.format(name=name), reason)
