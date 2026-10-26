# Spec: luxtronik2mqtt Bridge v1

Status: done

## Problem Statement

I run an Alpha Innotec / Novelan heat pump with a Luxtronik 2.1 Controller. Its values (temperatures, operating states, run hours, energy) are locked inside the Controller: there's no simple way to get them into Node-RED, my own Python applications or Telegraf/InfluxDB. I also want to steer the heat pump from my own control application later, through the Controller's Smart Home Interface (SHI), without putting the heat pump at risk from permanent settings changes.

Existing projects don't fit. The Home Assistant integration is tied to Home Assistant. minichma/luxtronik-mqtt-bridge uses the WebSocket interface, doesn't use the SHI, writes permanent settings, needs config files plus a state directory, and requires MQTT 5. The other bridges are inactive.

Other Luxtronik owners have installations that differ from mine, so whatever I build has to work on their Controllers without hand-curated value lists. And it has to be easy to run: one Docker image, configured only through environment variables.

## Solution

A Bridge: one Docker container per Controller. It reads the Controller through the CFI (port 8889) and the SHI (port 502), publishes every relevant value to an MQTT broker as its own retained topic with a plain payload, and, only when explicitly switched on, accepts Commands that set SHI Holdings (ADR 0001).

It works with zero configuration beyond the Controller's address and the broker. Users narrow or extend the published values with include/exclude patterns that look exactly like the topic paths. Values are converted to readable form (°C, mode names, `1`/`0`, ISO 8601 UTC timestamps), and each value has a retained metadata topic with its unit and type. Status topics show separately whether the Bridge, the CFI and the SHI are up. The image is multi-architecture, published to GHCR, and MIT-licensed.

## User Stories

### Getting started

1. As a heat-pump owner, I want to start the Bridge with only the Controller's address and my broker's address, so that I see values in MQTT within a minute without writing any configuration.
2. As a heat-pump owner, I want a single Docker image I can pull from GHCR, so that I don't have to build anything myself.
3. As a Raspberry Pi user, I want the image to run on arm64 and armv7 as well as amd64, so that I can run it on the hardware next to my heat pump.
4. As a heat-pump owner, I want the container to need no writable volume, so that it runs standalone and survives being recreated without losing anything.
5. As a security-minded user, I want the container to run as a non-root user, so that a bug in the Bridge can't take over the host.
6. As a heat-pump owner, I want a clear error at startup when a required setting is missing or invalid (for example a poll interval below 2 s), so that I don't get a silently misbehaving Bridge.
7. As a heat-pump owner, I want the README to list every ENV variable with its default and an example `docker run` / Compose snippet, so that I can set it up from the docs alone.

### Reading values

8. As a Node-RED user, I want one MQTT topic per value with a plain payload (for example `luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL` → `38.3`), so that I can subscribe to exactly the values a flow needs.
9. As a Node-RED user, I want every value topic retained, so that a flow that starts later gets the current value straight away.
10. As a heat-pump owner, I want all known CFI Calculations published by default, so that I see everything my Controller measures without knowing the field names in advance.
11. As a heat-pump owner, I want `Unknown_*` fields and known noise (such as the per-character `ID_WEB_SoftStand_0` to `_9` fields) left out by default, so that my broker isn't cluttered with meaningless topics.
12. As a heat-pump owner, I want all SHI Inputs and Holdings that have a value published by default, so that I see the SHI's view and the current control state without configuration.
13. As a heat-pump owner, I want SHI fields the Controller doesn't provide (for example unconfigured mixing circuits, which read as no value) left out, so that topics only exist for things my installation has.
14. As a heat-pump owner, I want CFI Parameters and Visibilities off by default and switchable with include patterns, so that I can add, for example, the hot-water setpoint Parameters without publishing about 1,600 values.
15. As a heat-pump owner, I want include and exclude patterns that are globs on the topic path after the prefix (for example `LUX_INCLUDE=cfi/parameters/ID_Einst_BWS_*`), so that I can copy a topic from MQTT Explorer straight into my configuration.
16. As a heat-pump owner, I want include patterns to add to the defaults rather than replace them, so that adding one Parameter doesn't make all my Calculations disappear.
17. As a heat-pump owner, I want exclude patterns to always win over include patterns and defaults, so that I can remove a placeholder value like `ID_WEB_Temperatur_TWA` = `-50.0` from a missing sensor.
18. As a heat-pump owner, I want to be able to switch `Unknown_*` fields on with an include pattern, so that I can help research what they mean.
19. As a heat-pump owner, I want field names exactly as python-luxtronik names them (German CFI IDs, English SHI names), so that they match forum posts and the library's docs.
20. As a heat-pump owner, I want temperatures, powers, energies and durations published as converted numbers (°C, kW, kWh, hours) rather than raw controller integers, so that I can use them directly.
21. As a Node-RED user, I want modes and states published as readable text (for example `heating`, `VD1 running`, `Off`), so that my flows compare against meaningful values instead of magic numbers.
22. As a Telegraf/Grafana user, I want booleans published as `1`/`0`, so that I can graph compressor runtime as a step line and sum it without conversion.
23. As a heat-pump owner, I want timestamps published as ISO 8601 in UTC with the zone marked (for example `2026-10-25T20:58:51Z`), so that they're unambiguous whatever time zone my container runs in.
24. As a heat-pump owner, I want IP addresses, version strings and fault texts published as readable text, so that I can read them without decoding.
25. As a heat-pump owner, I want each published value to have a retained `…/<name>/meta` topic with JSON describing its unit, type, whether it's writable and, for modes, the allowed options, so that I can label dashboards and know what a Command may contain.
26. As a future Home Assistant integrator, I want the metadata to carry enough information to generate Home Assistant Discovery later, so that Discovery can be added without changing the topic layout.

