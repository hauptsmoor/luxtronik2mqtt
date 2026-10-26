# 09: MQTT over TLS

**What to build:** An owner of a remote or community broker can connect securely. `LUX_MQTT_TLS=true` makes the Bridge connect with TLS and check the broker's certificate against the system CA certificates. `LUX_MQTT_CA_FILE` optionally points to a custom CA file, mounted read-only. Username and password work over TLS as they do without it.

**Blocked by:** 02 (Tracer bullet: CFI Calculations to MQTT)

**Status:** done

- [x] With `LUX_MQTT_TLS=true` and `LUX_MQTT_CA_FILE` pointing to the test's CA, the Bridge connects to a TLS broker started inside the test, and values arrive.
- [x] With a CA that doesn't match the broker's certificate, the connection fails with a clear log message and the Bridge doesn't fall back to plain MQTT.
- [x] A `LUX_MQTT_CA_FILE` that doesn't exist stops the Bridge at startup with a message naming the variable.
- [x] With `LUX_MQTT_TLS` unset, the Bridge connects without TLS as before.

A `LUX_MQTT_CA_FILE` without `LUX_MQTT_TLS=true` also stops the Bridge at startup, rather than being ignored: an owner who set a CA but forgot the switch would otherwise run on plain MQTT believing the connection secure.
