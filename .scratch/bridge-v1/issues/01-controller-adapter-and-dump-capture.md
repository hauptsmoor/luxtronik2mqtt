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

**Status:** done

- [x] The package installs with python-luxtronik pinned to the commit above; the test runner runs and the license file is MIT.
- [x] The capture command reads all CFI and SHI vectors read-only and writes a fixture to stdout.
- [x] In the fixture, `ID_WEB_AdresseIP_akt`, the subnet mask, the broadcast address and the gateway are replaced by placeholder values.
- [x] The first fixture, from the maintainer's Controller, is committed as a test fixture.
- [x] The fake Controller loaded from that fixture returns `29.2` for `ID_WEB_Temperatur_TVL` and `V3.92.1` as the firmware version.
- [x] A test can change a value in the fake between reads, and make the CFI or SHI unreachable and reachable again.
- [x] Against an unreachable host, the adapter reports "unreachable" within its timeout instead of hanging or returning `None`.

## Comments

**2026-10-25, implementation:**
- The fixture is `tests/fixtures/luxtronik-2.1-v3.92.1.json`, captured read-only from the maintainer's Controller while it was idle (`ID_WEB_WP_BZ_akt` = `no request`, compressor off). TVL read 29.2 rather than the 38.3 originally written above; the maintainer chose to keep the capture as it is, so the criterion now names the captured value.
- The Parameters keep copies of the network details (`ID_AdresseIP_akt`, `ID_SubNetMask_akt`, `ID_Add_Broadcast_akt`, `ID_Add_StdGateway_akt`, and `Unknown_Parameter_1127` holding the gateway on V3.92.1). The capture replaces the four Calculations by name, and the Controller's IP, broadcast and gateway address also wherever a Parameter or Calculation register holds them. The mask, `0.0.0.0` and `255.255.255.255` are too common as register values to match that way, so they're replaced only in the Calculations. (The committed fixture was captured under an earlier rule that also matched the mask, so its `ID_SubNetMask_akt` Parameter holds the placeholder mask too.)
- The fake Controller is `tests/fake_controller.py`: `set(vector, name, value)` changes a value, and `cfi_reachable` / `shi_reachable` take an interface away. It decodes the fixture through the library's own read path, and a test checks it reads the same values as the real adapter reading a simulated Controller.
- Possible library bug for ticket 03: python-luxtronik skips the bit mask when a field's `bit_offset` is `0`, so `heatpump_vd1_status` decodes the whole register at SHI address 10000 and reads true whenever any of the other status bits there is set.
