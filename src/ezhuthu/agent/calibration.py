"""Per-decider confidence calibration and abstain thresholds, fitted on the VAL split only (issue #22).

A decider's raw top-1 probability is not a probability of matching the expert: a ``choice`` over ~20
candidates spreads mass (the 2B never exceeded 0.5 in the 2026-11-02 benchmark), so one global abstain
threshold of 0.5 abstained on everything. Each decider *variant* therefore gets its own:

* **Platt scaling** (a generalised temperature): ``p' = sigmoid(a * logit(p) + b)``, fitted by Newton's method
  on (raw top-1 confidence, top-1 matched the expert) pairs from the VAL split, with a small L2 prior that
  keeps ``a`` near 1 and ``b`` near 0 when there is little data.
* **An abstain threshold** on the calibrated scale that maximises (fills matching the expert) - (fills that do
  not) on VAL, i.e. fill only where a fill is more likely right than wrong. If no threshold has a positive
  margin the threshold is 1.0 (abstain unless certain).

The variant key is ``<decider model>|<strategy>|k<top_k>|<llm-sonnet|llm-opus|retrieval>``: the same decider
sees a different candidate mix with and without LLM candidates, and Sonnet's and Opus's fills differ again, so
each is calibrated separately (a gap where Opus answered, alone or after Sonnet, uses the ``llm-opus`` entry).
Test data is never used: ``python -m ezhuthu.eval.calibrate`` refuses any split but ``val``.

**Minimum sample guard.** A fit on a handful of VAL items is not evidence: the 2026-11-02 ``|llm`` entries were
fitted on n=20 with 1-3 positives, and their in-sample threshold equals the score of the single best item. An
entry with ``n < min_n`` or ``positives < min_positives`` is *provisional*: it stays in the file (so the next run
can extend it) but :meth:`CalibrationTable.get` does not return it, and the restorer keeps raw confidences and
``routing.abstain_if_confidence_below`` for that variant.
"""

from __future__ import annotations

import json
import math
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .config import PACKAGE_DIR

EPS = 1e-4
MIN_N = 100  # items a calibration entry needs before the restorer uses it
MIN_POSITIVES = 10  # ... and items whose top-1 matched the expert


def logit(p: float) -> float:
    p = min(1 - EPS, max(EPS, p))
    return math.log(p / (1 - p))


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    e = math.exp(x)
    return e / (1 + e)


def llm_tag(llm: bool | str | None) -> str:
    """``retrieval`` (no LLM answered), ``llm-<short>`` for the strongest LLM that answered, ``llm`` if unknown."""
    if not llm:
        return "retrieval"
    if isinstance(llm, str):
        return f"llm-{llm}"
    return "llm"


def variant_key(decider_model: str, strategy: str, top_k: int, llm: bool | str | None) -> str:
    """``llm``: False/None (retrieval only), or the short name of the LLM whose fills are in the pool
    (``sonnet``/``opus``). ``True`` gives the legacy router-agnostic ``|llm`` key."""
    if decider_model.startswith("fallback:"):  # no decider ran: strategy and k do not apply
        strategy = "fallback"
    k = f"k{top_k}" if strategy in ("choice-topk", "noul-topk") else "kall"
    return f"{decider_model}|{strategy}|{k}|{llm_tag(llm)}"


@dataclass(frozen=True)
class Calibration:
    a: float = 1.0
    b: float = 0.0
    threshold: float = 0.5
    n: int = 0
    positives: int = 0
    split: str = "val"
    fitted_at: str = ""
    note: str = ""

    def provisional(self, min_n: int = MIN_N, min_positives: int = MIN_POSITIVES) -> bool:
        """Too few VAL items (or too few correct ones) for the fit or its threshold to mean anything."""
        return self.n < min_n or self.positives < min_positives

    def apply(self, p: float) -> float:
        if p <= 0.0:
            return 0.0
        return round(sigmoid(self.a * logit(p) + self.b), 4)