### Timing

27. As a heat-pump owner, I want the CFI and the SHI polled every 30 s by default, so that the Controller isn't stressed and my broker isn't flooded.
28. As a developer of my own control application, I want to set the CFI and SHI poll intervals separately, down to 2 s, so that I get fine-grained SHI data without reading about 1,500 CFI values every 2 s.
29. As a heat-pump owner, I want a changed value published straight after the poll that saw the change, so that my flows react quickly.
30. As a Telegraf user, I want every published value republished in full at a fixed interval (5 min by default, configurable), so that my time series has regular points even when a value doesn't change.
31. As a heat-pump owner, I want unchanged values not republished on every poll, so that the broker and InfluxDB don't fill with duplicates.

### Status and failures

32. As a heat-pump owner, I want a retained `<prefix>/status` topic that reads `online` while the Bridge runs and switches to `offline` automatically through MQTT Last Will if the Bridge dies, so that I can alert on a dead Bridge.
33. As a heat-pump owner, I want separate retained `<prefix>/cfi/status` and `<prefix>/shi/status` topics, so that "Bridge down", "Controller unreachable" and "SHI not available" look different.
34. As a Node-RED user, I want the last retained values kept when the Controller is unreachable, with the status switching to `offline`, so that dashboards keep showing the last known state, marked as stale.
35. As a heat-pump owner, I want the Bridge to keep running and retry an unreachable Controller with increasing delays (5 s up to 60 s), so that it recovers on its own after a network blip or Controller reboot.
36. As a heat-pump owner, I want all selected values republished in full once the Controller is reachable again, so that every consumer is back in sync straight away.
37. As an owner of an older Controller (firmware below V3.90.1, or SHI not switched on), I want the Bridge to detect that the SHI is unreachable, log one clear warning and run with the CFI only, so that I still get all CFI values.
38. As a heat-pump owner who switches the SHI on later, I want the Bridge to retry the SHI regularly and pick it up without a restart, so that I don't have to redeploy.
39. As a heat-pump owner, I want the Bridge to reconnect to the broker on its own after a broker restart, and to republish retained state and status after reconnecting, so that a broker update doesn't need a Bridge restart.
40. As a heat-pump owner, I want logs on stdout with a level set by `LUX_LOG_LEVEL`, so that `docker logs` shows what's happening and I can turn on debug output when something's wrong.
41. As a heat-pump owner, I want connection problems logged once when they start and once when they recover, not on every retry, so that my logs stay readable during a long outage.

### Commands

