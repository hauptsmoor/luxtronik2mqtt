# luxtronik2mqtt

Bridge between a Luxtronik 2.x heat-pump Controller and an MQTT broker.

The Bridge reads the Controller over both of its network interfaces and publishes every relevant value to MQTT, each as its own retained topic with a plain payload:

```
luxtronik/cfi/calculations/ID_WEB_Temperatur_TVL   29.2
luxtronik/cfi/calculations/ID_WEB_WP_BZ_akt        no request
luxtronik/shi/inputs/heatpump_status               Idle
luxtronik/shi/holdings/hot_water_setpoint          40.0
```

It works with Node-RED, Telegraf/InfluxDB, your own applications, or anything else that speaks MQTT. Configuration is ENV variables only, with no config file and no volume. Only the Controller's and the broker's addresses are required.

- **CFI** (port 8889): the Controller's configuration interface. It holds about 290 **Calculations** (temperatures, operating states, run hours, energy), about 1,200 **Parameters** (stored settings) and about 400 **Visibilities** (which features this installation has). The Bridge only ever reads it.
- **SHI** (port 502): the Smart Home Interface, Modbus TCP. It holds **Inputs** (read-only values) and **Holdings**. Holdings are values that outside systems write to steer the Controller, and the Controller forgets them on reboot. When you switch them on, the Bridge accepts **Commands** that set Holdings. It never writes Parameters, because those writes are permanent and wear the Controller's flash ([ADR 0001](docs/adr/0001-read-via-cfi-control-via-shi.md)).

## Supported Controllers

