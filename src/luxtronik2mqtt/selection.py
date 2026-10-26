"""Selection: whether a value is published, by its topic path after the prefix."""

from fnmatch import fnmatchcase

# Published unless something below leaves them out.
DEFAULTS = ("cfi/calculations/*", "shi/inputs/*", "shi/holdings/*")

# Fields without meaning (the library names them `Unknown_*` on the CFI and
# `unknown_*` on the SHI), and known noise: the firmware version one character per field.
# An include switches them on.
NOISE = (
    "*/Unknown_*",
    "shi/*/unknown_*",
    "cfi/calculations/ID_WEB_SoftStand_*",
)


class Selection:
    """The defaults and the noise list, with the user's include and exclude patterns on top.

    Patterns are globs on the topic path after the prefix. An include adds to the
    defaults, and an exclude wins over both.
    """

    def __init__(self, include: tuple[str, ...], exclude: tuple[str, ...]) -> None:
        self._include = include
        self._exclude = exclude

    def selected(self, path: str) -> bool:
        """Whether the value at this topic path, for example `cfi/calculations/ID_WEB_Temperatur_TVL`, is published."""
        if _matches(path, self._exclude):
            return False
        return _matches(path, self._include) or (_matches(path, DEFAULTS) and not _matches(path, NOISE))

    def reaches(self, vector_path: str) -> bool:
        """Whether any value under this vector, for example `cfi/parameters`, can be selected, so it's worth reading."""
        return any(_matches_some_path_below(vector_path + "/", pattern) for pattern in DEFAULTS + self._include)


def _matches(path: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatchcase(path, pattern) for pattern in patterns)


def _matches_some_path_below(start: str, pattern: str) -> bool:
    # Some path that begins with `start` matches if a head of the pattern matches `start`
    # itself: the rest of the pattern then matches whatever follows. A head cut inside a
    # `[...]` has an unclosed `[`, which matches only a literal `[`, so it never matches wrongly.
    return any(fnmatchcase(start, pattern[:end]) for end in range(len(pattern) + 1))
