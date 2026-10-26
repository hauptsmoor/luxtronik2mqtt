"""Publishing: the MQTT connection, and the last payload published on each topic."""

import logging
import threading
import time
from collections.abc import Callable, Mapping

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCode

from luxtronik2mqtt.config import Settings

LOGGER = logging.getLogger(__name__)

# How long a round of publishes may wait for the broker to acknowledge them.
ACK_TIMEOUT = 10.0

# The topic path of the Bridge's own status.
STATUS = "status"


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
        # The broker sets the status offline if the Bridge goes without disconnecting.
        self._client.will_set(f"{self._prefix}/{STATUS}", "offline", qos=1, retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.reconnect_delay_set(max_delay=60)
        # Set once the broker has answered the first connect, accepting it or not.
        self._connect_answered = threading.Event()
        # Why the broker refused the last connect, until it accepts one.
        self._refusal: str | None = None
        # Guards what paho's network thread shares with the Bridge's: the last payloads, and these.
        self._lock = threading.Lock()
        self._online = False
        # Topics cleared while disconnected. The reconnect clears them at the broker.
        self._cleared_offline: set[str] = set()

    def connect(self) -> None:
        """Connect to the broker. Raises OSError if it can't be reached or refuses; after that, paho reconnects on its own."""
        self._client.connect(self._settings.mqtt_host, self._settings.mqtt_port)
        self._client.loop_start()
        if not self._connect_answered.wait(ACK_TIMEOUT) or self._refusal is not None:
            self._client.loop_stop()
            raise OSError(self._refusal or "the broker didn't answer")

    def disconnect(self) -> None:
        """Publish the status offline, then disconnect cleanly, so the broker doesn't send the Last Will."""
        self.publish_changes({STATUS: "offline"})
        self._client.disconnect()
        self._client.loop_stop()

    def publish_changes(self, payloads: dict[str, str | None]) -> set[str]:
        """Publish each payload, by topic path after the prefix, whose topic last had a different one.

        None is a value without a payload: its topic, if it has one, is cleared with
        an empty retained payload. An empty payload clears the topic at the broker
        too, so it counts as None.

        Waits until the broker has acknowledged them, so a round is complete when it returns.
        Returns the paths it published.
        """
        changed = {}
        with self._lock:
            for path, payload in payloads.items():
                payload = payload or None
                if self._published.get(path) == payload:
                    continue
                changed[path] = payload
                if payload is None:
                    del self._published[path]
                else:
                    self._published[path] = payload
            sent = self._send(changed)
        self._wait(sent)
        LOGGER.debug("published %d of %d values", len(changed), len(payloads))
        return set(changed)

    def republish(self, wanted: Callable[[str], bool]) -> None:
        """Publish the last payload again on every topic whose path is wanted. Waits like `publish_changes`."""
        with self._lock:
            payloads = {path: payload for path, payload in self._published.items() if wanted(path)}
            sent = self._send(payloads)
        self._wait(sent)
        LOGGER.debug("republished %d values", len(payloads))

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.ConnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None,
    ) -> None:
        """Set the status online and publish every last payload, which a restarted broker has forgotten."""
        if reason_code.is_failure:
            if self._refusal is None and self._connect_answered.is_set():
                LOGGER.warning("MQTT broker %s:%s refuses the reconnect: %s", *self._address(), reason_code)
            self._refusal = str(reason_code)
            self._connect_answered.set()
            return
        self._refusal = None
        # paho sends what was in flight when the connection dropped again after this callback,
        # which would overwrite the newer payloads below. Every last payload goes out here anyway.
        with client._out_message_mutex:
            client._out_messages.clear()
        with self._lock:
            self._online = True
            self._published[STATUS] = "online"
            payloads = dict.fromkeys(self._cleared_offline) | self._published
            self._cleared_offline.clear()
            # No waiting for acknowledgements here: this runs in paho's network thread, which receives them.
            self._send(payloads)
        if self._connect_answered.is_set():
            LOGGER.info("reconnected to MQTT broker %s:%s", *self._address())
        else:
            LOGGER.info("connected to MQTT broker %s:%s", *self._address())
            self._connect_answered.set()

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: mqtt.DisconnectFlags,
        reason_code: ReasonCode,
        properties: Properties | None,
    ) -> None:
        """Note the connection is gone, and log it once if it wasn't the Bridge that disconnected."""
        with self._lock:
            was_online, self._online = self._online, False
        if was_online and reason_code.is_failure:
            LOGGER.warning("lost the connection to MQTT broker %s:%s (%s). Reconnecting.", *self._address(), reason_code)

    def _address(self) -> tuple[str, int]:
        return self._settings.mqtt_host, self._settings.mqtt_port

    def _send(self, payloads: Mapping[str, str | None]) -> list[mqtt.MQTTMessageInfo]:
        """Hand the payloads to paho to publish. Call with the lock held.

        While disconnected, nothing is sent: the reconnect publishes every last payload
        anyway, so queueing would only pile up messages during a long outage.
        """
        if not self._online:
            self._cleared_offline |= {path for path, payload in payloads.items() if payload is None}
            return []
        return [
            self._client.publish(f"{self._prefix}/{path}", payload or "", qos=1, retain=True)
            for path, payload in payloads.items()
        ]

    def _wait(self, sent: list[mqtt.MQTTMessageInfo]) -> None:
        """Wait until the broker has acknowledged these, or it's taking too long. Not in paho's network thread."""
        deadline = time.monotonic() + ACK_TIMEOUT
        for info in sent:
            try:
                info.wait_for_publish(max(deadline - time.monotonic(), 0))
            except (RuntimeError, ValueError):
                pass