42. As a heat-pump owner, I want Commands switched off by default, so that nobody can change my heat pump through MQTT unless I've decided to allow it.
43. As a developer of my own control application, I want one switch, `LUX_SHI_WRITE=true`, that allows Commands for every writable Holding, so that I don't have to maintain an allowlist.
44. As a developer of my own control application, I want to send a Command by publishing a plain value to `<prefix>/shi/holdings/<name>/set` (for example `hot_water_setpoint/set` → `45`, `lock_heating/set` → `On`), so that controlling the heat pump is as simple as reading it.
45. As a developer of my own control application, I want mode Commands to use the same readable text the Bridge publishes (for example `Setpoint`), so that I read and write the same vocabulary.
46. As a developer of my own control application, I want the Bridge to read the Holding back straight after writing and publish the value read back on the normal Holding topic, so that the topic always shows what the Controller actually applied, not what I asked for.
47. As a heat-pump owner, I want retained messages on `/set` topics rejected, so that an old Command sitting at the broker can't run again after a Bridge or broker restart.
48. As a developer of my own control application, I want a short, non-retained message on `<prefix>/shi/holdings/<name>/error` when a Command is rejected or fails, so that my application can tell that a Command didn't take effect and why.
49. As a heat-pump owner, I want Commands rejected with an error when Commands are switched off, when the name isn't a writable Holding, when the Holding has no value on this installation, when the value can't be converted, or when the SHI is unreachable, so that every unexpected case gives feedback instead of silence.
50. As a developer of my own control application, I want value conversion and range enforcement left to python-luxtronik and the Controller, with the read-back showing what was applied, so that the Bridge doesn't carry its own, possibly wrong, limits.
51. As a heat-pump owner, I want the Bridge never to write CFI Parameters, so that no MQTT message can make a permanent, flash-wearing change to my Controller (ADR 0001).
52. As a developer of my own control application, I want the Bridge not to reapply Holdings after a Controller reboot, and to publish the Holdings it reads back (now at their defaults), so that my application sees the reset and decides itself what to send again.

### MQTT connection

53. As a heat-pump owner, I want to set the broker host, port, username and password through ENV, so that the Bridge works with my secured broker.
54. As an owner of a remote or community broker, I want optional TLS (`LUX_MQTT_TLS=true`) using the system CA certificates, with an optional `LUX_MQTT_CA_FILE` for a custom CA mounted read-only, so that I can connect securely.
55. As a heat-pump owner, I want the Bridge to use MQTT 3.1.1, so that it works with any broker.
56. As an owner of two heat pumps, I want to set the topic prefix (`LUX_MQTT_PREFIX`, default `luxtronik`) and run two Bridges against one broker, so that their topics don't collide.

### Testing and contributing

57. As a contributor, I want the test suite to run without a heat pump, against a recorded dump of a real Controller, so that I can work on the Bridge anywhere and CI can run the tests.
58. As an owner of a different Controller, I want a read-only way to capture my Controller's dump with network details replaced by placeholders, so that I can contribute it as a test fixture and help the Bridge support my installation.
59. As a maintainer, I want every pull request to run the test suite in GitHub Actions, so that regressions are caught before release.
60. As a maintainer, I want pushing a `vX.Y.Z` tag to build the multi-architecture image and publish it to GHCR, so that releasing takes one command.

### Documentation

61. As a Telegraf user, I want an example `mqtt_consumer` configuration in the README that parses the topic path into measurement and field names, so that I can feed values into InfluxDB without working it out myself.
62. As a heat-pump owner, I want the README to explain how to switch the SHI on at the Controller (*Service → Systemsteuerung → Konnektivität → Smart-Home-Interface*) and which firmware it needs, so that I know why the SHI might show `offline`.
63. As a heat-pump owner, I want the README to warn that SHI Holdings are forgotten on Controller reboot and that frequent lock switching wears the compressor, so that I use Commands responsibly.

## Implementation Decisions

### Interfaces to the Controller

- The Bridge reads from both the CFI and the SHI and writes only SHI Holdings (ADR 0001). There is no write path to CFI Parameters at all.
- python-luxtronik is a dependency pinned to one master commit from GitHub, because SHI support exists only on master (ADR 0002). It was verified read-only against a real Controller on V3.92.1 at commit `02afea84bd5bf3ee87445de6f2a42b8029983169`. The Bridge uses MQTT 3.1.1 through `paho-mqtt` 2.x, with no MQTT 5 option.

### Modules

- **Controller adapter** (the test seam): the only module that imports python-luxtronik. Its interface is small:
  - read the CFI: Calculations, Parameters and Visibilities as library data vectors;
  - read the SHI: Inputs and Holdings;
  - write one Holding by name and value, returning the value read back;
  - report the firmware version.

  An unreachable CFI or SHI comes back as an explicit "unreachable" result or exception, never as a silent `None`. The library's CFI interface logs connection errors and returns `None`, and has no connect timeout of its own, so the adapter sets its own timeouts and turns that into a clear signal. CFI and SHI access stay serialised per interface, matching the library's own locking, since the Controller is known to be unstable under concurrent socket use.
