"""Numbers that print like JavaScript's: Math.round halves up, and a whole
number prints without ".0"."""

import math


def num(x):
    """50.0 -> 50, so messages read the same as the JS factory's."""
    return int(x) if isinstance(x, float) and x.is_integer() else x


def round1(x: float):
    """Rounds to one decimal, halves up."""
    return num(math.floor(x * 10 + 0.5) / 10)


def pct(part: int, total: int):
    return round1(part / total * 100) if total else None
