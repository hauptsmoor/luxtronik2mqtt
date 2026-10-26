# 04: Include/exclude patterns

**What to build:** A user can tailor what the Bridge publishes with two ENV variables, copying topic paths straight from MQTT Explorer. `LUX_INCLUDE` and `LUX_EXCLUDE` are comma-separated globs on the topic path after the prefix, such as `cfi/parameters/ID_Einst_BWS_*` or `cfi/calculations/ID_WEB_Temperatur_TWA`.
- `LUX_INCLUDE` adds to the defaults; it never replaces them.
- `LUX_EXCLUDE` always wins, over both defaults and includes.

Patterns apply to every topic path, CFI and SHI alike. This is how users switch on CFI Parameters, CFI Visibilities and `Unknown_*` fields, and remove placeholder values from missing sensors.

**Blocked by:** 03 (SHI Inputs and Holdings published)

**Status:** done

- [x] `LUX_INCLUDE=cfi/parameters/ID_Einst_BWS_*` publishes the matching Parameters, and all default Calculations and SHI fields are still published.
- [x] `LUX_INCLUDE=cfi/visibilities/*` publishes Visibilities.
- [x] `LUX_INCLUDE=cfi/calculations/Unknown_*` publishes the `Unknown_*` Calculations.
- [x] `LUX_EXCLUDE=cfi/calculations/ID_WEB_Temperatur_TWA` removes that topic.
- [x] An exclude removes an SHI topic, for example `shi/inputs/*`.
- [x] A path that matches both an include and an exclude is not published.
- [x] Whitespace around commas is ignored; an empty variable means no patterns.

## Comments

**2026-10-26, implementation:**
- `Selection` in `selection.py` now holds the include and exclude patterns from `LUX_INCLUDE` and `LUX_EXCLUDE`. A path is published when no exclude matches it and either an include matches it, or a default matches it and the noise list doesn't. So an include also switches on noise such as `Unknown_*`, `unknown_*` and `ID_WEB_SoftStand_<n>`.
- The CFI poll reads Parameters and Visibilities only when the defaults or an include could select some path below them (`Selection.reaches`), so a default Bridge still makes one CFI read per poll. Excludes don't stop a vector from being read; that only costs a read.
- A pattern without a field part, such as `cfi/parameters`, matches no value topic and so selects nothing, as globs on the topic path would.
- `Selection` is a small class built from the settings rather than a free function of path and settings; it stays pure.
- Not run against the real Controller in this ticket.
