"""The Bridge as a subscriber sees it: LUX_INCLUDE and LUX_EXCLUDE tailoring what is published."""

from collections.abc import Iterator

import pytest

from fake_controller import FakeController
from harness import FakeClock, Subscriber, broker, env, running_bridge
from luxtronik2mqtt.config import Settings

PREFIX = "luxtronik/"


@pytest.fixture
def port() -> Iterator[int]:
    with broker() as port:
        yield port


def retained_after_first_poll(port: int, **overrides: str) -> set[str]:
    """Run one poll with this ENV, then return the topics a subscriber that connects afterwards gets."""
    with running_bridge(env(port, **overrides), FakeController.from_fixture(), FakeClock()) as bridge:
        bridge.run_pending()
    subscriber = Subscriber(port)
    try:
        messages = subscriber.sync()
    finally:
        subscriber.close()
    assert all(m.retained for m in messages)
    return {m.topic.removeprefix(PREFIX) for m in messages}


def under(topics: set[str], vector_path: str) -> set[str]:
    return {topic for topic in topics if topic.startswith(vector_path + "/")}


def test_an_include_adds_parameters_to_the_defaults(port: int) -> None:
    with broker() as other_port:
        defaults = retained_after_first_poll(other_port)

    retained = retained_after_first_poll(port, LUX_INCLUDE="cfi/parameters/ID_Einst_BWS_*")

    parameters = under(retained, "cfi/parameters")
    assert "cfi/parameters/ID_Einst_BWS_akt" in parameters
    assert all(topic.startswith("cfi/parameters/ID_Einst_BWS_") for topic in parameters)
    assert retained - parameters == defaults


def test_an_include_adds_visibilities(port: int) -> None:
    retained = retained_after_first_poll(port, LUX_INCLUDE="cfi/visibilities/*")

    assert "cfi/visibilities/ID_Visi_Heizung" in retained
    assert len(under(retained, "cfi/visibilities")) > 300


def test_an_include_switches_on_the_unknown_calculations(port: int) -> None:
    retained = retained_after_first_poll(port, LUX_INCLUDE="cfi/calculations/Unknown_*")

    assert "cfi/calculations/Unknown_Calculation_0" in retained
    assert not any("/unknown_" in topic for topic in retained)


def test_an_exclude_removes_a_default_calculation(port: int) -> None:
    retained = retained_after_first_poll(port, LUX_EXCLUDE="cfi/calculations/ID_WEB_Temperatur_TWA")

    assert "cfi/calculations/ID_WEB_Temperatur_TWA" not in retained
    assert "cfi/calculations/ID_WEB_Temperatur_TVL" in retained


def test_an_exclude_removes_shi_topics(port: int) -> None:
    retained = retained_after_first_poll(port, LUX_EXCLUDE="shi/inputs/*")

    assert under(retained, "shi/inputs") == set()
    assert "shi/holdings/hot_water_setpoint" in retained


def test_an_exclude_wins_over_an_include(port: int) -> None:
    retained = retained_after_first_poll(
        port, LUX_INCLUDE="cfi/parameters/ID_Einst_BWS_*", LUX_EXCLUDE="cfi/parameters/ID_Einst_BWS_akt"
    )

    assert "cfi/parameters/ID_Einst_BWS_Hyst_akt" in retained
    assert "cfi/parameters/ID_Einst_BWS_akt" not in retained


@pytest.mark.parametrize(
    ("value", "patterns"),
    [
        (" cfi/parameters/ID_Einst_BWS_* ,  cfi/visibilities/* ", ("cfi/parameters/ID_Einst_BWS_*", "cfi/visibilities/*")),
        ("shi/inputs/*,,", ("shi/inputs/*",)),
        ("", ()),
        ("  ", ()),
    ],
)
def test_patterns_are_comma_separated_and_whitespace_around_them_is_ignored(
    value: str, patterns: tuple[str, ...]
) -> None:
    settings = Settings.from_env(env(1883, LUX_INCLUDE=value, LUX_EXCLUDE=value))

    assert settings.include == patterns
    assert settings.exclude == patterns
