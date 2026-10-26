"""A fake Controller that stands in for the Controller adapter in tests."""

import copy
from pathlib import Path
from typing import Any

import fixtures

from luxtronik2mqtt.controller import Dump, HoldingWrite, Unreachable, holding_to_write


class FakeController:
    """Answers like the Controller adapter, from a dump of a real Controller.

    Reads build real library data vectors from the dump's registers, so the
    library's own conversions run in tests. A test changes values with `set` and
    takes an interface away with `cfi_reachable` or `shi_reachable`. `attempts`
    counts the reads and writes tried on each interface, answered or not.

    Holding writes are accepted by default. A test makes the Controller refuse them
    with `refuse_writes`, or apply a different value with `applies_instead`. `writes`
    holds each write received, as (name, value).
    """

    def __init__(self, dump: Dump) -> None:
        self.dump = copy.deepcopy(dump)
        self.cfi_reachable = True
        self.shi_reachable = dump.shi is not None
        self.attempts = {"CFI": 0, "SHI": 0}
        self.writes: list[tuple[str, object]] = []
        self.refuse_writes = False
        self.applies_instead: object | None = None

    @classmethod
    def from_fixture(cls, path: Path = fixtures.V3_92_1) -> "FakeController":
        return cls(fixtures.load(path))

    def read_calculations(self) -> Any:
        return self._read("CFI", "calculations")

    def read_parameters(self) -> Any:
        return self._read("CFI", "parameters")

    def read_visibilities(self) -> Any:
        return self._read("CFI", "visibilities")

    def read_inputs(self) -> Any:
        return self._read("SHI", "inputs")

    def read_holdings(self) -> Any:
        return self._read("SHI", "holdings")

    def write_holding(self, name: str, value: object) -> HoldingWrite:
        self._require("SHI")
        requested = holding_to_write(name, value)
        self.writes.append((name, value))
        if not self.refuse_writes:
            self.set("holdings", name, requested.value if self.applies_instead is None else self.applies_instead)
        read_back = self.dump.decode("holdings").get(name)
        return HoldingWrite(requested, read_back, accepted=not self.refuse_writes)

    def firmware_version(self) -> str:
        self._require("CFI")
        return self.dump.firmware_version()

    def set(self, vector: str, name: str, value: object) -> None:
        """Change a value on the Controller, for example `set("calculations", "ID_WEB_Temperatur_TVL", 38.3)`."""
        self.dump.set(vector, name, value)

    def _read(self, interface: str, vector: str) -> Any:
        self._require(interface)
        return self.dump.decode(vector)

    def _require(self, interface: str) -> None:
        self.attempts[interface] += 1
        reachable = self.cfi_reachable if interface == "CFI" else self.shi_reachable
        if not reachable:
            raise Unreachable(interface, "the fake Controller", "made unreachable by the test")
