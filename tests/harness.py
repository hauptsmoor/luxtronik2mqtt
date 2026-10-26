"""The Bridge under test: a real MQTT broker, a subscriber watching it, and a clock tests move."""

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.enums import CallbackAPIVersion

from fake_controller import FakeController
from luxtronik2mqtt.bridge import Bridge
from luxtronik2mqtt.config import Settings
from peers import closed_port

TIMEOUT = 5.0
_SYNC_TOPIC = "test/sync"


def _mosquitto() -> str:
    """The mosquitto binary: from MOSQUITTO, the PATH, or where packages put it outside the PATH."""
    candidates = [os.environ.get("MOSQUITTO"), shutil.which("mosquitto")]
    candidates += ["/opt/homebrew/sbin/mosquitto", "/usr/local/sbin/mosquitto", "/usr/sbin/mosquitto"]
    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate
    raise RuntimeError(
        "The tests need the mosquitto MQTT broker: `brew install mosquitto` or `apt-get install mosquitto`, "
        "or set MOSQUITTO to its path."
    )


class Broker:
    """A mosquitto broker on localhost that a test can restart on the same port. It forgets everything on restart."""

    def __init__(self, config: Path) -> None:
        self.port = closed_port()
        self._config = config
        config.write_text(f"listener {self.port} 127.0.0.1\nallow_anonymous true\npersistence false\n")
        self._process = self._start()

    def restart(self) -> None:
        self.stop()
        self._process = self._start()

    def stop(self) -> None:
        self._process.terminate()
        self._process.wait(TIMEOUT)

    def _start(self) -> subprocess.Popen[bytes]:
        process = subprocess.Popen(
            [_mosquitto(), "-c", str(self._config)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _wait_until_listening(self.port, process)
        return process


@contextmanager
def restartable_broker() -> Iterator[Broker]:
    """A broker running until the block ends."""
    with tempfile.TemporaryDirectory() as directory:
        broker = Broker(Path(directory) / "mosquitto.conf")
        try:
            yield broker
        finally:
            broker.stop()


@contextmanager
def broker() -> Iterator[int]:
    """A mosquitto broker on localhost, running until the block ends. Yields its port."""
    with restartable_broker() as running:
        yield running.port


def _wait_until_listening(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        if process.poll() is not None:
            assert process.stderr is not None
            raise RuntimeError(f"mosquitto exited: {process.stderr.read().decode()}")
        try:
            socket.create_connection(("127.0.0.1", port), timeout=TIMEOUT).close()
            return
        except ConnectionRefusedError:
            time.sleep(0.01)
    raise RuntimeError(f"mosquitto didn't listen on port {port}")


@dataclass(frozen=True)
class Message:
    topic: str
    payload: str
    retained: bool


class Subscriber:
    """An outside MQTT client that subscribes to every topic and keeps what it receives."""

    def __init__(self, port: int) -> None:
        self.messages: list[Message] = []
        self._changed = threading.Condition()
        self._syncs = 0
        self._client = mqtt.Client(CallbackAPIVersion.VERSION2, client_id="test-subscriber", protocol=mqtt.MQTTv311)
        self._client.on_message = self._receive
        subscribed = threading.Event()
        self._client.on_subscribe = lambda client, userdata, mid, reason_codes, properties: subscribed.set()
        self._client.connect("127.0.0.1", port)
        self._client.subscribe("#", qos=1)
        self._client.loop_start()
        assert subscribed.wait(TIMEOUT), "the broker didn't confirm the subscription"

    def close(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()

    def sync(self) -> list[Message]:
        """Wait until everything the Bridge has published has arrived, and return what came in since the last sync.

        The Bridge waits for the broker to acknowledge each round, so a message
        this subscriber publishes now reaches it after all of them.
        """
        self._syncs += 1
        marker = str(self._syncs)
        self._client.publish(_SYNC_TOPIC, marker, qos=1)
        with self._changed:
            arrived = self._changed.wait_for(
                lambda: Message(_SYNC_TOPIC, marker, False) in self.messages, TIMEOUT
            )
            assert arrived, "the sync message didn't come back"
            received = [m for m in self.messages if m.topic != _SYNC_TOPIC]
            self.messages.clear()
        return received

    def _receive(self, client: mqtt.Client, userdata: object, message: mqtt.MQTTMessage) -> None:
        with self._changed:
            self.messages.append(Message(message.topic, message.payload.decode(), bool(message.retain)))
            self._changed.notify_all()


class FakeClock:
    """A clock that only moves when the test moves it."""

    def __init__(self) -> None:
        self.now = 1000.0

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def advance(self, seconds: float) -> None:
        self.now += seconds


@contextmanager
def running_bridge(env: Mapping[str, str], controller: FakeController, clock: FakeClock) -> Iterator[Bridge]:
    """The Bridge configured from this ENV, connected to its broker. The test drives it with `run_pending`."""
    bridge = Bridge(Settings.from_env(env), controller, clock)
    bridge.start()
    try:
        yield bridge
    finally:
        bridge.stop()


def env(port: int, **overrides: str) -> dict[str, str]:
    """The ENV for a Bridge talking to the broker on this port."""
    return {"LUX_HOST": "fake-controller", "LUX_MQTT_HOST": "127.0.0.1", "LUX_MQTT_PORT": str(port), **overrides}
