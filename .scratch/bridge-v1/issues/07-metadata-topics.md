# 07: Metadata topics

**What to build:** Next to each published value, a user can find out what it means. For every topic the Bridge publishes (CFI and SHI), it publishes a retained `…/<name>/meta` topic with a JSON document holding:
- `unit`: for example `°C`, or none;
- `type`: the library's data type name, for example `Celsius` or `HeatingMode`;
- `writable`: whether a Command can set it (true only for SHI Holdings);
- `options`: for modes, the list of allowed readable values.

The meta topic is published when its value topic first appears, and cleared when the value topic is cleared. It carries enough information to generate Home Assistant Discovery later.

**Blocked by:** 03 (SHI Inputs and Holdings published)

**Status:** ready-for-agent

- [ ] `luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL/meta` holds unit `°C`, type `Celsius` and `writable` false.
- [ ] `luxtronik/shi/holdings/hot_water_mode/meta` holds `writable` true and its allowed modes in `options`.
- [ ] Every published value topic has a matching retained meta topic, and no meta topic exists for unpublished values.
- [ ] When a value topic is cleared (see ticket 03), its meta topic is cleared too.
- [ ] Meta topics are not republished on every poll, only when their content changes, and with the full republish from ticket 05 once that's in.
