"""The Bridge as a subscriber sees it: status topics, and how the Bridge rides out outages."""

import logging
import os
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest

from fake_controller import FakeController
from harness import TIMEOUT, FakeClock, Message, Subscriber, broker, env, restartable_broker, running_bridge
from peers import closed_port

STATUS = "luxtronik/status"
CFI_STATUS = "luxtronik/cfi/status"
SHI_STATUS = "luxtronik/shi/status"
CALCULATIONS = "luxtronik/cfi/calculations/"
# The Bridge's own loggers, not the luxtronik library's.
OURS = "luxtronik2mqtt"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def retained(port: int) -> dict[str, str]:
    """What a subscriber that connects now gets, by topic."""
    messages = received_on_connect(port)
    assert all(m.retained for m in messages)
    return {m.topic: m.payload for m in messages}


def latest(port: int) -> dict[str, str]:
    """What a subscriber that connects now gets, by topic, retained or not.

    For waiting on a Bridge process the test doesn't step: it may publish while the
    subscriber connects, and a message published then arrives without the retained flag.
    """
    return {m.topic: m.payload for m in received_on_connect(port)}


def received_on_connect(port: int) -> list[Message]:
    """What a subscriber that connects now gets, retained or published while it connects."""
    subscriber = Subscriber(port)
    try:
        return subscriber.sync()
    finally:
        subscriber.close()


def test_while_the_bridge_runs_every_status_is_online(port: int) -> None:
    with running_bridge(env(port), FakeController.from_fixture(), FakeClock()) as bridge:
        bridge.run_pending()
        topics = retained(port)

    assert topics[STATUS] == "online"
    assert topics[CFI_STATUS] == "online"
    assert topics[SHI_STATUS] == "online"


@contextmanager
def bridge_process(port: int) -> Iterator[subprocess.Popen[bytes]]:
    """The `luxtronik2mqtt` command in its own process, with no Controller to talk to, once its status is online."""
    process = subprocess.Popen(
        [sys.executable, "-m", "luxtronik2mqtt.main"],
        env={
            **os.environ,
            **env(port, LUX_HOST="127.0.0.1", LUX_CFI_PORT=str(closed_port()), LUX_SHI_PORT=str(closed_port())),
        },
        stdout=subprocess.DEVNULL,
    )
    try:
        wait_until(lambda: latest(port).get(STATUS) == "online")
        yield process
    finally:
        process.kill()
        process.wait(TIMEOUT)


def wait_until(condition: Callable[[], bool]) -> None:
    """Wait in real time, for what happens outside the injected clock."""
    deadline = time.monotonic() + TIMEOUT
    while not condition():
        assert time.monotonic() < deadline, "timed out"
        time.sleep(0.05)


def test_on_sigterm_the_bridge_publishes_offline_before_it_exits(port: int) -> None:
    with bridge_process(port) as process:
        process.send_signal(signal.SIGTERM)
        assert process.wait(TIMEOUT) == 0

    assert retained(port)[STATUS] == "offline"


def test_when_the_bridge_dies_the_last_will_sets_its_status_offline(port: int) -> None:
    with bridge_process(port) as process:
        process.kill()
        process.wait(TIMEOUT)

        wait_until(lambda: latest(port).get(STATUS) == "offline")


