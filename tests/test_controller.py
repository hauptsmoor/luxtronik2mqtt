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


def test_writes_a_holding_and_returns_the_value_read_back() -> None:
    with simulated_controller(fixtures.load(), accept_writes=True) as simulated:
        written = simulated.controller().write_holding("hot_water_setpoint", "45")

    assert simulated.writes == ["SHI holdings 10006: [450]"]
    assert written.accepted
    assert written.requested.value == 45.0
    assert written.read_back.value == 45.0


def test_a_refused_write_still_returns_the_value_read_back() -> None:
    with simulated_controller(fixtures.load(), accept_writes=False) as simulated:
        written = simulated.controller().write_holding("hot_water_mode", "Setpoint")

    assert simulated.writes == ["SHI holdings 10005: [1]"]
    assert not written.accepted
    assert written.requested.value == "Setpoint"
    assert written.read_back.value == "Off"


def test_a_value_the_library_cant_convert_is_refused_before_anything_is_sent() -> None:
    with simulated_controller(fixtures.load(), accept_writes=True) as simulated:
        with pytest.raises(ValueError):
            simulated.controller().write_holding("hot_water_setpoint", "warm")
        with pytest.raises(ValueError):
            simulated.controller().write_holding("heating_mode", "Sometimes")

    assert simulated.writes == []


def test_a_write_to_an_unreachable_shi_raises_unreachable() -> None:
    controller = Controller("127.0.0.1", cfi_port=closed_port(), shi_port=closed_port())

    with pytest.raises(Unreachable) as raised:
        controller.write_holding("hot_water_setpoint", "45")

    assert raised.value.interface == "SHI"


def test_a_negative_value_is_written_as_the_register_holds_it() -> None:
    with simulated_controller(fixtures.load(), accept_writes=True) as simulated:
        written = simulated.controller().write_holding("heating_offset", "-2")

    assert simulated.writes == ["SHI holdings 10002: [65516]"]
    assert (written.accepted, written.requested.value, written.read_back.value) == (True, -2.0, -2.0)


@pytest.mark.parametrize(("name", "value"), [("hot_water_setpoint", "-5"), ("hot_water_setpoint", "7000"), ("heating_offset", "4000")])
def test_a_value_that_doesnt_fit_the_register_is_refused_before_anything_is_sent(name: str, value: str) -> None:
    with simulated_controller(fixtures.load(), accept_writes=True) as simulated:
        with pytest.raises(ValueError):
            simulated.controller().write_holding(name, value)

    assert simulated.writes == []
