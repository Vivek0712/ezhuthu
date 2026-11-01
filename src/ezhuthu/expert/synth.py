"""Synthetic filled sheets with a known generating model, to test the analysis (never real results).

Rating model: every option has a latent plausibility (edition fill ``q_edition``, AI options ``q_ai``, plus
unit noise ``unit_sd``); a rater's score is ``round(latent + rater_bias + N(0, rater_sd))`` clipped to 1..4.
``rater_sd = 0`` and no bias gives identical raters (kappa = 1). Rater ids start with ``SYN-`` so the report
carries a banner.

Reading model: a rater restores correctly with probability ``p_unaided``, or ``p_assisted`` with suggestions.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from .analyze import SYNTHETIC_PREFIX
from .packet import RATING_COLUMNS, READING_COLUMNS, form_for, label_map, rating_rows, reading_rows, write_csv


def synth_ratings(key: dict[str, Any], raters: list[str], *, seed: int = 0, q_edition: float = 3.4,
                  q_ai: float = 2.3, unit_sd: float = 0.6, rater_sd: float = 0.5, rater_bias_sd: float = 0.2,
                  p_cannot_judge: float = 0.02, p_flagged: float = 0.03) -> dict[str, list[dict[str, str]]]:
    rng = random.Random(seed)
    latent = {}
    for it in key["rating"]:
        for o in it["options"]:
            q = q_edition if o["origin"] == "expert" else q_ai
            latent[(it["code"], o.get("oid") or o["label"])] = q + rng.gauss(0, unit_sd)
    out: dict[str, list[dict[str, str]]] = {}
    for rater in raters:
        bias = rng.gauss(0, rater_bias_sd)
        rows = rating_rows(key, rater)
        labels = label_map(key, rater)
        flagged_items = {it["code"] for it in key["rating"] if rng.random() < p_flagged}
        for r in rows:
            if rng.random() < p_cannot_judge:
                r["cannot_judge_y"] = "y"
                continue
            v = latent[(r["item_code"], labels[r["item_code"]][r["option"]])] + bias + (rng.gauss(0, rater_sd) if rater_sd else 0.0)
            r["rating_1_to_4"] = str(min(4, max(1, round(v))))
            if r["item_code"] in flagged_items:
                r["knew_this_text_y"] = "y"
        out[rater] = rows
    return out


def _wrong(target: str, rng: random.Random) -> str:
    letters = "aikmnptṟḷṉ"
    t = list(target) or ["a"]
    t[rng.randrange(len(t))] = rng.choice(letters)
    s = "".join(t)
    return s + "a" if s == target else s


def synth_reading(key: dict[str, Any], raters: list[str], *, seed: int = 0, p_unaided: float = 0.3,
                  p_assisted: float = 0.6) -> dict[str, list[dict[str, str]]]:
    rng = random.Random(seed + 1)
    targets = {it["code"]: it["target"] for it in key["reading"]}
    out: dict[str, list[dict[str, str]]] = {}
    for i, rater in enumerate(raters):
        rows = reading_rows(key, rater, form_for(i))
        for r in rows:
            p = p_assisted if r["condition"] == "ai_assisted" else p_unaided
            t = targets[r["item_code"]]
            r["your_restoration"] = t if rng.random() < p else _wrong(t, rng)
            r["your_confidence_1_to_4"] = str(rng.randint(1, 4))
            r["seconds_taken"] = str(rng.randint(30, 240))
        out[rater] = rows
    return out


def write_synthetic(key: dict[str, Any], n_raters: int, out: Path, *, seed: int = 0, **kw: Any) -> list[Path]:
    raters = [f"{SYNTHETIC_PREFIX}R{i + 1}" for i in range(n_raters)]
    paths: list[Path] = []
    for rater, rows in synth_ratings(key, raters, seed=seed, **kw).items():
        p = out / f"rating-{rater}.csv"
        write_csv(p, RATING_COLUMNS, rows)
        paths.append(p)
    if key["reading"]:
        for rater, rows in synth_reading(key, raters, seed=seed).items():
            p = out / f"reading-{rater}.csv"
            write_csv(p, READING_COLUMNS, rows)
            paths.append(p)
    return paths
