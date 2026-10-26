# 05: Regular full republish

**What to build:** A Telegraf user gets regular data points even for values that never change. Every `LUX_REPUBLISH_INTERVAL` seconds (default 300), the Bridge republishes every currently selected value, whether or not it changed. Between republishes, publish-on-change from ticket 02 stays as it is.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [x] With no value changes, a subscriber receives every selected topic again once the republish interval passes on the injected clock, and not before.
- [x] Polls between republishes publish only changed values.
- [x] `LUX_REPUBLISH_INTERVAL` changes the interval; an invalid value stops the Bridge at startup with a message naming the variable.
- [x] Once ticket 03 is in, the republish includes SHI values as well.

## Comments

**2026-10-26, implementation:**
- A republish resends the last payload the Publisher sent on each topic (`Publisher.republish`), straight when the interval passes, without an extra read from the Controller. The broker-reconnect republish in ticket 06 can reuse it.
- The republish interval counts from the first poll, like the poll intervals, so when it falls on a poll both run in the same `run_pending`. A topic that poll just published isn't sent a second time by the republish.
- Values of an interface whose last poll found it unreachable are not republished, so a time series doesn't get stale points that look fresh during an outage. Ticket 06 adds the status topics and the full republish on recovery.
- A topic cleared to no value has nothing to republish.
- `LUX_REPUBLISH_INTERVAL` is checked like the poll intervals: a number of seconds, at least 2. The spec gives no minimum; this one keeps a typo such as `0` from flooding the broker.
- `_Poll` in `bridge.py` became `_Job`, which runs the polls and the republish alike.
- Not run against the real Controller in this ticket.
