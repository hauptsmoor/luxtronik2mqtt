# 01: Controller adapter, dump capture and first fixture

**What to build:** The foundation everything else stands on. A maintainer or contributor can run a read-only capture command against a Controller and get a fixture file that holds every CFI and SHI vector with the network details replaced by placeholders. Tests can load that fixture into a fake Controller that behaves like the real Controller adapter. This ticket also sets up the project skeleton: a Python package, python-luxtronik pinned to master commit `02afea84bd5bf3ee87445de6f2a42b8029983169` (ADR 0002), a test runner and the MIT license.

The **Controller adapter** is the only module that imports python-luxtronik. Here it covers reading only:
- read CFI Calculations, Parameters and Visibilities;
- read SHI Inputs and Holdings;
- report the firmware version.

An unreachable CFI or SHI comes back as an explicit "unreachable" signal, never as a silent `None`. The library's CFI interface swallows connection errors and has no connect timeout of its own, so the adapter sets its own timeouts. Access stays serialised per interface.

The **fake Controller** replaces the adapter in tests. It builds real python-luxtronik data vectors from the fixture's raw values, so the library's own conversions run in tests. It lets a test change values, and make the CFI or SHI unreachable and reachable again. Holding writes come in ticket 08.

The first fixture comes from the maintainer's Controller (Luxtronik 2.1, V3.92.1). **Ask the maintainer for the Controller address and permission before capturing, and never write to the Controller.**

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] The package installs with python-luxtronik pinned to the commit above; the test runner runs and the license file is MIT.
- [ ] The capture command reads all CFI and SHI vectors read-only and writes a fixture to stdout.
- [ ] In the fixture, `ID_WEB_AdresseIP_akt`, the subnet mask, the broadcast address and the gateway are replaced by placeholder values.
- [ ] The first fixture, from the maintainer's Controller, is committed as a test fixture.
- [ ] The fake Controller loaded from that fixture returns `38.3` for `ID_WEB_Temperatur_TVL` and `V3.92.1` as the firmware version.
- [ ] A test can change a value in the fake between reads, and make the CFI or SHI unreachable and reachable again.
- [ ] Against an unreachable host, the adapter reports "unreachable" within its timeout instead of hanging or returning `None`.
