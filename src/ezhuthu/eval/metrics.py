"""Restoration metrics: top-1 exact, top-20, character error rate, ECE (10 bins), coverage-accuracy.

CER is reported three ways because raw per-item CER is unbounded (a 150-character fill for a 1-character
target scores 149) and a few such outliers dominate the mean: ``cer`` (raw mean), ``cer_clipped`` (mean of
per-item CER clipped to 1.0) and ``cer_median``.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from rapidfuzz.distance import Levenshtein

from ..agent.text import normalize_iso

COVERAGE_THRESHOLDS = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9)


def canon(s: str) -> str:
    return normalize_iso(s).replace(" ", "")


@dataclass(frozen=True)
class Prediction:
    item_id: str
    target: str
    candidates: tuple[str, ...]  # ranked
    confidence: float  # of the top-1 candidate
    abstained: bool = False
    hard: bool = False
    age_set: bool = False

    @property
    def top1(self) -> str | None:
        return self.candidates[0] if self.candidates else None

    @property
    def top1_correct(self) -> bool:
        return self.top1 is not None and canon(self.top1) == canon(self.target)

    def in_top(self, k: int) -> bool:
        t = canon(self.target)
        return any(canon(c) == t for c in self.candidates[:k])

    @property
    def cer(self) -> float:
        t = canon(self.target)
        h = canon(self.top1 or "")
        return Levenshtein.distance(t, h) / max(1, len(t))


def ece(confidences: Sequence[float], correct: Sequence[bool], bins: int = 10) -> float:
    """Expected calibration error with equal-width bins over [0, 1]."""
    n = len(confidences)
    if n == 0:
        return 0.0
    total = 0.0
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        if not idx:
            continue
        acc = sum(correct[i] for i in idx) / len(idx)
        conf = sum(confidences[i] for i in idx) / len(idx)
        total += len(idx) / n * abs(acc - conf)
    return total


def reliability(confidences: Sequence[float], correct: Sequence[bool], bins: int = 10) -> list[dict]:
    out = []
    for b in range(bins):
        lo, hi = b / bins, (b + 1) / bins
        idx = [i for i, c in enumerate(confidences) if (lo <= c < hi) or (b == bins - 1 and c == 1.0)]
        out.append({"bin": [round(lo, 2), round(hi, 2)], "n": len(idx),
                    "accuracy": round(sum(correct[i] for i in idx) / len(idx), 4) if idx else None,
                    "confidence": round(sum(confidences[i] for i in idx) / len(idx), 4) if idx else None})
    return out


def coverage_curve(confidences: Sequence[float], correct: Sequence[bool],
                   thresholds: Sequence[float] = COVERAGE_THRESHOLDS) -> list[dict]:
    n = len(confidences)
    out = []
    for t in thresholds:
        idx = [i for i, c in enumerate(confidences) if c >= t]
        out.append({"threshold": t, "coverage": round(len(idx) / n, 4) if n else 0.0,
                    "accuracy": round(sum(correct[i] for i in idx) / len(idx), 4) if idx else None})
    return out


def summarize(preds: Sequence[Prediction]) -> dict:
    n = len(preds)
    if n == 0:
        return {"n": 0, "top1": None, "top20": None, "cer": None, "cer_clipped": None, "cer_median": None,
                "ece": None, "coverage": [], "reliability": [],
                "abstain_rate": None}
    conf = [p.confidence for p in preds]
    ok = [p.top1_correct for p in preds]
    return {
        "n": n,
        "top1": round(sum(ok) / n, 4),
        "top20": round(sum(p.in_top(20) for p in preds) / n, 4),
        "cer": round(sum(p.cer for p in preds) / n, 4),
        "cer_clipped": round(sum(min(1.0, p.cer) for p in preds) / n, 4),
        "cer_median": round(statistics.median(p.cer for p in preds), 4),
        "ece": round(ece(conf, ok), 4),
        "coverage": coverage_curve(conf, ok),
        "reliability": reliability(conf, ok),
        "abstain_rate": round(sum(p.abstained for p in preds) / n, 4),
        "accuracy_when_filled": (round(sum(ok[i] for i, p in enumerate(preds) if not p.abstained)
                                       / max(1, sum(not p.abstained for p in preds)), 4)),
    }


def by_subset(preds: Sequence[Prediction]) -> dict[str, dict]:
    return {"full": summarize(preds), "hard": summarize([p for p in preds if p.hard]),
            "age": summarize([p for p in preds if p.age_set])}
