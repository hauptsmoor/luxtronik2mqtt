"""Controller adapter: the only module that imports python-luxtronik (ADR 0002)."""

import json
import socket
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from luxtronik.cfi import (
    LUXTRONIK_DEFAULT_PORT,
    Calculations,
    LuxtronikSocketInterface,
    Parameters,
    Visibilities,
)
from luxtronik.cfi.constants import LUXTRONIK_CFI_REGISTER_BIT_SIZE
from luxtronik.collections import get_data_arr
from luxtronik.datatypes import IPv4Address
from luxtronik.shi import (
    LUXTRONIK_DEFAULT_MODBUS_PORT,
    Holdings,
    Inputs,
    LuxtronikModbusTcpInterface,
    LuxtronikSmartHomeInterface,
    resolve_version,
)
from luxtronik.shi.common import LuxtronikSmartHomeReadHoldingsTelegram
from luxtronik.shi.constants import LUXTRONIK_SHI_REGISTER_BIT_SIZE
from pyModbusTCP.constants import MB_EXCEPT_ERR, MB_NO_ERR

DEFAULT_CFI_PORT: int = LUXTRONIK_DEFAULT_PORT
DEFAULT_SHI_PORT: int = LUXTRONIK_DEFAULT_MODBUS_PORT
DEFAULT_TIMEOUT = 5.0

_Vector = TypeVar("_Vector")


@dataclass
class Dump:
    """The raw registers of every CFI and SHI vector, as one Controller sent them.

    `cfi` maps each CFI vector to its registers from index 0. `shi` maps each SHI
    vector to its registers by Modbus address, and is None when the SHI didn't answer.
    """

    cfi: dict[str, list[int]]
    shi: dict[str, dict[int, int]] | None

    def decode(self, vector: str) -> Any:
        """The library data vector built from these registers, as a read from the Controller builds it."""
        if vector in _CFI_VECTORS:
            decoded = _CFI_VECTORS[vector]()
            _cfi_parser._parse(decoded, self.cfi[vector])
            return decoded
        modbus = _Modbus("dump", DEFAULT_SHI_PORT, DEFAULT_TIMEOUT, client=_DumpedRegisters(self._shi_registers()))
        data = LuxtronikSmartHomeInterface(modbus, resolve_version(modbus)).read_data()
        return {"inputs": data.inputs, "holdings": data.holdings}[vector]

    def firmware_version(self) -> str:
        version: str = self.decode("calculations").get_firmware_version()
        return version

    def set(self, vector: str, name: str, value: object) -> None:
        """Set one field to a value, written into the registers the way the library encodes it.

        None on a SHI field removes its registers, so the SHI answers a read of them
        with a Modbus exception, as for a field this installation doesn't have.
        """
        if value is None and vector in _SHI_VECTORS:
            definition = _definition(_SHI_VECTORS[vector], name)
            for address in range(definition.addr, definition.addr + definition.count):
                self._shi_registers()[vector].pop(address, None)
            return
        if vector in _CFI_VECTORS:
            definition, registers = _encode(_CFI_VECTORS[vector], name, value, LUXTRONIK_CFI_REGISTER_BIT_SIZE)
            self.cfi[vector][definition.index : definition.index + definition.count] = registers
            return
        definition, registers = _encode(_SHI_VECTORS[vector], name, value, LUXTRONIK_SHI_REGISTER_BIT_SIZE)
        shi = self._shi_registers()[vector]
        if definition.bit_offset is not None:
            # Several fields share this register; change only this field's bits.
            mask = ((1 << definition.num_bits) - 1) << definition.bit_offset
            registers = [(shi[definition.addr] & ~mask) | ((registers[0] << definition.bit_offset) & mask)]
        for offset, register in enumerate(registers):
            shi[definition.addr + offset] = register

    def replace_address(self, address: str, replacement: str) -> None:
        """Replace an IPv4 address in every Parameter and Calculation register that holds it."""
        old, new = IPv4Address.to_heatpump(address), IPv4Address.to_heatpump(replacement)
        for vector in ("parameters", "calculations"):
            self.cfi[vector] = [new if register == old else register for register in self.cfi[vector]]

    def to_json(self) -> str:
        shi = None
        if self.shi is not None:
            shi = {vector: {str(a): r for a, r in sorted(registers.items())} for vector, registers in self.shi.items()}
        return json.dumps({"cfi": self.cfi, "shi": shi}, indent=2) + "\n"

    @classmethod
    def from_json(cls, text: str) -> "Dump":
        document = json.loads(text)
        shi = document["shi"]
        if shi is not None:
            shi = {vector: {int(a): r for a, r in registers.items()} for vector, registers in shi.items()}
        return cls(cfi=document["cfi"], shi=shi)

    def _shi_registers(self) -> dict[str, dict[int, int]]:
        if self.shi is None:
            raise ValueError("this dump has no SHI registers")
        return self.shi


