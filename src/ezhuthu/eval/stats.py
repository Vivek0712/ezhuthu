"""Uncertainty and paired tests for eval reports: percentile bootstrap CIs and the exact McNemar test."""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Sequence


def bootstrap_ci(values: Sequence[float], *, stat: Callable[[Sequence[float]], float] | None = None,
                 n_boot: int = 2000, alpha: float = 0.05, seed: int = 26) -> tuple[float, float] | None:
    """Percentile bootstrap (resampling items with replacement) of ``stat`` (default: the mean).
    Returns (low, high) rounded to 4 places, or None for an empty sample."""
    n = len(values)
    if n == 0:
        return None
    f = stat or (lambda xs: sum(xs) / len(xs))
    rng = random.Random(seed)
    vals = list(values)
    boots = sorted(f([vals[rng.randrange(n)] for _ in range(n)]) for _ in range(n_boot))
    lo = boots[math.floor(alpha / 2 * n_boot)]
    hi = boots[min(n_boot - 1, math.ceil((1 - alpha / 2) * n_boot) - 1)]
    return round(lo, 4), round(hi, 4)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value: ``b`` = pairs only system A got right, ``c`` = only system B.
    Under H0 the discordant pairs split Binomial(b + c, 1/2)."""
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return round(min(1.0, 2 * tail), 6)


def paired(a: Sequence[bool], b: Sequence[bool]) -> dict[str, float | int]:
    """Discordant counts and the exact McNemar p for two systems scored on the same items (same order)."""
    if len(a) != len(b):
        raise ValueError("paired comparison needs the same items")
    only_a = sum(1 for x, y in zip(a, b, strict=True) if x and not y)
    only_b = sum(1 for x, y in zip(a, b, strict=True) if y and not x)
    return {"only_a": only_a, "only_b": only_b, "both": sum(1 for x, y in zip(a, b, strict=True) if x and y),
            "p_mcnemar": mcnemar_exact(only_a, only_b)}
