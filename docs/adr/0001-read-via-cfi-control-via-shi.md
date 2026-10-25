# Read via CFI, control via SHI

The Bridge reads from both interfaces but writes only through the SHI. The CFI gives by far the broadest view of the Controller (about 1,500 Calculations, Parameters and Visibilities), so it stays the main source for reading, and SHI Inputs and Holdings are published alongside it. Writes go only to SHI Holdings. They are temporary (the Controller forgets them on reboot) and don't wear its flash, and the SHI exists precisely so outside systems can steer the Controller. CFI Parameter writes are permanent, wear the flash, run over a reverse-engineered protocol, and in one reported case (writing `ID_Einst_BA_Lueftung_akt`) left port 8889 hanging.

## Considered Options

- **CFI only, writing Parameters**: needs no SHI-capable firmware, but every command becomes a permanent, flash-wearing change.
- **SHI only**: one interface, but only about 130 values instead of about 1,500.
- **WebSocket on port 8214** (the approach minichma/luxtronik-mqtt-bridge takes): readable menu labels, but the structure depends on the firmware, and writes there also change permanent settings.

## Consequences

- SHI writes need firmware V3.90.1 or later (some Holdings need V3.92.0) and the SHI switched on at the Controller. On older Controllers the Bridge can only read.
- CFI Parameter writes are deliberately left out. If they're ever added, they get their own ENV switch and an explicit allowlist.