_CFI_VECTORS = {"parameters": Parameters, "calculations": Calculations, "visibilities": Visibilities}
_SHI_VECTORS = {"inputs": Inputs, "holdings": Holdings}

# The library parses CFI registers on its socket interface. This one never connects.
_cfi_parser = LuxtronikSocketInterface("dump")


def _definition(vector_type: Any, name: str) -> Any:
    definition = vector_type.definitions.get(name)
    if definition is None:
        raise KeyError(f"{vector_type.__name__} have no field {name}")
    return definition


def _encode(vector_type: Any, name: str, value: object, register_bits: int) -> tuple[Any, list[int]]:
    definition = _definition(vector_type, name)
    field = definition.create_field()
    field.value = value
    registers = get_data_arr(definition, field, register_bits)
    if registers is None:
        raise ValueError(f"{value!r} isn't a valid value for {name}")
    return definition, registers


class Unreachable(Exception):
    """The Controller didn't answer on the CFI or the SHI."""

    def __init__(self, interface: str, address: str, reason: object) -> None:
        super().__init__(f"{interface} at {address} is unreachable: {reason}")
        self.interface = interface


class _Cfi(LuxtronikSocketInterface):  # type: ignore[misc]
    """The library's CFI interface, with a timeout, and raising when the Controller doesn't answer.

    The library connects without a timeout and logs connection errors and returns
    None. Everything else, including the CFI protocol, stays the library's.
    """

    def __init__(self, host: str, port: int, timeout: float) -> None:
        super().__init__(host, port)
        self._timeout = timeout
        self._socket: socket.socket | None = None
        # The registers of the last vector read, for dumps.
        self.registers: list[int] = []

    def _parse(self, data_vector: Any, raw_data: list[int]) -> None:
        self.registers = list(raw_data)
        super()._parse(data_vector, raw_data)

    def _with_lock_and_connect(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self.lock:
            try:
                with socket.create_connection((self._host, self._port), timeout=self._timeout) as sock:
                    self._socket = sock
                    return func(*args, **kwargs)
            except OSError as error:
                raise Unreachable("CFI", f"{self._host}:{self._port}", error) from error
            finally:
                self._socket = None


class _Modbus(LuxtronikModbusTcpInterface):  # type: ignore[misc]
    """The library's Modbus TCP layer, noting whether the SHI answered.

    The library logs a failed connection or read and carries on, which leaves the
    fields without a value, so the SHI interface above it can't tell an unreachable
    SHI from fields this installation doesn't have. A Modbus exception is an answer.
    """

    def __init__(self, host: str, port: int, timeout: float, client: Any = None) -> None:
        super().__init__(host, port, timeout)
        if client is not None:
            self._client = client
        self.failure: str | None = None
        self.forget_registers()

    def forget_registers(self) -> None:
        # Every register read since, by SHI vector and address, for dumps.
        self.registers: dict[str, dict[int, int]] = {vector: {} for vector in _SHI_VECTORS}

    def raise_if_failed(self) -> None:
        if self.failure is not None:
            raise Unreachable("SHI", f"{self._host}:{self._port}", self.failure)

    def _connect(self) -> bool:
        try:
            connected: bool = super()._connect()
        except OSError as error:  # pyModbusTCP lets a failed name lookup through
            self.failure = str(error)
            return False
        if not connected:
            self.failure = self._client.last_error_as_txt
        return connected

    def _read_register(self, read_reg_cb: Callable[..., Any], telegram: Any) -> bool:
        valid: bool = super()._read_register(read_reg_cb, telegram)
        if valid:
            vector = "holdings" if isinstance(telegram, LuxtronikSmartHomeReadHoldingsTelegram) else "inputs"
            self.registers[vector].update(zip(range(telegram.addr, telegram.addr + telegram.count), telegram.data))
        elif self._client.last_error != MB_EXCEPT_ERR:
            self.failure = self._client.last_error_as_txt
        return valid


class _DumpedRegisters:
    """Stands in for pyModbusTCP's client, answering reads from a dump's registers.

    A register the dump doesn't have gets a Modbus exception, as from the SHI.
    """

    def __init__(self, registers: dict[str, dict[int, int]]) -> None:
        self._registers = registers
        self.is_open = False
        self.last_error = MB_NO_ERR
        self.last_error_as_txt = "no error"

    def open(self) -> bool:
        self.is_open = True
        return True

    def close(self) -> None:
        self.is_open = False

    def read_input_registers(self, address: int, count: int) -> list[int] | None:
        return self._read("inputs", address, count)

    def read_holding_registers(self, address: int, count: int) -> list[int] | None:
        return self._read("holdings", address, count)

    def _read(self, vector: str, address: int, count: int) -> list[int] | None:
        try:
            data = [self._registers[vector][a] for a in range(address, address + count)]
        except KeyError:
            self.last_error, self.last_error_as_txt = MB_EXCEPT_ERR, "modbus exception"
            return None
        self.last_error, self.last_error_as_txt = MB_NO_ERR, "no error"
        return data


class Controller:
    """One Controller, read through the CFI and the SHI.

    Every read either returns library data vectors or raises Unreachable. The
    timeout, in seconds, bounds each connect and each wait for an answer. Reads are
    serialised through the library's per-host lock, which the CFI and the SHI share.
    """

    def __init__(
        self,
        host: str,
        cfi_port: int = DEFAULT_CFI_PORT,
        shi_port: int = DEFAULT_SHI_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._cfi = _Cfi(host, cfi_port, timeout)
        self._modbus = _Modbus(host, shi_port, timeout)
        # Created once the SHI has answered, so a SHI switched on later gets the right version.
        self._shi: LuxtronikSmartHomeInterface | None = None

    def read_calculations(self) -> Calculations:
        return self._cfi.read_calculations()

    def read_parameters(self) -> Parameters:
        return self._cfi.read_parameters()

    def read_visibilities(self) -> Visibilities:
        return self._cfi.read_visibilities()

    def read_inputs(self) -> Inputs:
        return self._read_shi(lambda shi: shi.read_inputs())

    def read_holdings(self) -> Holdings:
        return self._read_shi(lambda shi: shi.read_holdings())

    def firmware_version(self) -> str:
        """The firmware version as the Controller shows it, for example `V3.92.1`. Reads the CFI."""
        version: str = self.read_calculations().get_firmware_version()
        return version

    def read_dump(self) -> Dump:
        """Read every CFI and SHI vector, keeping the registers exactly as the Controller sent them.

        Raises Unreachable if the CFI doesn't answer. A SHI that doesn't answer leaves `shi` None.
        """
        with self._cfi.lock:
            cfi = {}
            for vector, read in (
                ("parameters", self.read_parameters),
                ("calculations", self.read_calculations),
                ("visibilities", self.read_visibilities),
            ):
                read()
                cfi[vector] = self._cfi.registers
            self._modbus.forget_registers()
            try:
                self.read_inputs()
                self.read_holdings()
            except Unreachable:
                return Dump(cfi, None)
            return Dump(cfi, self._modbus.registers)

    def _read_shi(self, read: Callable[[LuxtronikSmartHomeInterface], _Vector]) -> _Vector:
        with self._modbus.lock:
            self._modbus.failure = None
            if self._shi is None:
                version = resolve_version(self._modbus)
                self._modbus.raise_if_failed()
                self._shi = LuxtronikSmartHomeInterface(self._modbus, version)
            vector = read(self._shi)
            self._modbus.raise_if_failed()
            return vector
