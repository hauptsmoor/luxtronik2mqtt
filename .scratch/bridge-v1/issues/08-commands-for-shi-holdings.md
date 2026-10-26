# 08: Commands for SHI Holdings

**What to build:** A developer of a control application can steer the heat pump through MQTT, but only once the owner has switched Commands on with `LUX_SHI_WRITE=true` (default `false`). Commands only ever write SHI Holdings, never CFI Parameters (ADR 0001).

A Command is a plain value published to `<prefix>/shi/holdings/<name>/set`, for example `hot_water_setpoint/set` → `45` or `lock_heating/set` → `On`, in the same form the Bridge publishes. The Bridge:
1. Rejects the Command with a short, non-retained message on `<prefix>/shi/holdings/<name>/error` if any of these holds:
   - the message is retained;
   - Commands are switched off;
   - `<name>` isn't a writable Holding;
   - the Holding has no value on this installation;
   - the SHI is unreachable;
   - the library can't convert the payload.
2. Otherwise writes the Holding through the Controller adapter and reads it back.
3. Publishes the value read back on `<prefix>/shi/holdings/<name>` straight away, outside the normal poll.
4. Also publishes an error if the write fails or the value read back differs from the requested one. The read-back is still what's published on the Holding topic.

Value ranges are left to the library and the Controller; the Bridge has no limits of its own. It never retries a Command on its own and never reapplies Holdings after a Controller reboot.

This ticket adds Holding writes to the Controller adapter and to the fake Controller. The fake lets a test accept a write, reject it, or apply a different value. **No test or agent ever writes to a real Controller.**

**Blocked by:** 06 (Status topics and outage recovery)

**Status:** ready-for-agent

- [ ] With `LUX_SHI_WRITE` unset, a Command produces an error and the fake receives no write.
- [ ] With `LUX_SHI_WRITE=true`, `hot_water_setpoint/set` → `45` writes to the fake, and the Holding topic shows the value read back.
- [ ] A mode Command such as `heating_mode/set` → `Setpoint` uses the same readable text the Bridge publishes.
- [ ] A retained Command is rejected with an error and not written.
- [ ] A Command for a name that isn't a writable Holding, or for a Holding with no value, is rejected with an error.
- [ ] A payload the library can't convert is rejected with an error.
- [ ] With the SHI unreachable, a Command is rejected with an error.
- [ ] When the fake applies a different value than requested, the Holding topic shows the applied value and an error is published.
- [ ] When the fake rejects the write, an error is published and the Holding topic keeps showing the value read back.
- [ ] There is no code path that writes a CFI Parameter.

## Comments

- 2026-10-26, decided with the maintainer during ticket 07: the `writable` field in a Holding's `meta` topic means "a Command could set this in principle". It stays `true` whatever `LUX_SHI_WRITE` is set to, so this ticket shouldn't tie it to that setting.
