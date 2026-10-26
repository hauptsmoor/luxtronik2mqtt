# Testing

Read this before writing or debugging a test. The rules for what a good test checks are in the spec's Testing Decisions (`.scratch/bridge-v1/spec.md`); this file covers the MQTT gotchas that broke tests during v1.

## The retained flag

Under MQTT 3.1.1 the broker sets the retained flag only on messages it sends because of a subscription. A retained message published while a subscriber is connected arrives with `retain=0`. So:

- `retained(port)` in `tests/harness.py` asserts every message is retained. Use it for a Bridge the test steps with `run_pending`, or one it has stopped: nothing publishes while the subscriber connects.
- `latest(port)` takes the last payload per topic, retained or not. Use it, inside `wait_until`, for anything that publishes on its own in real time: a Bridge in its own process (`bridge_process` in `tests/test_status.py`), the Last Will, paho reconnecting after a broker restart.
- On the Bridge side, a retained `/set` arrives unmarked when it is published while the Bridge is connected, and marked only on later (re)subscribes.

A test that is green locally and red on CI, with a sync or startup timeout, is usually `retained` used on a Bridge that publishes in real time.

## Many retained topics

With Visibilities included and their `meta` topics, a late subscriber gets over 1,000 retained messages. Mosquitto drops queued messages above 1,000 by default, so the test broker sets `max_queued_messages 0`. Keep that line when changing the broker config in `Broker`.

## Time

- **Injected clock:** a Bridge from `running_bridge` uses `FakeClock`. Move it with `clock.advance` and call `bridge.run_pending()`. Tests on intervals, republish and back-off use this and never sleep.
- **Real time:** what happens outside `run_pending` (paho's network thread, Commands, a Bridge process) runs in real time. Wait for it with `Subscriber.wait_for(topic)` or `wait_until(...)`, both bounded by `TIMEOUT`.
