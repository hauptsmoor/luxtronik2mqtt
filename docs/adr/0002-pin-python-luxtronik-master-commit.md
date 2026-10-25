# Pin python-luxtronik to a master commit

The Bridge depends on python-luxtronik from GitHub, pinned to one specific master commit, not on the PyPI release. The SHI support it needs exists only on master; the latest PyPI release, 0.3.14 from 2022, has none. The pin keeps builds reproducible: two people building the same Bridge version get the same library code, and announced API changes on master can't break the image without warning. All library calls go through one thin adapter module in the Bridge, so a library API change only touches that module.

## Considered Options

- **Track master unpinned**: always the newest fixes, but builds aren't reproducible and a breaking change on master breaks the next image without warning.
- **Wait for a PyPI release**: no SHI until then, so no Commands.
- **0.3.14 from PyPI for CFI plus our own SHI code on `pyModbusTCP`**: duplicates the library's SHI register map and its firmware-version handling, which we would then have to maintain ourselves.

## Consequences

- Moving the pin to a newer commit is a deliberate change, tested against a real Controller first.
- Once a PyPI release includes the SHI, switch to it and supersede this ADR.
