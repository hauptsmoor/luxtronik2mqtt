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

**Status:** ready-for-agent

- [ ] With the fixture loaded, a subscriber receives retained `luxtronik/cfi/calculations/<name>` topics for all known Calculations, and none for `Unknown_*` or `ID_WEB_SoftStand_<n>`.
- [ ] Payloads follow the rules: `ID_WEB_Temperatur_TVL` → `38.3`, `ID_WEB_WP_BZ_akt` → `heating`, `ID_WEB_VD1out` → `1`, `ID_WEB_ERROR_Time0` → an ISO 8601 UTC timestamp with `Z`, `ID_WEB_AdresseIP_akt` → dotted text.
- [ ] The timestamp payload is the same whatever the process's time zone.
- [ ] After the fake changes one value and the clock moves one poll interval, only that topic is published again.
- [ ] Missing `LUX_HOST` or `LUX_MQTT_HOST`, or `LUX_CFI_POLL_INTERVAL` below 2, stops the Bridge at startup with a message naming the variable.
- [ ] `LUX_MQTT_PREFIX` changes the topic root.
- [ ] The Bridge can be started locally against a real Controller and broker, read-only.

## Comments

**2026-10-25, from ticket 01:** the first fixture was captured while the heat pump was idle, so it holds `ID_WEB_Temperatur_TVL` = `29.2`, `ID_WEB_WP_BZ_akt` = `no request` and `ID_WEB_VD1out` = `0`. The payload examples above (`38.3`, `heating`, `1`) need values that fit this fixture, or the test sets them first with the fake Controller's `set`.
