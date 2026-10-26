"""Configuration: the Bridge's settings, parsed and validated from the ENV at startup."""

import logging
from collections.abc import Mapping
from dataclasses import dataclass

from luxtronik2mqtt.controller import DEFAULT_CFI_PORT, DEFAULT_SHI_PORT

MIN_POLL_INTERVAL = 2.0


class ConfigError(Exception):
    """A setting is missing or invalid. The message names the ENV variable."""

    def __init__(self, variable: str, problem: str) -> None:
        super().__init__(f"{variable} {problem}")
        self.variable = variable


@dataclass(frozen=True)
class Settings:
    host: str
    mqtt_host: str
    cfi_port: int = DEFAULT_CFI_PORT
    cfi_poll_interval: float = 30.0
    shi_port: int = DEFAULT_SHI_PORT
    shi_poll_interval: float = 30.0
    mqtt_port: int = 1883
    mqtt_username: str | None = None
    mqtt_password: str | None = None
    mqtt_prefix: str = "luxtronik"
    log_level: str = "INFO"
    include: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        """The settings from these ENV variables. Raises ConfigError naming the first bad one."""
        env = {name: value.strip() for name, value in env.items() if value.strip()}
        return cls(
            host=_required(env, "LUX_HOST"),
            mqtt_host=_required(env, "LUX_MQTT_HOST"),
            cfi_port=_port(env, "LUX_CFI_PORT", DEFAULT_CFI_PORT),
            cfi_poll_interval=_poll_interval(env, "LUX_CFI_POLL_INTERVAL"),
            shi_port=_port(env, "LUX_SHI_PORT", DEFAULT_SHI_PORT),
            shi_poll_interval=_poll_interval(env, "LUX_SHI_POLL_INTERVAL"),
            mqtt_port=_port(env, "LUX_MQTT_PORT", 1883),
            mqtt_username=env.get("LUX_MQTT_USERNAME"),
            mqtt_password=env.get("LUX_MQTT_PASSWORD"),
            mqtt_prefix=_prefix(env, "LUX_MQTT_PREFIX"),
            log_level=_log_level(env, "LUX_LOG_LEVEL"),
            include=_patterns(env, "LUX_INCLUDE"),
            exclude=_patterns(env, "LUX_EXCLUDE"),
        )


def _required(env: Mapping[str, str], variable: str) -> str:
    if variable not in env:
        raise ConfigError(variable, "is required")
    return env[variable]


def _port(env: Mapping[str, str], variable: str, default: int) -> int:
    if variable not in env:
        return default
    try:
        port = int(env[variable])
    except ValueError:
        raise ConfigError(variable, f"must be a port number, not {env[variable]!r}") from None
    if not 1 <= port <= 65535:
        raise ConfigError(variable, f"must be a port number from 1 to 65535, not {port}")
    return port


def _poll_interval(env: Mapping[str, str], variable: str) -> float:
    if variable not in env:
        return 30.0
    try:
        seconds = float(env[variable])
    except ValueError:
        raise ConfigError(variable, f"must be a number of seconds, not {env[variable]!r}") from None
    if not seconds >= MIN_POLL_INTERVAL:
        raise ConfigError(variable, f"must be at least {MIN_POLL_INTERVAL:g} seconds, not {env[variable]}")
    return seconds


def _prefix(env: Mapping[str, str], variable: str) -> str:
    prefix = env.get(variable, "luxtronik").strip("/")
    if not prefix or "+" in prefix or "#" in prefix:
        raise ConfigError(variable, f"must be a topic path without wildcards, not {env[variable]!r}")
    return prefix


def _log_level(env: Mapping[str, str], variable: str) -> str:
    level = env.get(variable, "INFO").upper()
    if level not in logging.getLevelNamesMapping():
        raise ConfigError(variable, f"must be a log level such as DEBUG, INFO or WARNING, not {env[variable]!r}")
    return level


def _patterns(env: Mapping[str, str], variable: str) -> tuple[str, ...]:
    patterns = (pattern.strip() for pattern in env.get(variable, "").split(","))
    return tuple(pattern for pattern in patterns if pattern)
