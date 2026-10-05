"""Glob matching for policy paths.

`**` matches any number of path segments and `*` matches within one segment.
Paths use forward slashes.
"""

import re
from functools import lru_cache


@lru_cache(maxsize=None)
def glob_to_regex(glob: str) -> re.Pattern:
    out = []
    i = 0
    while i < len(glob):
        c = glob[i]
        if c == "*" and glob[i + 1 : i + 2] == "*":
            # "dir/**" also matches "dir" itself; "**/x" matches "x" at any depth.
            if glob[i + 2 : i + 3] == "/":
                out.append("(?:.*/)?")
                i += 3
            else:
                out.append(".*")
                i += 2
            continue
        out.append("[^/]*" if c == "*" else re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path: str, glob: str) -> bool:
    return bool(glob_to_regex(glob).match(path))


def matches_any(path: str, globs) -> bool:
    return any(matches(path, g) for g in globs or [])
