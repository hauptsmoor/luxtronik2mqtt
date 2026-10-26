# 12: README

**What to build:** A heat-pump owner can set up and use the Bridge from the README alone. It covers:
- what the Bridge does, and which Controllers and firmware it supports;
- every ENV variable with its default;
- a `docker run` example and a Compose example;
- the topic reference: value, `meta`, status, `/set` and `/error` topics;
- the payload rules;
- how to use include/exclude patterns, with examples;
- an example Telegraf `mqtt_consumer` configuration that parses the topic path into measurement and field names;
- how to switch the SHI on at the Controller (*Service → Systemsteuerung → Konnektivität → Smart-Home-Interface*), which firmware it needs, and why `shi/status` might show `offline`;
- how to switch Commands on, with warnings that SHI Holdings are forgotten on Controller reboot and that frequent lock switching wears the compressor;
- how contributors capture and submit a fixture from their own Controller;
- the license (MIT).

Use the glossary terms throughout.

**Blocked by:** 04 (Include/exclude patterns), 05 (Regular full republish), 06 (Status topics and outage recovery), 07 (Metadata topics), 08 (Commands for SHI Holdings), 09 (MQTT over TLS), 10 (Docker image and CI)

**Status:** done

- [x] Every ENV variable the Bridge reads is in the table with its default and matches the code.
- [x] Every topic the Bridge publishes or subscribes to is documented with retain behaviour and an example payload.
- [x] The Telegraf example parses at least one CFI and one SHI topic correctly when tried against a test broker.
- [x] The SHI section explains how to switch it on, the firmware requirement and the CFI-only behaviour.
- [x] The Commands section shows a `/set` example and carries the reboot and compressor-wear warnings.
- [x] The contributing section explains how to capture and submit a fixture.

The Telegraf example was tried with the `telegraf:1.36` image against a mosquitto broker, with the real Bridge publishing the fixture's values. It produced 227 CFI Calculations, 45 SHI Inputs, 19 SHI Holdings and one included Parameter, each as its own field. The example uses the `grok` parser, not `data_format = "value"`, because the `value` parser keeps only the last word of a payload (`no request` became `request`). Where the code differs from the spec, the README follows the code: durations publish in python-luxtronik's unit, seconds, not hours. The image is `ghcr.io/hauptsmoor/luxtronik2mqtt`, after the repository at https://github.com/hauptsmoor/luxtronik2mqtt.
