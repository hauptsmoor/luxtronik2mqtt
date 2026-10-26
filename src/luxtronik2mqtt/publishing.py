"""Publishing: the MQTT connection, and the last payload published on each topic."""

import logging
import time

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from luxtronik2mqtt.config import Settings

LOGGER = logging.getLogger(__name__)

# How long a round of publishes may wait for the broker to acknowledge them.
ACK_TIMEOUT = 10.0


class Publisher:
    """Publishes retained values under the prefix, each only when its payload changed."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._prefix = settings.mqtt_prefix
        self._published: dict[str, str] = {}
        self._client = mqtt.Client(
            CallbackAPIVersion.VERSION2,
            # Derived from the prefix, so two Bridges on one broker don't collide.
            client_id="luxtronik2mqtt-" + self._prefix.replace("/", "-"),
            protocol=mqtt.MQTTv311,
        )
        if settings.mqtt_username is not None:
            self._client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def connect(self) -> None:
        """Connect to the broker. Raises OSError if it can't be reached; after that, paho reconnects on its own."""
        self._client.connect(self._settings.mqtt_host, self._settings.mqtt_port)
        self._client.loop_start()
        LOGGER.info("connected to MQTT broker %s:%s", self._settings.mqtt_host, self._settings.mqtt_port)

    def disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def publish_changes(self, payloads: dict[str, str | None]) -> None:
        """Publish each payload, by topic path after the prefix, whose topic last had a different one.

        None is a value without a payload: its topic, if it has one, is cleared with
        an empty retained payload. An empty payload clears the topic at the broker
        too, so it counts as None.

        Waits until the broker has acknowledged them, so a round is complete when it returns.
        """
        sent = []
        for path, payload in payloads.items():
            payload = payload or None
            if self._published.get(path) == payload:
                continue
            # A message published while disconnected stays queued and goes out on reconnect.
            sent.append(self._client.publish(f"{self._prefix}/{path}", payload or "", qos=1, retain=True))
            if payload is None:
                del self._published[path]
            else:
                self._published[path] = payload
        LOGGER.debug("published %d of %d values", len(sent), len(payloads))
        deadline = time.monotonic() + ACK_TIMEOUT
        for info in sent:
            try:
                info.wait_for_publish(max(deadline - time.monotonic(), 0))
            except (RuntimeError, ValueError):
                pass
