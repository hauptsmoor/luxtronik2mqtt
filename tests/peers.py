"""Network peers for testing the Controller adapter without a Controller."""

import copy
import socket
import socketserver
import struct
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

from pyModbusTCP.server import DataBank, ModbusServer

from luxtronik2mqtt.controller import Controller, Dump

# The CFI's read commands; the Controller answers anything else by closing the connection here.
_CFI_PARAMETERS = 3003
_CFI_CALCULATIONS = 3004
_CFI_VISIBILITIES = 3005


def closed_port() -> int:
    """A localhost port that nothing listens on."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
    return port


@contextmanager
def silent_port() -> Iterator[int]:
    """A localhost port that accepts connections and never answers."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(8)
        yield sock.getsockname()[1]


@dataclass
class SimulatedController:
    cfi_port: int
    shi_port: int
    # Every write anyone attempted. Unless it accepts writes, the simulated Controller refuses them all.
    writes: list[str] = field(default_factory=list)

    def controller(self) -> Controller:
        return Controller("127.0.0.1", cfi_port=self.cfi_port, shi_port=self.shi_port)


@contextmanager
def simulated_controller(dump: Dump, accept_writes: bool = False) -> Iterator[SimulatedController]:
    """A Controller on localhost that serves the dump's registers.

    Without SHI registers in the dump, the SHI port is closed. With `accept_writes`,
    the SHI stores what is written to Holdings it has; otherwise it refuses every write.
    """
    writes: list[str] = []
    with _cfi_server(dump.cfi, writes) as cfi_port:
        if dump.shi is None:
            yield SimulatedController(cfi_port, closed_port(), writes)
        else:
            with _shi_server(dump.shi, writes, accept_writes) as shi_port:
                yield SimulatedController(cfi_port, shi_port, writes)


@contextmanager
def _cfi_server(registers: dict[str, list[int]], writes: list[str]) -> Iterator[int]:
    class Handler(socketserver.BaseRequestHandler):
        def handle(self) -> None:
            while request := self._receive(8):
                command, _ = struct.unpack(">ii", request)
                if command not in (_CFI_PARAMETERS, _CFI_CALCULATIONS, _CFI_VISIBILITIES):
                    writes.append(f"CFI command {command}")
                    return
                self.request.sendall(_cfi_answer(command, registers))

        def _receive(self, size: int) -> bytes:
            data = b""
            while len(data) < size:
                chunk = self.request.recv(size - len(data))
                if not chunk:
                    return b""
                data += chunk
            return data

    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()


def _cfi_answer(command: int, registers: dict[str, list[int]]) -> bytes:
    if command == _CFI_PARAMETERS:
        values = registers["parameters"]
        return struct.pack(f">ii{len(values)}i", command, len(values), *values)
    if command == _CFI_CALCULATIONS:
        values = registers["calculations"]
        return struct.pack(f">iii{len(values)}i", command, 0, len(values), *values)
    values = registers["visibilities"]
    return struct.pack(f">ii{len(values)}b", command, len(values), *values)


class _Registers(DataBank):  # type: ignore[misc]
    """SHI registers; reading or writing one the dump doesn't have gets a Modbus exception."""

    def __init__(self, registers: dict[str, dict[int, int]], writes: list[str], accept_writes: bool) -> None:
        super().__init__()
        self._registers = registers
        self._writes = writes
        self._accept_writes = accept_writes

    def get_input_registers(self, address: int, number: int = 1, srv_info: Any = None) -> list[int] | None:
        return self._get("inputs", address, number)

    def get_holding_registers(self, address: int, number: int = 1, srv_info: Any = None) -> list[int] | None:
        return self._get("holdings", address, number)

    def set_holding_registers(self, address: int, word_list: list[int], srv_info: Any = None) -> bool | None:
        self._writes.append(f"SHI holdings {address}: {word_list}")
        addresses = range(address, address + len(word_list))
        if not self._accept_writes or any(a not in self._registers["holdings"] for a in addresses):
            return None
        self._registers["holdings"].update(zip(addresses, word_list))
        return True

    def set_coils(self, address: int, bit_list: list[bool], srv_info: Any = None) -> None:
        self._writes.append(f"SHI coils {address}: {bit_list}")

    def _get(self, vector: str, address: int, number: int) -> list[int] | None:
        try:
            return [self._registers[vector][a] for a in range(address, address + number)]
        except KeyError:
            return None


@contextmanager
def _shi_server(registers: dict[str, dict[int, int]], writes: list[str], accept_writes: bool) -> Iterator[int]:
    data_bank = _Registers(copy.deepcopy(registers), writes, accept_writes)
    server = ModbusServer("127.0.0.1", 0, no_block=True, data_bank=data_bank)
    server.start()
    try:
        yield server._service.server_address[1]
    finally:
        server.stop()
