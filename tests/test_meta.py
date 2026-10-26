"""The Bridge as a subscriber sees it: the meta topic next to each value topic."""

import json
from collections.abc import Iterator
from typing import Any

import pytest

from fake_controller import FakeController
from harness import FakeClock, Subscriber, broker, env, running_bridge

CALCULATIONS = "luxtronik/cfi/calculations/"
HOLDINGS = "luxtronik/shi/holdings/"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def retained_after_first_poll(controller: FakeController, port: int) -> dict[str, str]:
    """Run one poll, then return what a subscriber that connects afterwards gets, by topic."""
    with running_bridge(env(port), controller, FakeClock()) as bridge:
        bridge.run_pending()
    subscriber = Subscriber(port)
    try:
        messages = subscriber.sync()
    finally:
        subscriber.close()
    assert all(m.retained for m in messages)
    return {m.topic: m.payload for m in messages}


def meta_of(retained: dict[str, str], topic: str) -> Any:
    return json.loads(retained[topic + "/meta"])


def test_a_calculation_meta_holds_its_unit_and_type_and_is_not_writable(port: int) -> None:
    retained = retained_after_first_poll(FakeController.from_fixture(), port)

    assert meta_of(retained, CALCULATIONS + "ID_WEB_Temperatur_TVL") == {
        "unit": "°C",
        "type": "Celsius",
        "writable": False,
    }


def test_a_holding_meta_is_writable_and_a_mode_lists_its_options(port: int) -> None:
    retained = retained_after_first_poll(FakeController.from_fixture(), port)

    assert meta_of(retained, HOLDINGS + "hot_water_mode") == {
        "unit": None,
        "type": "ControlMode",
        "writable": True,
        "options": ["Off", "Setpoint", "Offset", "Level"],
    }
    assert meta_of(retained, HOLDINGS + "hot_water_setpoint") == {
        "unit": "°C",
        "type": "CelsiusUInt16",
        "writable": True,
    }
    assert "options" not in meta_of(retained, "luxtronik/shi/inputs/flow_line_temp")


def test_every_value_topic_and_only_those_have_a_meta_topic(port: int) -> None:
    retained = retained_after_first_poll(FakeController.from_fixture(), port)

    values = {topic for topic in retained if "/status" not in topic and not topic.endswith("/meta")}
    metas = {topic.removesuffix("/meta") for topic in retained if topic.endswith("/meta")}
    assert metas == values
    # The fixture's installation has no mixing circuits, and Parameters aren't published by default.
    assert HOLDINGS + "mc1_heat_mode/meta" not in retained
    assert not any(topic.startswith("luxtronik/cfi/parameters/") for topic in retained)


def test_a_meta_topic_is_cleared_with_its_value_topic_and_not_resent_on_each_poll(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port, LUX_SHI_POLL_INTERVAL="10"), controller, clock) as bridge:
            bridge.run_pending()
            subscriber.sync()

            controller.set("inputs", "flow_line_temp", 30.0)
            clock.advance(10)
            bridge.run_pending()
            changed = subscriber.sync()

            controller.set("holdings", "hot_water_setpoint", None)
            clock.advance(10)
            bridge.run_pending()
            cleared = {m.topic: m.payload for m in subscriber.sync()}
    finally:
        subscriber.close()

    assert [m.topic for m in changed] == ["luxtronik/shi/inputs/flow_line_temp"]
    assert cleared[HOLDINGS + "hot_water_setpoint"] == ""
    assert cleared[HOLDINGS + "hot_water_setpoint/meta"] == ""
    assert {topic.removesuffix("/meta") for topic in cleared} == {t for t in cleared if not t.endswith("/meta")}
