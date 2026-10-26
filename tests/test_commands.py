"""The Bridge as a control application sees it: Commands that set SHI Holdings."""

from collections.abc import Iterator

import pytest

from fake_controller import FakeController
from harness import FakeClock, Message, Subscriber, broker, env, running_bridge

HOLDINGS = "luxtronik/shi/holdings/"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


@pytest.fixture
def subscriber(port: int) -> Iterator[Subscriber]:
    subscriber = Subscriber(port)
    yield subscriber
    subscriber.close()


def send(subscriber: Subscriber, name: str, payload: str, wait_for: str) -> dict[str, str]:
    """Send a Command for this Holding and wait for its topic or its error topic.

    Returns what the Bridge published meanwhile, by topic.
    """
    subscriber.publish(f"{HOLDINGS}{name}/set", payload)
    arrived = subscriber.wait_for(f"{HOLDINGS}{name}/{wait_for}".rstrip("/"))
    return {m.topic: m.payload for m in arrived if not m.topic.endswith("/set")}


def test_with_commands_switched_off_a_command_gets_an_error_and_isnt_written(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        subscriber.publish(HOLDINGS + "hot_water_setpoint/set", "45")
        arrived = subscriber.wait_for(HOLDINGS + "hot_water_setpoint/error")

    assert controller.writes == []
    [error] = [m for m in arrived if m.topic.endswith("/error")]
    assert not error.retained
    assert "LUX_SHI_WRITE" in error.payload


def test_a_command_is_written_and_the_holding_topic_shows_the_value_read_back(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="")

    assert controller.writes == [("hot_water_setpoint", "45")]
    assert arrived == {HOLDINGS + "hot_water_setpoint": "45.0"}


def test_a_mode_command_uses_the_readable_text_the_bridge_publishes(port: int, subscriber: Subscriber) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        assert {m.topic: m.payload for m in subscriber.sync()}[HOLDINGS + "heating_mode"] == "Off"

        arrived = send(subscriber, "heating_mode", "Setpoint", wait_for="")

    assert arrived == {HOLDINGS + "heating_mode": "Setpoint"}
    assert controller.read_holdings().get("heating_mode").value == "Setpoint"


def test_a_retained_command_left_at_the_broker_is_rejected_and_not_written(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    subscriber.publish(HOLDINGS + "hot_water_setpoint/set", "45", retain=True)
    subscriber.sync()

    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()):
        arrived = subscriber.wait_for(HOLDINGS + "hot_water_setpoint/error")

    assert controller.writes == []
    assert Message(HOLDINGS + "hot_water_setpoint/error", "rejected: a retained Command isn't run", False) in arrived


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("flow_line_temp", "rejected: flow_line_temp isn't a writable Holding"),
        ("unknown_holding_60", "rejected: unknown_holding_60 isn't a writable Holding"),
        ("no_such_holding", "rejected: no_such_holding isn't a writable Holding"),
        # The fixture's installation has no mixing circuits.
        ("mc1_heat_mode", "rejected: mc1_heat_mode has no value on this Controller"),
    ],
)
def test_a_command_for_a_name_that_isnt_a_writable_holding_with_a_value_is_rejected(
    port: int, subscriber: Subscriber, name: str, reason: str
) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, name, "1", wait_for="error")

    assert controller.writes == []
    assert arrived == {f"{HOLDINGS}{name}/error": reason}


@pytest.mark.parametrize(("name", "payload"), [("hot_water_setpoint", "warm"), ("heating_mode", "Sometimes")])
def test_a_command_the_library_cant_convert_is_rejected(
    port: int, subscriber: Subscriber, name: str, payload: str
) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, name, payload, wait_for="error")

    assert controller.writes == []
    assert arrived == {f"{HOLDINGS}{name}/error": f"rejected: {payload!r} isn't a valid value for {name}"}


def test_with_the_shi_unreachable_a_command_is_rejected(port: int, subscriber: Subscriber) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, clock) as bridge:
        bridge.run_pending()
        controller.shi_reachable = False
        clock.advance(30)
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="error")

    assert controller.writes == []
    assert arrived == {HOLDINGS + "hot_water_setpoint/error": "rejected: the SHI is unreachable"}


def test_a_command_the_shi_doesnt_answer_since_the_last_poll_gets_an_error(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()
        controller.shi_reachable = False

        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="error")

    assert arrived == {HOLDINGS + "hot_water_setpoint/error": "failed: the SHI is unreachable"}


def test_when_the_controller_applies_a_different_value_the_topic_shows_it_and_an_error_is_published(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    controller.applies_instead = 42.0
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="error")

    assert arrived == {
        HOLDINGS + "hot_water_setpoint": "42.0",
        HOLDINGS + "hot_water_setpoint/error": "failed: the Controller applied 42.0 instead of 45.0",
    }


def test_when_the_controller_refuses_the_write_an_error_is_published_and_the_topic_keeps_the_value_read_back(
    port: int, subscriber: Subscriber
) -> None:
    controller = FakeController.from_fixture()
    controller.refuse_writes = True
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        before = {m.topic: m.payload for m in subscriber.sync()}

        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="error")

    assert controller.writes == [("hot_water_setpoint", "45")]
    assert before[HOLDINGS + "hot_water_setpoint"] == "40.0"
    # The value read back is still 40.0, so its retained topic doesn't change.
    assert arrived == {HOLDINGS + "hot_water_setpoint/error": "failed: the Controller refused the write"}


def test_a_command_for_a_cfi_parameter_is_ignored(port: int, subscriber: Subscriber) -> None:
    controller = FakeController.from_fixture()
    include = "cfi/parameters/ID_Einst_BWS_akt"
    with running_bridge(env(port, LUX_SHI_WRITE="true", LUX_INCLUDE=include), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        subscriber.publish("luxtronik/cfi/parameters/ID_Einst_BWS_akt/set", "45")
        # The broker delivers in order, so once this one has run, the one before would have arrived.
        arrived = send(subscriber, "hot_water_setpoint", "45", wait_for="")

    assert controller.writes == [("hot_water_setpoint", "45")]
    assert arrived == {HOLDINGS + "hot_water_setpoint": "45.0"}


def test_a_negative_offset_is_written_and_read_back(port: int, subscriber: Subscriber) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        arrived = send(subscriber, "heating_offset", "-2", wait_for="")

    assert arrived == {HOLDINGS + "heating_offset": "-2.0"}


def test_an_empty_message_clearing_a_retained_command_is_ignored(port: int, subscriber: Subscriber) -> None:
    controller = FakeController.from_fixture()
    with running_bridge(env(port, LUX_SHI_WRITE="true"), controller, FakeClock()) as bridge:
        bridge.run_pending()
        subscriber.sync()

        subscriber.publish(HOLDINGS + "hot_water_setpoint/set", "", retain=True)
        arrived = send(subscriber, "hot_water_mode", "Setpoint", wait_for="")

    assert controller.writes == [("hot_water_mode", "Setpoint")]
    assert arrived == {HOLDINGS + "hot_water_mode": "Setpoint"}
