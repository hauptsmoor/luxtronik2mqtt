# 03: SHI Inputs and Holdings published

**What to build:** Next to the CFI Calculations, a user sees the SHI's view: every SHI Input and Holding that has a value on this installation appears as a retained topic, for example `luxtronik/shi/inputs/heatpump_status` → `VD1 running` and `luxtronik/shi/holdings/hot_water_setpoint` → `40.0`.

The SHI is polled on its own interval, `LUX_SHI_POLL_INTERVAL` (default 30 s, minimum 2 s), independent of the CFI. Fields that have no value (such as unconfigured mixing circuits `mc1..3_*`) are not published. If a published field later reads as no value, its retained topic is cleared with an empty retained payload. The same payload rules and publish-on-change behaviour as ticket 02 apply.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [ ] With the fixture loaded, a subscriber receives retained `luxtronik/shi/inputs/<name>` and `luxtronik/shi/holdings/<name>` topics for every field that has a value.
- [ ] No topic exists for fields that have no value, for example `mc1_heat_mode`.
- [ ] When the fake changes a published SHI field to no value, its retained topic is cleared.
- [ ] CFI and SHI poll on their own intervals: with different intervals set, each interface is read on its own schedule on the injected clock.
- [ ] `LUX_SHI_POLL_INTERVAL` below 2 stops the Bridge at startup with a message naming the variable.
