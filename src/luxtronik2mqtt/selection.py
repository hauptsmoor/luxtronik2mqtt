"""Selection: whether a value is published, by its topic path after the prefix."""

from fnmatch import fnmatchcase

# Published unless something below leaves them out.
DEFAULTS = ("cfi/calculations/*", "shi/inputs/*", "shi/holdings/*")

# Fields without meaning (the library names them `Unknown_*` on the CFI and
# `unknown_*` on the SHI), and known noise: the firmware version one character per field.
NOISE = (
    "*/Unknown_*",
    "shi/*/unknown_*",
    "cfi/calculations/ID_WEB_SoftStand_*",
)


def selected(path: str) -> bool:
    """Whether the value at this topic path, for example `cfi/calculations/ID_WEB_Temperatur_TVL`, is published."""
    return _matches(path, DEFAULTS) and not _matches(path, NOISE)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)
