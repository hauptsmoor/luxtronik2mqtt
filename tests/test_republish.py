"""The Bridge as a subscriber sees it: every selected value republished on LUX_REPUBLISH_INTERVAL."""

from collections.abc import Iterator

import pytest

from fake_controller import FakeController
from harness import FakeClock, Message, Subscriber, broker, env, running_bridge

TVL = "luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def test_every_value_is_republished_once_the_interval_passes_and_not_before(port: int) -> None:
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port), FakeController.from_fixture(), clock) as bridge:
            bridge.run_pending()
            first = subscriber.sync()

            # The default polls run every 30 s, the republish every 300 s.
            for _ in range(9):
                clock.advance(30)
                bridge.run_pending()
                assert subscriber.sync() == []

            clock.advance(30)
            bridge.run_pending()
            republished = subscriber.sync()
    finally:
        subscriber.close()

    assert any(m.topic.startswith("luxtronik/shi/") for m in first)
    assert sorted(republished, key=lambda m: m.topic) == sorted(first, key=lambda m: m.topic)


def test_between_republishes_only_changes_are_published_and_the_interval_is_configurable(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(
            env(port, LUX_CFI_POLL_INTERVAL="10", LUX_SHI_POLL_INTERVAL="10", LUX_REPUBLISH_INTERVAL="60"),
            controller,
            clock,
        ) as bridge:
            bridge.run_pending()
            first = subscriber.sync()

            controller.set("calculations", "ID_WEB_Temperatur_TVL", 38.3)
            clock.advance(30)
            bridge.run_pending()
            assert subscriber.sync() == [Message(TVL, "38.3", False)]

            # A change on the poll at the republish is published once, with its new value.
            controller.set("calculations", "ID_WEB_Temperatur_TVL", 40.1)
            clock.advance(30)
            bridge.run_pending()
            republished = subscriber.sync()
    finally:
        subscriber.close()

    assert [m for m in republished if m.topic == TVL] == [Message(TVL, "40.1", False)]
    assert {m.topic for m in republished} == {m.topic for m in first}


def test_the_republish_interval_counts_from_the_first_poll(port: int) -> None:
    clock = FakeClock()
    subscriber = Subscriber(port)
    republished_after = []
    try:
        with running_bridge(
            env(port, LUX_CFI_POLL_INTERVAL="10", LUX_SHI_POLL_INTERVAL="10", LUX_REPUBLISH_INTERVAL="60"),
            FakeController.from_fixture(),
            clock,
        ) as bridge:
            # Connecting to the broker took a while.
            clock.advance(5)
            first_poll = clock.now
            wait = bridge.run_pending()
            subscriber.sync()

            # Sleep as `run` does, until the time `run_pending` returns.
            while clock.now < first_poll + 120:
                clock.advance(wait)
                wait = bridge.run_pending()
                if subscriber.sync():
                    republished_after.append(clock.now - first_poll)
    finally:
        subscriber.close()

    assert republished_after == [60, 120]


def test_values_of_an_unreachable_interface_are_not_republished(port: int) -> None:
    controller = FakeController.from_fixture()
    clock = FakeClock()
    subscriber = Subscriber(port)
    try:
        with running_bridge(env(port, LUX_REPUBLISH_INTERVAL="60"), controller, clock) as bridge:
            bridge.run_pending()
            subscriber.sync()

            controller.cfi_reachable = False
            clock.advance(30)
            bridge.run_pending()
            subscriber.sync()
            clock.advance(30)
            bridge.run_pending()
            republished = subscriber.sync()
    finally:
        subscriber.close()

    assert any(m.topic.startswith("luxtronik/shi/") for m in republished)
    assert [m for m in republished if m.topic.startswith("luxtronik/cfi/")] == [
        Message("luxtronik/cfi/status", "offline", False)
    ]
