"""Entry point: configures the Bridge from the ENV and runs it until stopped."""

import logging
import os
import signal
import sys
from collections.abc import Mapping
from types import FrameType

from luxtronik2mqtt.bridge import Bridge
from luxtronik2mqtt.config import ConfigError, Settings
from luxtronik2mqtt.controller import Controller

LOGGER = logging.getLogger("luxtronik2mqtt")


def main(env: Mapping[str, str] | None = None) -> int:
    try:
        settings = Settings.from_env(os.environ if env is None else env)
    except ConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    logging.basicConfig(
        level=settings.log_level,
        stream=sys.stdout,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # The library logs every read at INFO; that much only belongs in debug output.
    if settings.log_level != "DEBUG":
        logging.getLogger("luxtronik").setLevel(max(logging.getLevelName(settings.log_level), logging.WARNING))
    signal.signal(signal.SIGTERM, _exit)

    bridge = Bridge(settings, Controller(settings.host, cfi_port=settings.cfi_port, shi_port=settings.shi_port))
    try:
        bridge.start()
    except OSError as error:
        LOGGER.error("can't connect to MQTT broker %s:%s: %s", settings.mqtt_host, settings.mqtt_port, error)
        return 1
    except KeyboardInterrupt:
        # Stopped while connecting.
        return 0
    try:
        bridge.run()
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
    return 0


def _exit(signum: int, frame: FrameType | None) -> None:
    raise KeyboardInterrupt


if __name__ == "__main__":
    sys.exit(main())
