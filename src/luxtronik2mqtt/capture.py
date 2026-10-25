"""Dump capture: reads every CFI and SHI vector from a Controller and writes a fixture to stdout.

It only ever reads. The Controller's network details are replaced by placeholders,
so the fixture can be shared as a test fixture: in their Calculations, and its
addresses also wherever else a register holds them (the Parameters keep copies).
"""

import argparse
import sys
from collections.abc import Sequence

from luxtronik2mqtt.controller import DEFAULT_CFI_PORT, DEFAULT_SHI_PORT, Controller, Unreachable

# Documentation addresses (RFC 5737), in place of the Controller's own.
PLACEHOLDERS = {
    "ID_WEB_AdresseIP_akt": "192.0.2.10",
    "ID_WEB_SubNetMask_akt": "255.255.255.0",
    "ID_WEB_Add_Broadcast": "192.0.2.255",
    "ID_WEB_Add_StdGateway": "192.0.2.1",
}

# The fields whose address is distinctive enough to replace wherever a register holds it.
# A mask, 0.0.0.0 or 255.255.255.255 is too common a register value for that.
_ADDRESSES = ("ID_WEB_AdresseIP_akt", "ID_WEB_Add_Broadcast", "ID_WEB_Add_StdGateway")
_UNSPECIFIC_ADDRESSES = {"0.0.0.0", "255.255.255.255"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="luxtronik2mqtt-capture",
        description="Read every CFI and SHI vector from a Controller, read-only, and write a fixture to stdout.",
    )
    parser.add_argument("host", help="the Controller's address")
    parser.add_argument("--cfi-port", type=int, default=DEFAULT_CFI_PORT)
    parser.add_argument("--shi-port", type=int, default=DEFAULT_SHI_PORT)
    args = parser.parse_args(argv)

    try:
        dump = Controller(args.host, cfi_port=args.cfi_port, shi_port=args.shi_port).read_dump()
    except Unreachable as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if dump.shi is None:
        print("warning: the SHI didn't answer, so the fixture holds CFI vectors only", file=sys.stderr)
    calculations = dump.decode("calculations")
    for name, placeholder in PLACEHOLDERS.items():
        address = calculations.get(name).value
        if name in _ADDRESSES and address not in _UNSPECIFIC_ADDRESSES:
            dump.replace_address(address, placeholder)
        dump.set("calculations", name, placeholder)
    sys.stdout.write(dump.to_json())
    return 0


if __name__ == "__main__":
    sys.exit(main())
