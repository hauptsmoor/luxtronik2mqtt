# 02: Tracer bullet: CFI Calculations to MQTT

**What to build:** A user starts the Bridge with only `LUX_HOST` and `LUX_MQTT_HOST` set and sees every known CFI Calculation appear in MQTT as its own retained topic, for example `luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL` → `38.3`, refreshed on each poll.

This slice cuts through every layer:
- **Configuration** from ENV, validated at startup, failing fast with a message that names the bad variable.
- **MQTT 3.1.1 connection** with optional username and password, and `LUX_MQTT_PREFIX` (default `luxtronik`).
- **CFI poll** on `LUX_CFI_POLL_INTERVAL` (default 30 s, minimum 2 s), driven by an injectable clock.
- **Selection defaults:** all known Calculations, minus `Unknown_*` and the built-in noise list (initially the per-character `ID_WEB_SoftStand_<n>` fields).
- **Payload rules** (see the spec):
  - converted numbers as plain decimal text;
  - modes, states and fault texts as readable text;
  - booleans as `1`/`0`;
  - timestamps as ISO 8601 UTC with `Z`, derived from the raw epoch value;
  - IP addresses and versions as readable text.
- **Publish on change:** a topic is published only when its payload differs from the last one published.

It also builds the test harness every later ticket uses: the Bridge configured with an ENV dictionary, the fake Controller from ticket 01, and a real MQTT 3.1.1 broker started inside the test. Tests check only what a subscriber sees.

**Blocked by:** 01 (Controller adapter, dump capture and first fixture)

**Status:** done

- [x] With the fixture loaded, a subscriber receives retained `luxtronik/cfi/calculations/<name>` topics for all known Calculations, and none for `Unknown_*` or `ID_WEB_SoftStand_<n>`.
- [x] Payloads follow the rules: after the test sets them with the fake Controller's `set` (the fixture was captured idle), `ID_WEB_Temperatur_TVL` → `38.3`, `ID_WEB_WP_BZ_akt` → `heating`, `ID_WEB_VD1out` → `1`; `ID_WEB_ERROR_Time0` → an ISO 8601 UTC timestamp with `Z`, `ID_WEB_AdresseIP_akt` → dotted text.
- [x] The timestamp payload is the same whatever the process's time zone.
- [x] After the fake changes one value and the clock moves one poll interval, only that topic is published again.
- [x] Missing `LUX_HOST` or `LUX_MQTT_HOST`, or `LUX_CFI_POLL_INTERVAL` below 2, stops the Bridge at startup with a message naming the variable.
- [x] `LUX_MQTT_PREFIX` changes the topic root.
- [x] The Bridge can be started locally against a real Controller and broker, read-only.

## Comments

**2026-10-25, from ticket 01:** the first fixture was captured while the heat pump was idle, so it holds `ID_WEB_Temperatur_TVL` = `29.2`, `ID_WEB_WP_BZ_akt` = `no request` and `ID_WEB_VD1out` = `0`. The payload examples above (`38.3`, `heating`, `1`) need values that fit this fixture, or the test sets them first with the fake Controller's `set`.

**2026-10-26, maintainer:** keep the idle fixture. Tests set `38.3`, `heating` and `1` with the fake Controller's `set` before the Bridge reads them.

**2026-10-26, implementation:**
- Modules: `config.py` (Settings from the ENV, ConfigError naming the variable), `selection.py` (defaults and the noise list as globs on the topic path, ready for ticket 04's patterns), `formatting.py` (payload from a library field without importing the library), `publishing.py` (paho 2.x, MQTT 3.1.1, QoS 1 retained, publish on change), `bridge.py` (the Bridge and its schedule, driven by an injectable clock through `run_pending`) and `main.py` (the `luxtronik2mqtt` command).
- The test harness is `tests/harness.py`: `broker()` starts mosquitto on a free port, `Subscriber` sees what an outside client sees, `FakeClock` moves only when the test moves it, `running_bridge(env, controller, clock)` runs the Bridge. `Subscriber.sync()` returns what arrived since the last sync; that relies on the Bridge waiting for the broker's acknowledgements each round.
- The tests need the mosquitto binary (`brew install mosquitto`, `apt-get install mosquitto`, or `MOSQUITTO=<path>`). amqtt was tried as an in-process broker and dropped: it delivered retained messages to subscribers that didn't match them, and twice to wildcard subscriptions.
- A Calculation without a value (`Desired_Room_Temperature` on V3.92.1) gets no topic. A timestamp with raw value 0 or less publishes as `1970-01-01T00:00:00Z`, as the library shows it.
- Left for later tickets: an unreachable CFI is logged on every poll (ticket 06 logs it once and sets the status), and the broker must be reachable at startup (ticket 06 / story 39).
- 2026-10-26, with the maintainer's permission: the Bridge ran read-only against the maintainer's Controller (V3.92.1) and a local mosquitto, polling every 5 s. It sent only the CFI read-Calculations command (3004). The first poll published 227 topics, none of them `Unknown_*` or `ID_WEB_SoftStand_<n>`, and the next two published only the 7 values that changed. `ID_WEB_AktuelleTimeStamp` read `2026-10-26T08:29:43Z` at 09:29 CET, so the Controller's raw timestamps are real UTC epochs and the conversion is right.
