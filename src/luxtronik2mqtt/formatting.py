"""Formatting: turns a library field into its payload and its meta document.

Fields come from the Controller adapter as library fields; this module reads them
through their `datatype_class`, `value` and `raw`, and their `unit` and `codes`
for the meta document, without importing the library.
"""

import json
from datetime import UTC, datetime
from typing import Any


def payload(field: Any) -> str | None:
    """The payload for a field, or None when it has no value.

    The library converts numbers into display units and codes into readable text.
    Booleans become `1`/`0`, and timestamps ISO 8601 UTC with `Z`, from the raw
    epoch value: the library's own value is in the process's local time.
    """
    value = field.value
    if value is None:
        return None
    if field.datatype_class == "boolean":
        return "1" if value else "0"
    if field.datatype_class == "timestamp":
        # The library shows a raw value of 0 or less as the epoch.
        return datetime.fromtimestamp(max(field.raw, 0), UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(value)


def meta(field: Any, writable: bool) -> str:
    """The meta document for a field, as JSON.

    It holds the unit, the library's data type name, whether a Command can set
    the field and, for a mode, the readable values it allows as `options`.
    """
    document = {"unit": field.unit or None, "type": type(field).__name__, "writable": writable}
    if field.datatype_class == "selection":
        document["options"] = list(field.codes.values())
    return json.dumps(document, ensure_ascii=False)
