# 03: SHI Inputs and Holdings published

**What to build:** Next to the CFI Calculations, a user sees the SHI's view: every SHI Input and Holding that has a value on this installation appears as a retained topic, for example `luxtronik/shi/inputs/heatpump_status` → `VD1 running` and `luxtronik/shi/holdings/hot_water_setpoint` → `40.0`.

The SHI is polled on its own interval, `LUX_SHI_POLL_INTERVAL` (default 30 s, minimum 2 s), independent of the CFI. Fields that have no value (such as unconfigured mixing circuits `mc1..3_*`) are not published. If a published field later reads as no value, its retained topic is cleared with an empty retained payload. The same payload rules and publish-on-change behaviour as ticket 02 apply.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [x] With the fixture loaded, a subscriber receives retained `luxtronik/shi/inputs/<name>` and `luxtronik/shi/holdings/<name>` topics for every field that has a value.
- [x] No topic exists for fields that have no value, for example `mc1_heat_mode`.
- [x] When the fake changes a published SHI field to no value, its retained topic is cleared.
- [x] CFI and SHI poll on their own intervals: with different intervals set, each interface is read on its own schedule on the injected clock.
- [x] `LUX_SHI_POLL_INTERVAL` below 2 stops the Bridge at startup with a message naming the variable.

## Comments

**2026-10-26, implementation:**
- The Bridge now runs one poll per interface (`_Poll` in `bridge.py`), each with its own interval and due time on the injected clock. `LUX_SHI_PORT` (default 502, from the spec's ENV contract) is wired through as well.
- SHI fields the library names `unknown_input_*` and `unknown_holding_*` (lowercase on the SHI) are left out by default, like the CFI's `Unknown_*` (spec, Selection defaults). Ticket 04's include patterns need to be able to switch both on.
- A field that loses its value has its retained topic cleared with an empty retained payload. This applies to CFI Calculations as well as to SHI fields, so both behave the same. An empty payload from the library counts as no value, since publishing it would clear the topic at the broker anyway.
- The fake Controller sets a SHI field to no value with `set(vector, name, None)`, which removes its registers from the dump. The SHI answers reads in blocks of registers, so the fields that share that block lose their value too, as they would on a real Controller.
- `heatpump_status` and `heatpump_vd1_status` etc. share one register, so setting `heatpump_status` to `VD1 running` also turns `heatpump_vd1_status` to `1`.
- If the Inputs read and the Holdings read fail in one SHI round, nothing from that round is published. An unreachable SHI is still logged on every poll (ticket 06).
- 2026-10-26, with the maintainer's permission: the Bridge ran read-only against the maintainer's Controller (V3.92.1) and a local mosquitto for 17 s, polling both interfaces every 5 s. It sent only the CFI read-Calculations command (3004) and Modbus reads (function codes 03 and 04), no writes. The first SHI poll published 64 topics, 45 Inputs and 19 Holdings, none of them `mc1..3_*` or `unknown_*`, with readable values such as `heatpump_status` → `Idle`, `hot_water_setpoint` → `40.0`, `lock_heating` → `Off`, `version` → `3.92.1`. The next three SHI polls published nothing, as no SHI value changed, while the CFI polls published 5 to 7 changes each. No warnings or errors were logged.

