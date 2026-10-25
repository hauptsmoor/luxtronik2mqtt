# 06: Status topics and outage recovery

**What to build:** A user can always tell what's working, and the Bridge looks after itself through outages.

- **Status topics** (retained, `online`/`offline`):
  - `<prefix>/status` for the Bridge itself, set to `offline` by MQTT Last Will if the Bridge dies and published as `offline` on a clean SIGTERM shutdown;
  - `<prefix>/cfi/status` and `<prefix>/shi/status` for each interface.
- **Controller outage:** when the CFI or SHI becomes unreachable, its status goes `offline` and the retained values stay as they are. The Bridge retries with growing delays (5 s up to 60 s). Once the interface is back, its status goes `online` and every selected value from it is republished in full.
- **No SHI:** if the SHI is unreachable at startup (old firmware, or SHI switched off), the Bridge logs one clear warning, runs CFI-only, and keeps retrying the SHI so it's picked up without a restart.
- **Broker outage:** the Bridge reconnects to the broker on its own, then republishes the status topics and all retained values.
- **Logging:** logs go to stdout at `LUX_LOG_LEVEL` (default `INFO`). A connection problem is logged once when it starts and once when it recovers, not on every retry.

**Blocked by:** 03 (SHI Inputs and Holdings published)

**Status:** ready-for-agent

- [ ] While the Bridge runs, `status`, `cfi/status` and `shi/status` are retained `online`.
- [ ] When the Bridge's MQTT connection drops without a clean disconnect, the broker publishes `status` → `offline` through the Last Will.
- [ ] On SIGTERM, the Bridge publishes `status` → `offline` before it exits.
- [ ] Making the fake CFI unreachable sets `cfi/status` → `offline`, and the retained Calculation topics keep their last values.
- [ ] Retries during an outage follow growing delays from 5 s up to 60 s on the injected clock.
- [ ] When the fake CFI is reachable again, `cfi/status` → `online` and every selected CFI topic is republished.
- [ ] With the SHI unreachable from startup, CFI values are still published, `shi/status` is `offline`, and exactly one warning is logged.
- [ ] When the SHI later becomes reachable, its values are published without a restart.
- [ ] After a broker restart, the Bridge reconnects and the status topics and retained values are back.
- [ ] A long outage logs one message at the start and one at recovery, not one per retry.
