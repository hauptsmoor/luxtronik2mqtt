# 05: Regular full republish

**What to build:** A Telegraf user gets regular data points even for values that never change. Every `LUX_REPUBLISH_INTERVAL` seconds (default 300), the Bridge republishes every currently selected value, whether or not it changed. Between republishes, publish-on-change from ticket 02 stays as it is.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** ready-for-agent

- [ ] With no value changes, a subscriber receives every selected topic again once the republish interval passes on the injected clock, and not before.
- [ ] Polls between republishes publish only changed values.
- [ ] `LUX_REPUBLISH_INTERVAL` changes the interval; an invalid value stops the Bridge at startup with a message naming the variable.
- [ ] Once ticket 03 is in, the republish includes SHI values as well.
