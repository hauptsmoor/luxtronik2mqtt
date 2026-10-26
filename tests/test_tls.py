"""MQTT over TLS: the Bridge talks to a broker's TLS listener and checks its certificate."""

import logging
import signal
from collections.abc import Iterator
from pathlib import Path

import pytest
from fake_controller import FakeController
from harness import (
    Broker,
    Certificates,
    FakeClock,
    Subscriber,
    broker_certificates,
    env,
    restartable_broker,
    running_bridge,
)

from luxtronik2mqtt.main import main

TVL = "luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL"


@pytest.fixture
def certificates(tmp_path: Path) -> Certificates:
    return broker_certificates(tmp_path / "ca")


@pytest.fixture(autouse=True)
def sigterm_restored() -> Iterator[None]:
    """`main` handles SIGTERM; the test process gets its own handler back afterwards."""
    previous = signal.getsignal(signal.SIGTERM)
    yield
    signal.signal(signal.SIGTERM, previous)


@pytest.fixture
def tls_broker(certificates: Certificates) -> Iterator[Broker]:
    with restartable_broker(certificates) as broker:
        yield broker


def test_values_arrive_over_tls_with_a_custom_ca(tls_broker: Broker, certificates: Certificates) -> None:
    bridge_env = env(tls_broker.tls_port, LUX_MQTT_TLS="true", LUX_MQTT_CA_FILE=str(certificates.ca))
    subscriber = Subscriber(tls_broker.port)
    try:
        with running_bridge(bridge_env, FakeController.from_fixture(), FakeClock()) as bridge:
            bridge.run_pending()
            topics = {m.topic for m in subscriber.sync()}
    finally:
        subscriber.close()

    assert TVL in topics


def test_a_ca_that_doesnt_match_fails_clearly_without_falling_back_to_plain_mqtt(
    tls_broker: Broker, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    other_ca = broker_certificates(tmp_path / "other-ca").ca
    subscriber = Subscriber(tls_broker.port)
    try:
        assert main(env(tls_broker.tls_port, LUX_MQTT_TLS="true", LUX_MQTT_CA_FILE=str(other_ca))) != 0
        received = subscriber.sync()
    finally:
        subscriber.close()

    errors = [r.getMessage() for r in caplog.records if r.levelno >= logging.ERROR]
    assert any("MQTT broker" in error and "certificate verify failed" in error for error in errors)
    assert received == []
