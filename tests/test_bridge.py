"""The Bridge as a subscriber sees it: CFI Calculations from the fake Controller on a real broker."""

import os
import re
import time
from collections.abc import Iterator

import pytest

from fake_controller import FakeController
from harness import FakeClock, Message, Subscriber, broker, env, running_bridge
from luxtronik2mqtt.main import main

TOPIC = "luxtronik/cfi/calculations/"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def retained_after_first_poll(controller: FakeController, bridge_env: dict[str, str], port: int) -> dict[str, str]:
    """Run one poll, then return what a subscriber that connects afterwards gets, by topic."""
    with running_bridge(bridge_env, controller, FakeClock()) as bridge:
        bridge.run_pending()
    subscriber = Subscriber(port)
    try:
        messages = subscriber.sync()
    finally:
        subscriber.close()
    assert all(m.retained for m in messages)
    return {m.topic: m.payload for m in messages}


def test_every_known_calculation_is_a_retained_topic(port: int) -> None:
    controller = FakeController.from_fixture()

    retained = retained_after_first_poll(controller, env(port), port)

    known = {
        field.name
        for _, field in controller.read_calculations().items()
        if field.value is not None
        and not field.name.startswith("Unknown_")
        and not re.fullmatch(r"ID_WEB_SoftStand_\d+", field.name)
    }
    values = {topic for topic in retained if topic.startswith(TOPIC) and not topic.endswith("/meta")}
    assert values == {TOPIC + name for name in known}
    assert TOPIC + "ID_WEB_SoftStand" in retained
    assert not any(re.search(r"/Unknown_|/ID_WEB_SoftStand_\d", topic) for topic in retained)


def test_payloads_are_readable_values(port: int) -> None:
    controller = FakeController.from_fixture()
    # The fixture was captured while the heat pump was idle.
    controller.set("calculations", "ID_WEB_Temperatur_TVL", 38.3)
    controller.set("calculations", "ID_WEB_WP_BZ_akt", "heating")
    controller.set("calculations", "ID_WEB_VD1out", True)

    retained = retained_after_first_poll(controller, env(port), port)

    assert retained[TOPIC + "ID_WEB_Temperatur_TVL"] == "38.3"
    assert retained[TOPIC + "ID_WEB_WP_BZ_akt"] == "heating"
    assert retained[TOPIC + "ID_WEB_VD1out"] == "1"
    assert retained[TOPIC + "ID_WEB_ASDin"] == "1"
    assert retained[TOPIC + "ID_WEB_ERROR_Time0"] == "2025-06-19T21:31:28Z"
    assert retained[TOPIC + "ID_WEB_AdresseIP_akt"] == "192.0.2.10"
    assert retained[TOPIC + "ID_WEB_SoftStand"] == "V3.92.1"
    assert retained[TOPIC + "ID_WEB_ERROR_Nr0"] == "Modbus inverter"


def test_timestamps_dont_depend_on_the_time_zone(port: int) -> None:
    controller = FakeController.from_fixture()
    previous = os.environ.get("TZ")
    os.environ["TZ"] = "Pacific/Auckland"
    time.tzset()
    try:
        retained = retained_after_first_poll(controller, env(port), port)
    finally:
        if previous is None:
            del os.environ["TZ"]
        else:
            os.environ["TZ"] = previous
        time.tzset()

    assert retained[TOPIC + "ID_WEB_ERROR_Time0"] == "2025-06-19T21:31:28Z"


def test_only_a_changed_value_is_published_again_on_the_next_poll(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port, LUX_CFI_POLL_INTERVAL="10"), controller, clock) as bridge:
            bridge.run_pending()
            assert len(subscriber.sync()) > 200

            controller.set("calculations", "ID_WEB_Temperatur_TVL", 38.3)
            clock.advance(9.9)
            bridge.run_pending()
            assert subscriber.sync() == []

            clock.advance(0.1)
            bridge.run_pending()
            assert subscriber.sync() == [Message(TOPIC + "ID_WEB_Temperatur_TVL", "38.3", False)]

            clock.advance(10)
            bridge.run_pending()
            assert subscriber.sync() == []
    finally:
        subscriber.close()


def test_the_prefix_sets_the_topic_root(port: int) -> None:
    retained = retained_after_first_poll(FakeController.from_fixture(), env(port, LUX_MQTT_PREFIX="home/heatpump"), port)

    assert retained["home/heatpump/cfi/calculations/ID_WEB_Temperatur_TVL"] == "29.2"
    assert all(topic.startswith("home/heatpump/") for topic in retained)


@pytest.mark.parametrize(
    ("bridge_env", "variable"),
    [
        ({"LUX_MQTT_HOST": "broker"}, "LUX_HOST"),
        ({"LUX_HOST": "controller"}, "LUX_MQTT_HOST"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_CFI_POLL_INTERVAL": "1.5"}, "LUX_CFI_POLL_INTERVAL"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_CFI_POLL_INTERVAL": "often"}, "LUX_CFI_POLL_INTERVAL"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_SHI_POLL_INTERVAL": "1"}, "LUX_SHI_POLL_INTERVAL"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_SHI_PORT": "modbus"}, "LUX_SHI_PORT"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_REPUBLISH_INTERVAL": "hourly"}, "LUX_REPUBLISH_INTERVAL"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_REPUBLISH_INTERVAL": "0"}, "LUX_REPUBLISH_INTERVAL"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_SHI_WRITE": "yes"}, "LUX_SHI_WRITE"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_MQTT_PORT": "0"}, "LUX_MQTT_PORT"),
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_MQTT_TLS": "on"}, "LUX_MQTT_TLS"),
        (
            {"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_MQTT_TLS": "true", "LUX_MQTT_CA_FILE": "/nonexistent/ca.crt"},
            "LUX_MQTT_CA_FILE",
        ),
        # A readable file, but no TLS to use it with.
        ({"LUX_HOST": "controller", "LUX_MQTT_HOST": "broker", "LUX_MQTT_CA_FILE": __file__}, "LUX_MQTT_CA_FILE"),
    ],
)
def test_a_missing_or_invalid_setting_stops_the_bridge_at_startup(
    bridge_env: dict[str, str], variable: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(bridge_env) != 0

    assert variable in capsys.readouterr().err
