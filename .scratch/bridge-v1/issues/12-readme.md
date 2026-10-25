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

**Status:** ready-for-agent

- [ ] Every ENV variable the Bridge reads is in the table with its default and matches the code.
- [ ] Every topic the Bridge publishes or subscribes to is documented with retain behaviour and an example payload.
- [ ] The Telegraf example parses at least one CFI and one SHI topic correctly when tried against a test broker.
- [ ] The SHI section explains how to switch it on, the firmware requirement and the CFI-only behaviour.
- [ ] The Commands section shows a `/set` example and carries the reboot and compressor-wear warnings.
- [ ] The contributing section explains how to capture and submit a fixture.
