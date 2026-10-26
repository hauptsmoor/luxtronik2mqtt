"""The fake Controller that stands in for the Controller adapter in tests."""

from collections.abc import Callable
from typing import Any

import fixtures
import pytest
from fake_controller import FakeController
from peers import simulated_controller

from luxtronik2mqtt.controller import Unreachable

READS = ["read_parameters", "read_calculations", "read_visibilities", "read_inputs", "read_holdings"]


def values(vector: Any) -> dict[str, object]:
    return {definition.name: field.value for definition, field in vector.data.items()}


def test_reads_the_values_of_the_fixture() -> None:
    fake = FakeController.from_fixture()

    assert fake.read_calculations().get("ID_WEB_Temperatur_TVL").value == 29.2
    assert fake.read_holdings().get("hot_water_setpoint").value == 40.0
    assert fake.firmware_version() == "V3.92.1"


def test_a_test_can_change_values_between_reads() -> None:
    fake = FakeController.from_fixture()

    fake.set("calculations", "ID_WEB_Temperatur_TVL", 38.3)
    fake.set("holdings", "hot_water_setpoint", 45.0)

    assert fake.read_calculations().get("ID_WEB_Temperatur_TVL").value == 38.3
    assert fake.read_holdings().get("hot_water_setpoint").value == 45.0


def test_changing_a_value_packed_into_a_shared_register_keeps_the_others() -> None:
    fake = FakeController.from_fixture()

    fake.set("inputs", "heatpump_zwe1_status", True)
    fake.set("inputs", "heatpump_vd2_status", True)
    fake.set("inputs", "heatpump_vd2_status", False)

    inputs = fake.read_inputs()
    assert inputs.get("heatpump_zwe1_status").value is True
    assert inputs.get("heatpump_vd2_status").value is False


def assert_unreachable(interface: str, read: Callable[[], object]) -> None:
    with pytest.raises(Unreachable) as raised:
        read()
    assert raised.value.interface == interface


def test_the_cfi_can_be_made_unreachable_and_reachable_again() -> None:
    fake = FakeController.from_fixture()

    fake.cfi_reachable = False

    for read in (fake.read_parameters, fake.read_calculations, fake.read_visibilities, fake.firmware_version):
        assert_unreachable("CFI", read)
    assert fake.read_holdings().get("hot_water_setpoint").value == 40.0

    fake.cfi_reachable = True

    assert fake.read_calculations().get("ID_WEB_Temperatur_TVL").value == 29.2


def test_the_shi_can_be_made_unreachable_and_reachable_again() -> None:
    fake = FakeController.from_fixture()

    fake.shi_reachable = False

    for read in (fake.read_inputs, fake.read_holdings):
        assert_unreachable("SHI", read)
    assert fake.read_calculations().get("ID_WEB_Temperatur_TVL").value == 29.2

    fake.shi_reachable = True

    assert fake.read_holdings().get("hot_water_setpoint").value == 40.0


def test_a_dump_without_shi_registers_has_an_unreachable_shi() -> None:
    dump = fixtures.load()
    dump.shi = None

    assert_unreachable("SHI", FakeController(dump).read_inputs)


def test_reads_what_the_controller_adapter_reads_from_the_same_controller() -> None:
    dump = fixtures.load()
    fake = FakeController(dump)

    with simulated_controller(dump) as simulated:
        controller = simulated.controller()

        for read in READS:
            assert values(getattr(fake, read)()) == values(getattr(controller, read)()), read


def test_a_holding_write_is_accepted_and_read_back_by_default() -> None:
    fake = FakeController.from_fixture()

    written = fake.write_holding("hot_water_setpoint", "45")

    assert fake.writes == [("hot_water_setpoint", "45")]
    assert (written.accepted, written.requested.value, written.read_back.value) == (True, 45.0, 45.0)
    assert fake.read_holdings().get("hot_water_setpoint").value == 45.0


def test_a_holding_write_can_be_refused() -> None:
    fake = FakeController.from_fixture()
    fake.refuse_writes = True

    written = fake.write_holding("hot_water_setpoint", "45")

    assert (written.accepted, written.read_back.value) == (False, 40.0)
    assert fake.read_holdings().get("hot_water_setpoint").value == 40.0


def test_a_holding_write_can_apply_a_different_value() -> None:
    fake = FakeController.from_fixture()
    fake.applies_instead = 42.0

    written = fake.write_holding("hot_water_setpoint", "45")

    assert (written.accepted, written.requested.value, written.read_back.value) == (True, 45.0, 42.0)


def test_a_holding_write_the_library_cant_convert_or_to_an_unreachable_shi_isnt_received() -> None:
    fake = FakeController.from_fixture()

    with pytest.raises(ValueError):
        fake.write_holding("hot_water_setpoint", "warm")
    fake.shi_reachable = False
    assert_unreachable("SHI", lambda: fake.write_holding("hot_water_setpoint", "45"))

    assert fake.writes == []
