# 04: Include/exclude patterns

**What to build:** A user can tailor what the Bridge publishes with two ENV variables, copying topic paths straight from MQTT Explorer. `LUX_INCLUDE` and `LUX_EXCLUDE` are comma-separated globs on the topic path after the prefix, such as `cfi/parameters/ID_Einst_BWS_*` or `cfi/calculations/ID_WEB_Temperatur_TWA`.
- `LUX_INCLUDE` adds to the defaults; it never replaces them.
- `LUX_EXCLUDE` always wins, over both defaults and includes.

Patterns apply to every topic path, CFI and SHI alike. This is how users switch on CFI Parameters, CFI Visibilities and `Unknown_*` fields, and remove placeholder values from missing sensors.

**Blocked by:** 03 (SHI Inputs and Holdings published)

**Status:** ready-for-agent

- [ ] `LUX_INCLUDE=cfi/parameters/ID_Einst_BWS_*` publishes the matching Parameters, and all default Calculations and SHI fields are still published.
- [ ] `LUX_INCLUDE=cfi/visibilities/*` publishes Visibilities.
- [ ] `LUX_INCLUDE=cfi/calculations/Unknown_*` publishes the `Unknown_*` Calculations.
- [ ] `LUX_EXCLUDE=cfi/calculations/ID_WEB_Temperatur_TWA` removes that topic.
- [ ] An exclude removes an SHI topic, for example `shi/inputs/*`.
- [ ] A path that matches both an include and an exclude is not published.
- [ ] Whitespace around commas is ignored; an empty variable means no patterns.