Luxtronik 2.0 and 2.1 Controllers, as built into Alpha Innotec, Novelan and other heat pumps. The Bridge reads them through [python-luxtronik](https://github.com/Bouni/python-luxtronik), pinned to one master commit ([ADR 0002](docs/adr/0002-pin-python-luxtronik-master-commit.md)).

- The **CFI** works on any firmware the library supports.
- The **SHI** needs firmware **V3.90.1** or later, and it has to be switched on at the Controller (see [The SHI](#the-shi)). Some Inputs and Holdings, such as the `lock_*` Holdings, need V3.92.0 or later. On older firmware those fields have no value and aren't published.

So far it has been tested against one real Controller: a Luxtronik 2.1 on V3.92.1, read-only. **SHI writes haven't been tried on a real Controller yet.** If you run another model or firmware, please [contribute a fixture](#contributing-a-fixture).

## Quick start

The image runs on amd64, arm64 and armv7 (for example a Raspberry Pi). It runs as a non-root user and needs no volume, so a read-only root filesystem works.

```bash
docker run -d --name luxtronik2mqtt --restart unless-stopped --read-only \
  -e LUX_HOST=192.168.1.50 \
  -e LUX_MQTT_HOST=192.168.1.10 \
  ghcr.io/OWNER/luxtronik2mqtt:latest
```

With Compose:

```yaml
services:
  luxtronik2mqtt:
    image: ghcr.io/OWNER/luxtronik2mqtt:latest
    restart: unless-stopped
    read_only: true
    environment:
      LUX_HOST: 192.168.1.50
      LUX_MQTT_HOST: mosquitto
      LUX_MQTT_USERNAME: luxtronik
      LUX_MQTT_PASSWORD: change-me
      # Hot-water Parameters too, and no placeholder from a missing sensor.
      LUX_INCLUDE: cfi/parameters/ID_Einst_BWS_*
      LUX_EXCLUDE: cfi/calculations/ID_WEB_Temperatur_TWA
```

Within a poll interval (30 s by default), the values appear under `luxtronik/`. The logs go to stdout, so `docker logs luxtronik2mqtt` shows what's happening. `docker stop` shuts the Bridge down cleanly and sets its status to `offline`.

If a setting is missing or invalid, the Bridge exits at startup with a message naming the variable, for example `error: LUX_CFI_POLL_INTERVAL must be at least 2 seconds, not 1`. If it can't reach the broker at startup, it exits too, so let Docker restart it. Once it's running, it reconnects to the broker on its own.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `LUX_HOST` | (required) | The Controller's address. |
| `LUX_CFI_PORT` | `8889` | The CFI's port. |
| `LUX_SHI_PORT` | `502` | The SHI's port. |
| `LUX_CFI_POLL_INTERVAL` | `30` | Seconds between CFI reads. Minimum `2`. |
| `LUX_SHI_POLL_INTERVAL` | `30` | Seconds between SHI reads. Minimum `2`. |
| `LUX_REPUBLISH_INTERVAL` | `300` | Seconds between full republishes of every value. Minimum `2`. |
| `LUX_INCLUDE` | (empty) | Comma-separated patterns for values to publish on top of the defaults. See [Choosing what's published](#choosing-whats-published). |
| `LUX_EXCLUDE` | (empty) | Comma-separated patterns for values never to publish. It wins over the defaults and `LUX_INCLUDE`. |
| `LUX_SHI_WRITE` | `false` | `true` accepts Commands for every writable Holding. See [Commands](#commands). |
| `LUX_MQTT_HOST` | (required) | The broker's address. |
| `LUX_MQTT_PORT` | `1883` | The broker's port. With TLS, usually `8883`. |
| `LUX_MQTT_USERNAME` | (empty) | Username for the broker. |
| `LUX_MQTT_PASSWORD` | (empty) | Password for the broker. Used only with a username. |
| `LUX_MQTT_TLS` | `false` | `true` connects with TLS. It checks the broker's certificate and host name against the system CA certificates. |
| `LUX_MQTT_CA_FILE` | (empty) | A CA file to check the broker's certificate against instead. It needs `LUX_MQTT_TLS=true`. |
| `LUX_MQTT_PREFIX` | `luxtronik` | The first part of every topic. Give each Bridge its own if two share a broker. |
| `LUX_LOG_LEVEL` | `INFO` | A Python log level, such as `DEBUG`, `INFO`, `WARNING` or `ERROR`. |

An empty variable counts as unset. `true`/`false` and the log level can be in any case.

The Bridge speaks MQTT 3.1.1, which every broker supports. Its client ID is `luxtronik2mqtt-` followed by the prefix, with `/` replaced by `-`, so two Bridges with different prefixes don't collide.

For a custom CA, mount the file read-only. The Bridge runs as user `65534`, so the file must be readable by that user:

```bash
docker run -d --read-only \
  -e LUX_HOST=192.168.1.50 \
  -e LUX_MQTT_HOST=mqtt.example.org -e LUX_MQTT_PORT=8883 \
  -e LUX_MQTT_TLS=true -e LUX_MQTT_CA_FILE=/ca.crt \
  -v /etc/luxtronik/ca.crt:/ca.crt:ro \
  ghcr.io/OWNER/luxtronik2mqtt:latest
```

## Topics

All topics start with `<prefix>/`, which is `luxtronik/` by default. `<name>` is the field's name exactly as python-luxtronik gives it. CFI names are German IDs such as `ID_WEB_Temperatur_TVL`, and SHI names are English, such as `hot_water_setpoint`.

| Topic | Retained | Example payload |
|---|---|---|
| `status` | yes | `online`, or `offline` |
| `cfi/status` | yes | `online`, or `offline` |
| `shi/status` | yes | `online`, or `offline` |
| `cfi/calculations/<name>` | yes | `29.2` |
| `cfi/parameters/<name>` | yes | `75.0` |
| `cfi/visibilities/<name>` | yes | `1` |
| `shi/inputs/<name>` | yes | `Idle` |
| `shi/holdings/<name>` | yes | `40.0` |
| `<value topic>/meta` | yes | `{"unit": "°C", "type": "Celsius", "writable": false}` |
| `shi/holdings/<name>/set` | the Bridge subscribes; send it **not** retained | `45` |
| `shi/holdings/<name>/error` | no | `rejected: Commands are switched off (LUX_SHI_WRITE)` |

### Values

A value is published straight after the poll that sees it change. Unchanged values aren't sent again on every poll. Every `LUX_REPUBLISH_INTERVAL` seconds, though, every value is republished whether it changed or not, so time-series databases get regular points.

### Payload rules

- **Numbers** are converted by python-luxtronik into display units and published as plain decimal text, for example `29.2` (°C) or `3664` (seconds). The unit is in the value's `meta` topic.
- **Modes, states and fault codes** are readable text, for example `no request`, `Idle` or `Off`.
- **Booleans** are `1` or `0`.
- **Timestamps** are ISO 8601 in UTC, for example `2025-06-19T21:31:28Z`, whatever time zone the container runs in.
- **IP addresses and version strings** are readable text, for example `192.168.1.50`.
- **No value.** Some fields have no value on your installation, for example the SHI Holdings of an unconfigured mixing circuit (`mc1_*`). Their topics aren't published at all. If a published field later loses its value, its topic and its `meta` topic are cleared with an empty retained payload.

### Metadata

Next to each value topic, `…/<name>/meta` holds a retained JSON document:

```json
{"unit": "°C", "type": "CelsiusUInt16", "writable": true}
{"unit": null, "type": "ControlMode", "writable": true, "options": ["Off", "Setpoint", "Offset", "Level"]}
```

- `unit`: the unit of the payload, or `null`.
- `type`: python-luxtronik's data type name.
- `writable`: whether a Command can set it. This is true only for writable SHI Holdings, whatever `LUX_SHI_WRITE` says.
- `options`: for modes and states only, the readable values the field can take. A Command for a mode uses one of these.

### Status

- `status` is the Bridge itself. It's `online` while the Bridge runs and `offline` after a clean shutdown. If the Bridge dies or loses its connection, the broker sets it to `offline` through the MQTT Last Will.
- `cfi/status` and `shi/status` show whether each interface of the Controller answered its last poll.

When an interface stops answering, its status goes `offline` and its values keep their last retained payloads, so dashboards keep the last known state. The Bridge retries after 5 s, then with doubling delays up to 60 s. Once the interface answers again, its status goes `online` and every value from it is republished. The log notes an outage once when it starts and once when it ends, not on every retry.

If the broker restarts, the Bridge reconnects on its own and publishes its status and every value again.

## Choosing what's published

By default the Bridge publishes:

- every CFI Calculation, except fields named `Unknown_*` and the per-character firmware fields `ID_WEB_SoftStand_*`;
- every SHI Input and Holding that has a value, except fields named `unknown_*`.

CFI Parameters and Visibilities aren't published by default, as there are about 1,600 of them. They aren't even read until an include asks for some of them.

`LUX_INCLUDE` and `LUX_EXCLUDE` take comma-separated patterns on the topic path after the prefix. Copy a topic from MQTT Explorer and drop the prefix:

- An include **adds to** the defaults; it never replaces them.
- An exclude **always wins**, over the defaults and over includes.

Patterns are shell-style globs, and case matters. `*` matches any characters, including `/`. `?` matches one character, and `[...]` matches one of a set of characters.

| Goal | Setting |
|---|---|
| Add the hot-water Parameters | `LUX_INCLUDE=cfi/parameters/ID_Einst_BWS_*` |
| Add one Parameter | `LUX_INCLUDE=cfi/parameters/ID_Einst_WK_akt` |
| Add every Visibility | `LUX_INCLUDE=cfi/visibilities/*` |
| Add the unknown Calculations and SHI fields, to help research what they mean | `LUX_INCLUDE=cfi/calculations/Unknown_*,shi/*/unknown_*` |
| Add every unknown field, including about 180 unknown Parameters and Visibilities | `LUX_INCLUDE=cfi/*/Unknown_*,shi/*/unknown_*` |
| Leave out the placeholder value of a missing sensor (it reads `-50.0`) | `LUX_EXCLUDE=cfi/calculations/ID_WEB_Temperatur_TWA` |
| Leave out every SHI Input | `LUX_EXCLUDE=shi/inputs/*` |

An excluded value's retained topic stays at the broker until you clear it, for example in MQTT Explorer.

## Telegraf

This `mqtt_consumer` configuration feeds every value into InfluxDB. The vector (`calculations`, `holdings` and so on) becomes the measurement and the interface becomes a tag. Each value is a field named after its topic:

```
calculations,interface=cfi ID_WEB_Temperatur_TVL=29.2
calculations,interface=cfi ID_WEB_WP_BZ_akt="no request"
holdings,interface=shi hot_water_setpoint=40
```

```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://192.168.1.10:1883"]
  # Value topics only, which are four levels deep. Status topics are three, and meta, set and error five.
  topics = ["luxtronik/cfi/+/+", "luxtronik/shi/+/+"]
  topic_tag = ""
  # The whole payload is the value: a number becomes a float, anything else (a mode, a timestamp) a string.
  # Not data_format = "value": it keeps only the last word, so "no request" would become "request".
  data_format = "grok"
  grok_patterns = ['^%{NUMBER:value:float}$', '^%{GREEDYDATA:value}$']

  # luxtronik/<interface>/<vector>/<name>: the measurement is the vector, and the name is a tag for now.
  [[inputs.mqtt_consumer.topic_parsing]]
    topic = "luxtronik/+/+/+"
    measurement = "_/_/measurement/_"
    tags = "_/interface/_/field"

# Turns the name tag into the field's name.
[[processors.pivot]]
  tag_key = "field"
  value_key = "value"
```

Add your InfluxDB output as usual. If you changed `LUX_MQTT_PREFIX`, change `luxtronik` in `topics` and `topic` to match. Each field keeps one type: numbers stay floats, and modes stay strings. The full republish every `LUX_REPUBLISH_INTERVAL` seconds gives every field a point at least that often.

## The SHI

The SHI is switched off on the Controller by default. To switch it on, go to the Controller's menu at *Service → Systemsteuerung → Konnektivität → Smart-Home-Interface*. The menu needs firmware V3.90.1 or later; if it isn't there, the firmware is too old.

If `shi/status` shows `offline`, one of these is the cause:

- the firmware is older than V3.90.1;
- the SHI isn't switched on at the Controller;
- port 502 is blocked between the Bridge and the Controller, or `LUX_SHI_PORT` is wrong;
- the Controller isn't reachable at all (then `cfi/status` is `offline` too).

The Bridge doesn't need the SHI. Without it, it logs one warning, publishes the CFI values and keeps retrying the SHI. Switch the SHI on later and the Bridge picks it up without a restart.

## Commands

Commands set SHI Holdings over MQTT. They're **off by default**. Switch them on with `LUX_SHI_WRITE=true`, which accepts Commands for every writable Holding.

> [!WARNING]
> - **The Controller forgets Holdings when it reboots.** After a reboot, every Holding is back at its default. The Bridge publishes those defaults but doesn't send your values again; that's up to your application.
> - **Frequent lock switching wears the compressor.** Every `lock_heating` or `lock_hot_water` change can start or stop the compressor. Don't toggle locks in short cycles.
> - Anyone who can publish to `<prefix>/shi/holdings/+/set` on your broker can steer the heat pump. Secure your broker before you switch Commands on.

To send a Command, publish a plain value, in the same form the Bridge publishes, to `<prefix>/shi/holdings/<name>/set`. Don't set the retain flag:

```bash
mosquitto_pub -h 192.168.1.10 -t luxtronik/shi/holdings/hot_water_mode/set -m Setpoint
mosquitto_pub -h 192.168.1.10 -t luxtronik/shi/holdings/hot_water_setpoint/set -m 45
mosquitto_pub -h 192.168.1.10 -t luxtronik/shi/holdings/lock_heating/set -m On
```

A mode takes one of the `options` in its `meta` topic. According to python-luxtronik, a setpoint Holding only applies while its mode Holding is `Setpoint`. The offset and level Holdings work the same way with `Offset` and `Level`. The Controller and the library enforce ranges, not the Bridge.

After writing, the Bridge reads the Holding back and publishes what the Controller actually applied on `<prefix>/shi/holdings/<name>`, unless you've excluded that topic. If that differs from what you asked for, the Holding topic shows the Controller's value and an error says so.

A Command that's rejected or doesn't take effect gets a short message on `<prefix>/shi/holdings/<name>/error`. The message isn't retained. The Bridge never retries a Command.

| Error | Why |
|---|---|
| `rejected: a retained Command isn't run` | The broker sent a retained Command when the Bridge (re)connected. It could be an old one, so it isn't run. A Command published with the retain flag runs once, but its copy at the broker gets this error on every later reconnect. Clear it by publishing an empty retained message to the `/set` topic. |
| `rejected: Commands are switched off (LUX_SHI_WRITE)` | `LUX_SHI_WRITE` isn't `true`. |
| `rejected: the SHI is unreachable` | The last SHI poll got no answer. |
| `rejected: <name> isn't a writable Holding` | There's no such Holding, or it can't be written. |
| `rejected: <name> has no value on this Controller` | The Holding doesn't exist on this installation or firmware. |
| `rejected: <reason>` | python-luxtronik can't convert the value, for example a mode name that isn't one of its `options`. |
| `failed: the SHI is unreachable` | The SHI stopped answering during the write. |
| `failed: the Controller refused the write` | The Controller didn't accept the write. |
| `failed: the Controller applied <value> instead of <value>` | The value read back differs from the Command, for example because the Controller limited it. |

## Contributing a fixture

The tests run without a heat pump, against a recorded dump of a real Controller (`tests/fixtures/`). A dump of your Controller helps the Bridge support installations that differ from the maintainer's.

The capture command ships in the image. It only reads from the Controller, never writes:

```bash
docker run --rm ghcr.io/OWNER/luxtronik2mqtt:latest luxtronik2mqtt-capture 192.168.1.50 > luxtronik-2.1-v3.92.1.json
```

It reads every CFI and SHI vector and writes them to stdout as JSON. It replaces the Controller's IP address, subnet mask, broadcast address and gateway with documentation placeholders. The IP, broadcast and gateway addresses are also replaced in every other CFI register that holds them, such as the copies the Parameters keep. `--cfi-port` and `--shi-port` set other ports. If the SHI doesn't answer, the fixture holds the CFI only, and the command says so on stderr.

To submit it:

1. Name the file after the Controller model and firmware, such as `luxtronik-2.1-v3.92.1.json`.
2. Look through it before sharing. Apart from the network details, it holds your Parameters, run hours and error history.
3. Open a pull request that adds it to `tests/fixtures/`, with a constant for it in `tests/fixtures/__init__.py`. Say which heat pump it comes from and what the Controller was doing at the time, for example idle or heating.

To run the tests yourself, you need Python 3.11 or later and the [mosquitto](https://mosquitto.org/) broker, which the tests start themselves:

```bash
pip install -e '.[dev]'
```

```bash
mypy && pytest
```

## License

MIT, see [LICENSE](LICENSE). python-luxtronik is MIT-licensed too.
