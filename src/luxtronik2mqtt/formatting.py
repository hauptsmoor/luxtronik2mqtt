"""Formatting: turns a library field into its payload.

Fields come from the Controller adapter as library fields; this module reads them
through their `datatype_class`, `value` and `raw` only, without importing the library.
"""

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