- **Configuration**: parses and validates the ENV into one settings object at startup, and fails fast with a message naming the bad variable.
- **Selection**: decides from the defaults, the built-in noise list and the include/exclude patterns whether a given topic path is published. A pure function of path and settings.
- **Formatting**: turns a library field into its payload string and its `meta` JSON, following the payload rules below.
- **Publishing**: remembers the last published payload per topic, publishes changes, republishes everything on the republish interval and after the Controller or broker comes back, and keeps the status topics up to date.
- **Commands**: subscribes to `<prefix>/shi/holdings/+/set`, checks the rules, writes through the adapter, publishes the read-back or the error.
- **Scheduler**: drives the CFI poll, SHI poll, republish and retry back-off from an injectable clock.
- **Entry point**: wires everything together, connects to MQTT with Last Will and TLS, and shuts down cleanly on SIGTERM by publishing `offline`.
- **Dump capture**: a read-only command shipped in the image that reads every CFI and SHI vector from a Controller, replaces network details with placeholders, and writes a fixture file to stdout.

### ENV contract

| Variable | Default | Notes |
|---|---|---|
| `LUX_HOST` | (required) | Controller address |
| `LUX_CFI_PORT` | `8889` | |
| `LUX_SHI_PORT` | `502` | |
| `LUX_CFI_POLL_INTERVAL` | `30` | seconds, minimum `2` |
| `LUX_SHI_POLL_INTERVAL` | `30` | seconds, minimum `2` |
| `LUX_REPUBLISH_INTERVAL` | `300` | seconds |
| `LUX_INCLUDE` | (empty) | comma-separated globs on the topic path after the prefix; adds to the defaults |
| `LUX_EXCLUDE` | (empty) | same syntax; always wins |
| `LUX_SHI_WRITE` | `false` | `true` allows Commands for every writable Holding |
| `LUX_MQTT_HOST` | (required) | |
| `LUX_MQTT_PORT` | `1883` | |
| `LUX_MQTT_USERNAME` / `LUX_MQTT_PASSWORD` | (empty) | |
| `LUX_MQTT_TLS` | `false` | system CA certificates |
| `LUX_MQTT_CA_FILE` | (empty) | optional custom CA, mounted read-only |
| `LUX_MQTT_PREFIX` | `luxtronik` | |
| `LUX_LOG_LEVEL` | `INFO` | |

### Topic contract (paths after `<prefix>/`)

| Topic | Retained | Payload |
|---|---|---|
| `status` | yes | `online` / `offline` (Last Will sets `offline`) |
| `cfi/status`, `shi/status` | yes | `online` / `offline` |
| `cfi/calculations/<name>`, `cfi/parameters/<name>`, `cfi/visibilities/<name>` | yes | value |
| `shi/inputs/<name>`, `shi/holdings/<name>` | yes | value |
| `<any value topic>/meta` | yes | JSON: `unit`, `type`, `writable`, `options` (for modes) |
| `shi/holdings/<name>/set` | subscribed; retained messages rejected | value in the same form as published |
| `shi/holdings/<name>/error` | no | short text reason |

- `<name>` is the library's canonical field name, unchanged. Renames in a library update change topics and are called out in the release notes.

### Payload rules

- Numbers: converted by the library into display units (°C, K, kW, kWh, hours and so on), published as plain decimal text.
- Modes, states, fault codes: the library's readable text.
- Booleans: `1` / `0`.
- Timestamps: ISO 8601 UTC with `Z`, derived from the raw epoch value rather than from the library's local-time string.
- IP addresses, version strings: readable text.

### Selection defaults

- Published: all CFI Calculations, except `Unknown_*` and a small built-in noise list (initially the per-character `ID_WEB_SoftStand_<n>` fields); all SHI Inputs and Holdings that have a value.
- Not published unless included: CFI Parameters, CFI Visibilities, `Unknown_*`.
- Visibilities are not used for filtering. python-luxtronik has no mapping from Visibilities to Calculations or Parameters, and the flags are known to be unreliable.

### Command flow

