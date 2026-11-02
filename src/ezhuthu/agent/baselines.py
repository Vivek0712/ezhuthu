"""Baselines for the restoration benchmark.

- ``copy``: copy the aligned text from the best parallel passage (retrieval only). Fills whose length is
  outside the gap's tolerance (``length_tolerance``, the same rule the restorer uses) are dropped: alignment
  can return the rest of a line (150 characters for a 1-letter gap), which is not a restoration. Lengths are
  counted in Tamil letters (``akshara_len``), the unit of ``gap_chars``.
- ``ngram``: character 5-gram model with beam search, trained on the train corpus lines.
- ``zeroshot``: the default LLM with no parallels and no ontology hints.

Each returns ranked candidates with a confidence in [0, 1] so the same metrics (top-1, top-20, ECE) apply.
"""

from __future__ import annotations

import math

from .llm import LLMClient
from .prompts import RESTORER_SYSTEM, parse_candidates, propose_max_tokens, zero_shot_prompt
from .restorer import Restorer, length_ok
from .text import normalize_iso

BASELINES = ("copy", "ngram", "zeroshot")


def copy_best_parallel(restorer: Restorer, left: str, right: str, gap_chars: int | None, *,
                       exclude_inscription: str | None = None, k: int = 20) -> list[tuple[str, float]]:
    ps = restorer.retrieve_parallels(left, right, gap_chars, k=k, exclude_inscription=exclude_inscription)
    out: dict[str, float] = {}
    for p in ps:
        if gap_chars and p.fill and not length_ok(p.fill, gap_chars):  # both in Tamil letters
            continue
        if p.fill and p.fill not in out:
            out[p.fill] = round(p.score / 100.0, 4)
    return sorted(out.items(), key=lambda x: x[1], reverse=True)


def ngram_fill(restorer: Restorer, left: str, right: str, gap_chars: int, *, k: int = 20) -> list[tuple[str, float]]:
    beams = restorer.ngram.fill(left, right, gap_chars, k=k, beam=max(16, k))
    if not beams:
        return []
    # Softmax over beam log-probs: a relative confidence among the beam, not a calibrated probability.
    m = max(lp for _, lp in beams)
    exps = [(t, math.exp(lp - m)) for t, lp in beams]
    z = sum(e for _, e in exps)
    return [(t, round(e / z, 4)) for t, e in exps]


def zero_shot(llm: LLMClient, left: str, right: str, gap_chars: int | None, *, k: int = 20) -> list[tuple[str, float]]:
    # Same compact format and output budget as the restorer; a truncated reply keeps its complete fills.
    r = llm.complete("default", RESTORER_SYSTEM, zero_shot_prompt(left, right, gap_chars, k),
                     max_tokens=propose_max_tokens(k, gap_chars))
    out: dict[str, float] = {}
    for t, c in parse_candidates(r.text):
        t = normalize_iso(t)
        if t and t not in out:
            out[t] = c if c is not None else 0.0
    return sorted(out.items(), key=lambda x: x[1], reverse=True)
