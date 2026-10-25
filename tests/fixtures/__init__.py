"""Dumps of real Controllers, captured read-only with luxtronik2mqtt-capture."""

from pathlib import Path

from luxtronik2mqtt.controller import Dump

# The maintainer's Luxtronik 2.1 on V3.92.1, captured while idle.
V3_92_1 = Path(__file__).parent / "luxtronik-2.1-v3.92.1.json"


def load(path: Path = V3_92_1) -> Dump:
    return Dump.from_json(path.read_text())
