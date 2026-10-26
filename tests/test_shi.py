"""The Bridge as a subscriber sees it: SHI Inputs and Holdings from the fake Controller on a real broker."""

from collections.abc import Iterator

import pytest
from fake_controller import FakeController
from harness import FakeClock, Message, Subscriber, broker, env, retained, running_bridge

INPUTS = "luxtronik/shi/inputs/"
HOLDINGS = "luxtronik/shi/holdings/"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def retained_after_first_poll(controller: FakeController, port: int) -> dict[str, str]:
    """Run one poll, then return what a subscriber that connects afterwards gets, by topic."""
    with running_bridge(env(port), controller, FakeClock()) as bridge:
        bridge.run_pending()
    return retained(port)


def test_every_input_and_holding_with_a_value_is_a_retained_topic(port: int) -> None:
    controller = FakeController.from_fixture()
    controller.set("inputs", "heatpump_status", "VD1 running")

    retained = retained_after_first_poll(controller, port)

    assert retained[INPUTS + "heatpump_status"] == "VD1 running"
    assert retained[INPUTS + "flow_line_temp"] == "29.2"
    assert retained[INPUTS + "heatpump_vd1_status"] == "1"
    assert retained[INPUTS + "version"] == "3.92.1"
    assert retained[HOLDINGS + "hot_water_setpoint"] == "40.0"
    assert retained[HOLDINGS + "lock_heating"] == "Off"
    # The fixture's installation has no mixing circuits.
    assert HOLDINGS + "mc1_heat_mode" not in retained
    with_value = {
        prefix + field.name
        for prefix, vector in ((INPUTS, controller.read_inputs()), (HOLDINGS, controller.read_holdings()))
        for _, field in vector.items()
        if field.value is not None and not field.name.startswith("unknown_")
    }
    values = {topic for topic in retained if topic.startswith((INPUTS, HOLDINGS)) and not topic.endswith("/meta")}
    assert values == with_value


def test_a_field_that_loses_its_value_has_its_topic_cleared(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port, LUX_SHI_POLL_INTERVAL="10"), controller, clock) as bridge:
            bridge.run_pending()
            subscriber.sync()

            controller.set("holdings", "hot_water_setpoint", None)
            clock.advance(10)
            bridge.run_pending()
            cleared = subscriber.sync()

            clock.advance(10)
            bridge.run_pending()
            assert subscriber.sync() == []
    finally:
        subscriber.close()

    assert Message(HOLDINGS + "hot_water_setpoint", "", False) in cleared
    # The SHI answers a block of registers at once, so the fields next to it lose their value too.
    values = {m.topic for m in cleared if not m.topic.endswith("/meta")}
    assert values == without_value(controller) - without_value(FakeController.from_fixture())
    assert all(m.payload == "" for m in cleared)


def without_value(controller: FakeController) -> set[str]:
    return {HOLDINGS + field.name for _, field in controller.read_holdings().items() if field.value is None}


def test_the_cfi_and_the_shi_are_polled_on_their_own_intervals(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)

    def change_both(cfi: float, shi: float) -> None:
        controller.set("calculations", "ID_WEB_Temperatur_TVL", cfi)
        controller.set("inputs", "flow_line_temp", shi)

    try:
        with running_bridge(
            env(port, LUX_CFI_POLL_INTERVAL="10", LUX_SHI_POLL_INTERVAL="4"), controller, clock
        ) as bridge:
            bridge.run_pending()
            subscriber.sync()

            change_both(30.0, 30.0)
            clock.advance(4)
            bridge.run_pending()
            assert subscriber.sync() == [Message(INPUTS + "flow_line_temp", "30.0", False)]

            change_both(31.0, 31.0)
            clock.advance(4)
            bridge.run_pending()
            assert subscriber.sync() == [Message(INPUTS + "flow_line_temp", "31.0", False)]

            clock.advance(2)
            bridge.run_pending()
            assert subscriber.sync() == [Message("luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL", "31.0", False)]
    finally:
        subscriber.close()