def fit_platt(conf: Sequence[float], correct: Sequence[bool], *, l2: float = 1.0, iters: int = 50) -> tuple[float, float]:
    """MAP logistic regression of ``correct`` on ``logit(conf)`` with a Gaussian prior centred on (a=1, b=0)."""
    xs = [logit(c) for c in conf]
    ys = [1.0 if y else 0.0 for y in correct]
    a, b = 1.0, 0.0
    for _ in range(iters):
        ga = l2 * (a - 1.0)
        gb = l2 * b
        haa, hab, hbb = l2, 0.0, l2
        for x, y in zip(xs, ys, strict=True):
            p = sigmoid(a * x + b)
            r = p - y
            w = p * (1 - p)
            ga += r * x
            gb += r
            haa += w * x * x
            hab += w * x
            hbb += w
        det = haa * hbb - hab * hab
        if det <= 1e-12:
            break
        da = (hbb * ga - hab * gb) / det
        db = (haa * gb - hab * ga) / det
        a, b = a - da, b - db
        if abs(da) < 1e-8 and abs(db) < 1e-8:
            break
    return round(a, 6), round(b, 6)


def fit_threshold(conf: Sequence[float], correct: Sequence[bool]) -> float:
    """Threshold maximising (right fills - wrong fills) over the filled items; 1.0 if nothing has a margin."""
    best_t, best_u = 1.0, 0
    for t in sorted(set(conf), reverse=True):
        u = sum((1 if ok else -1) for c, ok in zip(conf, correct, strict=True) if c >= t)
        if u > best_u:
            best_t, best_u = t, u
    return round(best_t, 4)


def fit(conf: Sequence[float], correct: Sequence[bool], **meta: Any) -> Calibration:
    a, b = fit_platt(conf, correct)
    tmp = Calibration(a, b)
    cal = [tmp.apply(c) for c in conf]
    return Calibration(a, b, fit_threshold(cal, correct), len(conf), sum(bool(x) for x in correct), **meta)


def cross_validated(conf: Sequence[float], correct: Sequence[bool], folds: int = 5,
                    seed: int = 13) -> tuple[list[float], list[bool]]:
    """Out-of-fold calibrated confidences and fill decisions, for an honest within-VAL estimate."""
    idx = list(range(len(conf)))
    random.Random(seed).shuffle(idx)
    cal_out = [0.0] * len(conf)
    fill_out = [False] * len(conf)
    for f in range(folds):
        test = set(idx[f::folds])
        tr = [i for i in idx if i not in test]
        if not tr:
            continue
        c = fit([conf[i] for i in tr], [correct[i] for i in tr])
        for i in test:
            cal_out[i] = c.apply(conf[i])
            fill_out[i] = cal_out[i] >= c.threshold
    return cal_out, fill_out


class CalibrationTable:
    """Calibration entries by variant key. ``get`` skips provisional entries (see the module docstring);
    pass ``min_n=0, min_positives=0`` to trust every entry (unit tests with hand-made entries do)."""

    def __init__(self, entries: dict[str, Calibration] | None = None, path: Path | None = None, *,
                 min_n: int = MIN_N, min_positives: int = MIN_POSITIVES):
        self.entries = dict(entries or {})
        self.path = path
        self.min_n = min_n
        self.min_positives = min_positives

    @classmethod
    def load(cls, spec: str | Path | None, *, min_n: int = MIN_N, min_positives: int = MIN_POSITIVES) -> CalibrationTable:
        guard = {"min_n": min_n, "min_positives": min_positives}
        if not spec:
            return cls(**guard)
        p = Path(spec)
        if not p.is_absolute() and not p.exists():
            p = PACKAGE_DIR / p
        if not p.is_file():
            return cls(path=p, **guard)
        raw = json.loads(p.read_text(encoding="utf-8"))
        fields = Calibration.__dataclass_fields__
        return cls({k: Calibration(**{f: v for f, v in d.items() if f in fields})
                    for k, d in raw.get("variants", {}).items()}, path=p, **guard)

    def get(self, key: str) -> Calibration | None:
        """The entry for ``key`` if it has enough VAL data to be used; ``None`` if missing or provisional."""
        c = self.entries.get(key)
        if c is None or c.provisional(self.min_n, self.min_positives):
            return None
        return c

    def raw_get(self, key: str) -> Calibration | None:
        """The stored entry, provisional or not (reports and the calibrate CLI)."""
        return self.entries.get(key)

    def to_json(self, note: str = "") -> str:
        return json.dumps({"note": note or "Platt (a, b) and abstain threshold per decider variant; VAL split only.",
                           "variants": {k: asdict(v) for k, v in sorted(self.entries.items())}},
                          ensure_ascii=False, indent=1) + "\n"
