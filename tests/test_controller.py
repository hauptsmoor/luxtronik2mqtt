"""The Controller adapter against network peers on localhost."""

import time

import pytest

import fixtures
from luxtronik2mqtt.controller import Controller, Dump, Unreachable
from peers import closed_port, silent_port, simulated_controller

TIMEOUT = 0.5


def test_reads_calculations_from_the_cfi() -> None:
    calculations = [0] * 260
    calculations[10] = 383  # ID_WEB_Temperatur_TVL, in tenths of a degree
    dump = Dump(cfi={"parameters": [], "calculations": calculations, "visibilities": []}, shi=None)

    with simulated_controller(dump) as simulated:
        controller = simulated.controller()

        assert controller.read_calculations().get("ID_WEB_Temperatur_TVL").value == 38.3


def test_reports_the_firmware_version() -> None:
    with simulated_controller(fixtures.load()) as simulated:
        assert simulated.controller().firmware_version() == "V3.92.1"


def test_dump_holds_the_cfi_registers_as_sent_and_no_shi_when_it_doesnt_answer() -> None:
    dump = Dump(
        cfi={"parameters": [1, -2, 3], "calculations": list(range(260)), "visibilities": [0, 1, -1]},
        shi=None,
    )

    with simulated_controller(dump) as simulated:
        assert simulated.controller().read_dump() == dump


def test_dump_of_a_real_controller_holds_every_register_as_sent() -> None:
    dump = fixtures.load()

    with simulated_controller(dump) as simulated:
        assert simulated.controller().read_dump() == dump


def test_cfi_on_a_closed_port_is_unreachable() -> None:
    controller = Controller("127.0.0.1", cfi_port=closed_port(), shi_port=closed_port())

    with pytest.raises(Unreachable) as raised:
        controller.read_calculations()

    assert raised.value.interface == "CFI"


def test_cfi_that_never_answers_is_unreachable_within_the_timeout() -> None:
    with silent_port() as port:
        controller = Controller("127.0.0.1", cfi_port=port, shi_port=closed_port(), timeout=TIMEOUT)
        started = time.monotonic()

        with pytest.raises(Unreachable) as raised:
            controller.read_calculations()

    assert raised.value.interface == "CFI"
    assert time.monotonic() - started < 2 * TIMEOUT


def test_a_host_name_that_doesnt_resolve_is_unreachable_on_both_interfaces() -> None:
    controller = Controller("controller.invalid")

    with pytest.raises(Unreachable) as cfi:
        controller.read_calculations()
    with pytest.raises(Unreachable) as shi:
        controller.read_inputs()

    assert (cfi.value.interface, shi.value.interface) == ("CFI", "SHI")


def test_shi_on_a_closed_port_is_unreachable() -> None:
    controller = Controller("127.0.0.1", cfi_port=closed_port(), shi_port=closed_port())

    with pytest.raises(Unreachable) as raised:
        controller.read_inputs()

    assert raised.value.interface == "SHI"


def test_shi_that_never_answers_is_unreachable_within_the_timeout() -> None:
    with silent_port() as port:
        controller = Controller("127.0.0.1", cfi_port=closed_port(), shi_port=port, timeout=TIMEOUT)
        started = time.monotonic()

        with pytest.raises(Unreachable) as raised:
            controller.read_holdings()

    assert raised.value.interface == "SHI"
    assert time.monotonic() - started < 2 * TIMEOUT
