# 06: Status topics and outage recovery

**What to build:** A user can always tell what's working, and the Bridge looks after itself through outages.

- **Status topics** (retained, `online`/`offline`):
  - `<prefix>/status` for the Bridge itself, set to `offline` by MQTT Last Will if the Bridge dies and published as `offline` on a clean SIGTERM shutdown;
  - `<prefix>/cfi/status` and `<prefix>/shi/status` for each interface.
- **Controller outage:** when the CFI or SHI becomes unreachable, its status goes `offline` and the retained values stay as they are. The Bridge retries with growing delays (5 s up to 60 s). Once the interface is back, its status goes `online` and every selected value from it is republished in full.
- **No SHI:** if the SHI is unreachable at startup (old firmware, or SHI switched off), the Bridge logs one clear warning, runs CFI-only, and keeps retrying the SHI so it's picked up without a restart.
- **Broker outage:** the Bridge reconnects to the broker on its own, then republishes the status topics and all retained values.
- **Logging:** logs go to stdout at `LUX_LOG_LEVEL` (default `INFO`). A connection problem is logged once when it starts and once when it recovers, not on every retry.

**Blocked by:** 03 (SHI Inputs and Holdings published)

**Status:** done

- [x] While the Bridge runs, `status`, `cfi/status` and `shi/status` are retained `online`.
- [x] When the Bridge's MQTT connection drops without a clean disconnect, the broker publishes `status` → `offline` through the Last Will.
- [x] On SIGTERM, the Bridge publishes `status` → `offline` before it exits.
- [x] Making the fake CFI unreachable sets `cfi/status` → `offline`, and the retained Calculation topics keep their last values.
- [x] Retries during an outage follow growing delays from 5 s up to 60 s on the injected clock.
- [x] When the fake CFI is reachable again, `cfi/status` → `online` and every selected CFI topic is republished.
- [x] With the SHI unreachable from startup, CFI values are still published, `shi/status` is `offline`, and exactly one warning is logged.
- [x] When the SHI later becomes reachable, its values are published without a restart.
- [x] After a broker restart, the Bridge reconnects and the status topics and retained values are back.
- [x] A long outage logs one message at the start and one at recovery, not one per retry.

## Comments

**2026-10-26, implementation:**
- The Publisher owns `status`: `online` when the broker accepts the connection (on reconnects too), `offline` through the Last Will, and `offline` on a clean stop (`Bridge.stop`, which `main` runs on SIGTERM). The Bridge sets `cfi/status` and `shi/status` from each poll, since it is the one that knows whether an interface answered. All three are kept like any other last payload, so the regular republish and the broker-reconnect republish include them. A status is never stale, so it is republished even while its interface is unreachable.
- An unreachable interface is retried after 5 s, then after double the last delay, up to 60 s (`FIRST_RETRY`, `LONGEST_RETRY` in `bridge.py`). A poll can now return the delay until it is next due (`_Job`). On recovery it goes back to its poll interval, counted from the successful retry.
- Logging: the first failure is a warning, each retry is logged at DEBUG, and recovery is logged at INFO ("CFI answers again"). An SHI that doesn't answer before it has ever answered gets a warning naming the firmware (V3.90.1) and the switch at the Controller. The MQTT side logs a lost connection once, and the reconnect once. A broker that refuses reconnects is logged once until it accepts one.
- `main` keeps the `luxtronik` library's logger at WARNING unless `LUX_LOG_LEVEL=DEBUG`. The library logs every CFI and SHI read at INFO, which would put two or three lines per poll in the default logs. Not in the ticket; it follows from "logs stay readable".
- While disconnected from the broker, the Publisher doesn't hand publishes to paho, which would queue them without limit during a long outage. It keeps the last payloads and sends them all on reconnect, together with empty payloads for the topics cleared in the meantime. The clearing part isn't covered by a test: the test broker forgets everything on restart, so only a network drop without a broker restart would show it.
- On reconnect, paho would send the QoS 1 messages that were in flight when the connection dropped again, after `on_connect` and so after the newer full republish. The Publisher drops them from paho's queue in `on_connect` (`client._out_messages`, a private attribute; paho is pinned below 3). A round that was waiting for their acknowledgements times out after `ACK_TIMEOUT`. Not covered by a test: it needs a message caught in flight at the moment the connection drops.
- `Publisher.connect` now waits for the broker's CONNACK and raises if the broker refuses, so bad credentials stop the Bridge at startup with a message. paho's broker reconnect delay is capped at 60 s, like the Controller retries.
- The broker still has to be reachable when the Bridge starts (ticket 02 left this for 06). Story 39 covers broker restarts only, so the Bridge exits 1 at startup and Docker's restart policy retries it.
- The harness has `restartable_broker()` for a broker that restarts on the same port, and the fake Controller counts read attempts per interface (`attempts`). The SIGTERM and Last Will tests run the `luxtronik2mqtt` command in its own process.
- Not run against the real Controller in this ticket.

**2026-10-26, maintainer:** keep exiting at startup when the broker is unreachable; Docker's restart policy covers it.
