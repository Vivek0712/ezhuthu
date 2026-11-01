"""Agreement and summary statistics for the expert-validation kit (pure Python, no numpy).

- :func:`cohen_kappa`: two raters, nominal (unweighted) or ordinal (``linear`` / ``quadratic`` weights).
- :func:`fleiss_kappa`: any number of raters per unit. When every unit has the same number of ratings this
  is Fleiss (1971). When the number varies, units with fewer than two ratings are dropped and the observed
  agreement of each unit is weighted by its number of rater pairs, with category shares pooled over all
  ratings (the usual generalisation; it equals Fleiss 1971 when the counts are constant).
- :func:`cluster_bootstrap_ci`: percentile bootstrap over clusters (inscriptions or raters), because
  items from one inscription are correlated.
- :func:`spearman`, :func:`sign_test_p`: small helpers for the report.
"""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from collections.abc import Callable, Hashable, Iterable, Sequence


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable], *, categories: Sequence[Hashable] | None = None,
                weights: str | None = None) -> float:
    """Cohen's kappa for two raters on the same units. ``weights``: None, ``linear`` or ``quadratic``
    (weighted kappa needs ordered numeric categories). Returns NaN when chance agreement is 1 (both raters
    used one and the same category throughout), where kappa is undefined."""
    if len(a) != len(b):
        raise ValueError("raters must rate the same units")
    if not a:
        return math.nan
    cats = list(categories) if categories is not None else sorted(set(a) | set(b))
    idx = {c: i for i, c in enumerate(cats)}
    k, n = len(cats), len(a)
    if weights is None:
        w = [[0.0 if i == j else 1.0 for j in range(k)] for i in range(k)]
    else:
        if k < 2:
            return math.nan
        span = k - 1
        if weights == "linear":
            w = [[abs(i - j) / span for j in range(k)] for i in range(k)]
        elif weights == "quadratic":
            w = [[((i - j) / span) ** 2 for j in range(k)] for i in range(k)]
        else:
            raise ValueError("weights must be None, 'linear' or 'quadratic'")
    obs = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b, strict=True):
        obs[idx[x]][idx[y]] += 1 / n
    pa = [sum(row) for row in obs]
    pb = [sum(obs[i][j] for i in range(k)) for j in range(k)]
    d_obs = sum(w[i][j] * obs[i][j] for i in range(k) for j in range(k))
    d_exp = sum(w[i][j] * pa[i] * pb[j] for i in range(k) for j in range(k))
    if d_exp == 0:
        return math.nan
    return 1 - d_obs / d_exp


def fleiss_kappa(units: Iterable[Sequence[Hashable]], *, categories: Sequence[Hashable] | None = None) -> dict:
    """Fleiss' kappa. ``units`` is one list of ratings per unit (any raters). Returns
    ``{"kappa", "p_observed", "p_expected", "units", "ratings"}``; kappa is NaN when undefined."""
    rows = [list(u) for u in units if len(u) >= 2]
    cats = list(categories) if categories is not None else sorted({c for r in rows for c in r})
    total = sum(len(r) for r in rows)
    if not rows or not cats:
        return {"kappa": math.nan, "p_observed": math.nan, "p_expected": math.nan, "units": 0, "ratings": 0}
    share = Counter(c for r in rows for c in r)
    p_e = sum((share[c] / total) ** 2 for c in cats)
    agree_pairs = 0.0
    all_pairs = 0.0
    for r in rows:
        n_i = len(r)
        cnt = Counter(r)
        agree_pairs += sum(v * (v - 1) for v in cnt.values())
        all_pairs += n_i * (n_i - 1)
    p_o = agree_pairs / all_pairs
    kappa = math.nan if p_e == 1 else (p_o - p_e) / (1 - p_e)
    return {"kappa": kappa, "p_observed": p_o, "p_expected": p_e, "units": len(rows), "ratings": total}


def percent_agreement(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    if not a:
        return math.nan
    return sum(1 for x, y in zip(a, b, strict=True) if x == y) / len(a)


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else math.nan


def cluster_bootstrap_ci(values: Sequence[tuple[Hashable, float]], *, stat: Callable[[list[float]], float] = mean,
                         n_boot: int = 2000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Percentile CI of ``stat`` over ``(cluster, value)`` pairs, resampling whole clusters."""
    groups: dict[Hashable, list[float]] = defaultdict(list)
    for c, v in values:
        groups[c].append(v)
    keys = list(groups)
    if len(keys) < 2:
        return (math.nan, math.nan)
    rng = random.Random(seed)
    boots: list[float] = []
    for _ in range(n_boot):
        sample: list[float] = []
        for _k in keys:
            sample.extend(groups[keys[rng.randrange(len(keys))]])
        s = stat(sample)
        if not math.isnan(s):
            boots.append(s)
    if not boots:
        return (math.nan, math.nan)
    boots.sort()
    lo = boots[math.floor(alpha / 2 * (len(boots) - 1))]
    hi = boots[math.ceil((1 - alpha / 2) * (len(boots) - 1))]
    return (lo, hi)


def _ranks(xs: Sequence[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        r = (i + j) / 2 + 1
        for t in range(i, j + 1):
            ranks[order[t]] = r
        i = j + 1
    return ranks


def spearman(x: Sequence[float], y: Sequence[float]) -> float:
    """Spearman rank correlation (average ranks for ties); NaN for fewer than 3 points or no variance."""
    if len(x) != len(y):
        raise ValueError("x and y differ in length")
    if len(x) < 3:
        return math.nan
    rx, ry = _ranks(x), _ranks(y)
    mx, my = mean(rx), mean(ry)
    sxy = sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True))
    sxx = sum((a - mx) ** 2 for a in rx)
    syy = sum((b - my) ** 2 for b in ry)
    if sxx == 0 or syy == 0:
        return math.nan
    return sxy / math.sqrt(sxx * syy)


def sign_test_p(pos: int, neg: int) -> float:
    """Exact two-sided sign test (ties dropped before calling)."""
    n = pos + neg
    if n == 0:
        return math.nan
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)