def test_an_unreachable_cfi_goes_offline_and_keeps_its_retained_values(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    with running_bridge(env(port), controller, clock) as bridge:
        bridge.run_pending()
        before = retained(port)

        controller.cfi_reachable = False
        clock.advance(30)
        bridge.run_pending()
        during = retained(port)

    assert during[CFI_STATUS] == "offline"
    assert during[SHI_STATUS] == "online"
    calculations = {topic: payload for topic, payload in before.items() if topic.startswith(CALCULATIONS)}
    assert calculations
    assert calculations.items() <= during.items()


def test_when_the_cfi_is_back_it_goes_online_and_every_cfi_topic_is_republished(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port), controller, clock) as bridge:
            bridge.run_pending()
            first = subscriber.sync()

            controller.cfi_reachable = False
            clock.advance(30)
            bridge.run_pending()
            assert subscriber.sync() == [Message(CFI_STATUS, "offline", False)]

            controller.cfi_reachable = True
            clock.advance(bridge.run_pending())
            bridge.run_pending()
            back = subscriber.sync()
    finally:
        subscriber.close()

    cfi_topics = {m.topic for m in first if m.topic.startswith("luxtronik/cfi/")}
    assert {m.topic for m in back} == cfi_topics
    assert Message(CFI_STATUS, "online", False) in back


def test_an_unreachable_cfi_is_retried_with_growing_delays_from_5_up_to_60_seconds(port: int) -> None:
    controller = FakeController.from_fixture()
    controller.cfi_reachable = False
    clock = FakeClock()
    attempted_at = []
    with running_bridge(env(port), controller, clock) as bridge:
        start = clock.now
        # Sleep as `run` does, until the time `run_pending` returns.
        while clock.now < start + 300:
            attempts = controller.attempts["CFI"]
            wait = bridge.run_pending()
            if controller.attempts["CFI"] > attempts:
                attempted_at.append(clock.now)
            clock.advance(wait)

    delays = [later - earlier for earlier, later in zip(attempted_at, attempted_at[1:])]
    assert delays[:6] == [5, 10, 20, 40, 60, 60]


def test_without_the_shi_the_bridge_runs_cfi_only_warns_once_and_picks_the_shi_up_later(
    port: int, caplog: pytest.LogCaptureFixture
) -> None:
    controller = FakeController.from_fixture()
    controller.shi_reachable = False
    clock = FakeClock()
    with running_bridge(env(port), controller, clock) as bridge:
        for _ in range(20):
            clock.advance(bridge.run_pending())
        without_shi = retained(port)
        warnings = [r for r in caplog.records if r.levelno >= logging.WARNING and r.name.startswith(OURS)]

        controller.shi_reachable = True
        clock.advance(bridge.run_pending())
        bridge.run_pending()
        with_shi = retained(port)

    assert any(topic.startswith(CALCULATIONS) for topic in without_shi)
    assert without_shi[SHI_STATUS] == "offline"
    assert not any(topic.startswith("luxtronik/shi/inputs/") for topic in without_shi)
    assert len(warnings) == 1
    assert "SHI" in warnings[0].getMessage()
    assert with_shi[SHI_STATUS] == "online"
    assert with_shi["luxtronik/shi/holdings/hot_water_setpoint"] == "40.0"


def test_a_long_outage_logs_once_when_it_starts_and_once_when_it_recovers(
    port: int, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    controller = FakeController.from_fixture()
    clock = FakeClock()
    with running_bridge(env(port), controller, clock) as bridge:
        bridge.run_pending()
        caplog.clear()

        controller.cfi_reachable = False
        for _ in range(50):
            clock.advance(bridge.run_pending())
        controller.cfi_reachable = True
        for _ in range(5):
            clock.advance(bridge.run_pending())
        logged = [r.getMessage() for r in caplog.records if r.levelno >= logging.INFO and r.name.startswith(OURS)]

    assert controller.attempts["CFI"] > 20
    assert len(logged) == 2
    assert all("CFI" in message for message in logged)


def test_after_a_broker_restart_the_bridge_reconnects_and_republishes_everything() -> None:
    with restartable_broker() as broker:
        with running_bridge(env(broker.port), FakeController.from_fixture(), FakeClock()) as bridge:
            bridge.run_pending()
            before = retained(broker.port)

            broker.restart()
            assert retained(broker.port) == {}

            # paho reconnects on its own, in real time.
            wait_until(lambda: {m.topic: m.payload for m in received_on_connect(broker.port)} == before)
