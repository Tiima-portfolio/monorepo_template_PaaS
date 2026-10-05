"""Rounding that matches JavaScript's Math.round (half up), not Python's round."""

import math


def round1(x: float) -> float:
    """Rounds to one decimal, halves up."""
    return math.floor(x * 10 + 0.5) / 10


def pct(part: int, total: int) -> float | None:
    return round1(part / total * 100) if total else None