1. A message arrives on `shi/holdings/<name>/set`.
2. It's rejected with an error if any of these holds:
   - it's retained;
   - Commands are switched off;
   - `<name>` isn't a writable Holding;
   - the Holding has no value on this installation;
   - the SHI is unreachable;
   - the library can't convert the payload.
3. Otherwise the Bridge writes it through the adapter and reads the Holding back.
4. The value read back is published on `shi/holdings/<name>` straight away, outside the normal poll.
5. If the write fails, or the value read back differs from the requested one, an error is published as well. The read-back is still what's published on the Holding topic.

The Bridge never retries a Command on its own, and never reapplies Holdings after a Controller reboot.

### Packaging and release

- Slim Python base image, non-root user, no writable volume. The image works with a read-only root filesystem.
- GitHub Actions: run the tests on every pull request. A `vX.Y.Z` tag builds amd64, arm64 and armv7 and pushes to `ghcr.io/<owner>/luxtronik2mqtt`.
- MIT license (python-luxtronik is MIT too).

## Testing Decisions

- **One seam: the Controller adapter.** Tests replace it with a fake Controller built from a recorded fixture of a real Controller. The fake builds real python-luxtronik data vectors from the fixture's raw values, so the library's own conversions (units, mode names, timestamps) are exercised in tests. It also lets a test:
  - change values between polls;
  - make the CFI or SHI unreachable, and reachable again;
  - accept a Holding write, reject it, or apply a different value, so read-back divergence can be tested.
- **No seam on the MQTT side.** Tests run against a real MQTT 3.1.1 broker started inside the test. They configure the Bridge with an ENV dictionary and assert only on what an outside subscriber sees: retained topics, payloads, `meta`, status topics including the Last Will, and Command behaviour.
- **Time is an input.** The scheduler takes an injectable clock, so poll intervals, the republish interval and retry back-off are tested without real waiting.
- **A good test** reads "given this ENV and Controller state, when this happens (poll, value change, outage, Command), these topics have these payloads". Tests don't call Selection, Formatting or Publishing directly. Those are covered through what ends up on the broker.
- **The first fixture** comes from the maintainer's Controller (Luxtronik 2.1, V3.92.1, captured read-only), with `ID_WEB_AdresseIP_akt`, the subnet mask, broadcast and gateway replaced by placeholders. Further fixtures from other Controllers can be added through the dump-capture command.
- **Prior art:** none in this repo yet; this is its first code. python-luxtronik's own test suite shows how it builds data vectors from raw values.
- Real-Controller checks are manual and read-only by default. The first real SHI write is done by the maintainer by hand. No automated test ever touches a real Controller.

## Out of Scope

- Writing CFI Parameters (setpoints, modes, timer schedules), including any allowlist for them.
- Home Assistant Discovery (the `meta` topics prepare for it).
- MQTT 5 and any option to switch to it.
- More than one Controller per Bridge.
- The WebSocket interface on port 8214.
- Publishing to Docker Hub.
- Remembering or reapplying Holdings after a Controller reboot; any on-disk state.
- The Bridge's own value-range limits for Commands.
- Parallel `/raw` topics with the raw numbers.
- Filtering by Visibilities, or a hand-maintained Calculation-to-Visibility mapping.
- A YAML or other configuration file.
- Curated English names for CFI fields.
- A Home Assistant add-on.

## Further Notes

- **SHI writes have not been tested on a real Controller yet.** The Holding names and current defaults were confirmed read-only on the maintainer's V3.92.1 Controller, where all Holding modes currently read `Off`/`Normal` and the `mc1..3_*` Holdings have no value.
- Measured read times on V3.92.1: a full CFI read takes about 0.25 s and a full SHI read about 1.0 s. That supports the 2 s minimum poll interval.
- A competing project reports port 8889 unavailable on firmware 3.92; on V3.92.1 it works fully, with live data. If users on other 3.92.x versions report CFI problems, CFI-only failure should degrade the same way SHI failure does (story 37).
- Assumption made while writing this spec, to be confirmed during implementation: if a published SHI field later reads as no value, its retained topic is cleared (empty retained payload) rather than left stale.
- Some SHI Holdings and Inputs need firmware V3.92.0 or later; the library handles this with its `since`/`until` gating, and those fields simply have no value on older firmware.
- The MQTT client ID is not part of the decided ENV contract; derive a default from the prefix so two Bridges don't collide.
