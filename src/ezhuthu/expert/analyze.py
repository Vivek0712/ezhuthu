"""Ingest filled rating / reading-study sheets and compute the protocol's metrics.

Main analysis set: ratings that are not "cannot judge" and whose rater did not consult the edition first or
already know the text. Those excluded ratings are counted, and the agreement figures are also reported with
them included (sensitivity).
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rapidfuzz.distance import Levenshtein

from ..agent.text import looks_tamil, tamil_to_iso
from ..corpus.script import normalise_for_scoring as letters
from .packet import RATING_COLUMNS, READING_COLUMNS
from .stats import (
    cluster_bootstrap_ci,
    cohen_kappa,
    fleiss_kappa,
    mean,
    percent_agreement,
    sign_test_p,
    spearman,
)

YES = {"y", "yes", "1", "true", "ஆம்"}
SYNTHETIC_PREFIX = "SYN-"


class SheetError(ValueError):
    """A filled sheet does not match the packet key."""


def _yes(v: str | None) -> bool:
    return (v or "").strip().lower() in YES


def read_sheet(path: Path) -> tuple[str, list[dict[str, str]]]:
    """Return ``("rating" | "reading", rows)``; the kind is taken from the header."""
    text = Path(path).read_text(encoding="utf-8-sig")
    rows = list(csv.DictReader(text.splitlines()))
    header = set(rows[0]) if rows else set(csv.reader(text.splitlines()).__next__())
    if {"rating_1_to_4", "option"} <= header:
        missing = set(RATING_COLUMNS) - header
        kind = "rating"
    elif {"your_restoration", "condition"} <= header:
        missing = set(READING_COLUMNS) - header
        kind = "reading"
    else:
        raise SheetError(f"{path}: not a rating or reading sheet (header {sorted(header)[:6]}...)")
    if missing:
        raise SheetError(f"{path}: missing columns {sorted(missing)}")
    return kind, rows


def collect_sheets(paths: list[Path]) -> dict[str, list[dict[str, str]]]:
    files: list[Path] = []
    for p in paths:
        files += sorted(Path(p).rglob("*.csv")) if Path(p).is_dir() else [Path(p)]
    out: dict[str, list[dict[str, str]]] = {"rating": [], "reading": []}
    for f in files:
        kind, rows = read_sheet(f)
        for r in rows:
            r["_file"] = f.name
        out[kind] += rows
    return out


# ------------------------------------------------------------------------------------------- ratings -------
@dataclass(frozen=True)
class Rating:
    rater: str
    item: str
    option: str
    value: int | None  # None = cannot judge
    flagged: bool  # consulted the edition first or knew the text


def parse_ratings(rows: list[dict[str, str]], key: dict[str, Any]) -> tuple[list[Rating], dict[str, int]]:
    units = {(it["code"], o["label"]) for it in key["rating"] for o in it["options"]}
    seen: set[tuple[str, str, str]] = set()
    item_flag: dict[tuple[str, str], bool] = defaultdict(bool)
    for r in rows:
        if _yes(r.get("consulted_edition_before_rating_y")) or _yes(r.get("knew_this_text_y")):
            item_flag[(r["rater_id"].strip(), r["item_code"].strip())] = True
    out: list[Rating] = []
    counts = {"rows": len(rows), "blank_unrated": 0, "cannot_judge": 0}
    for r in rows:
        rater, item, opt = r["rater_id"].strip(), r["item_code"].strip(), r["option"].strip().upper()
        where = f"{r.get('_file', '?')}: rater {rater} item {item} option {opt}"
        if not rater:
            raise SheetError(f"{where}: empty rater_id")
        if (item, opt) not in units:
            raise SheetError(f"{where}: not in this packet's key")
        if (rater, item, opt) in seen:
            raise SheetError(f"{where}: rated twice")
        seen.add((rater, item, opt))
        raw = (r.get("rating_1_to_4") or "").strip()
        cj = _yes(r.get("cannot_judge_y")) or raw == "?"
        if cj:
            counts["cannot_judge"] += 1
            value = None
        elif not raw:
            counts["blank_unrated"] += 1
            continue
        else:
            try:
                value = int(float(raw))
            except ValueError as exc:
                raise SheetError(f"{where}: rating {raw!r} is not 1-4") from exc
            if value not in (1, 2, 3, 4) or float(raw) != value:
                raise SheetError(f"{where}: rating {raw!r} is not 1-4")
        out.append(Rating(rater, item, opt, value, item_flag[(rater, item)]))
    return out, counts


def _source_group(opt: dict[str, Any]) -> str:
    if opt["origin"] == "expert":
        return "edition"
    s = set(opt.get("sources") or [])
    if s & {"sonnet", "opus"}:
        return "llm"
    if "parallel" in s:
        return "retrieval"
    if "ontology" in s:
        return "ontology"
    return "ngram"


def _r(x: float, nd: int = 3) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, nd)


def _agreement(ratings: list[Rating]) -> dict[str, Any]:
    by_unit: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for r in ratings:
        if r.value is not None:
            by_unit[(r.item, r.option)][r.rater] = r.value
    raters = sorted({r for u in by_unit.values() for r in u})
    fl = fleiss_kappa([list(u.values()) for u in by_unit.values()], categories=[1, 2, 3, 4])
    flb = fleiss_kappa([[v >= 3 for v in u.values()] for u in by_unit.values()], categories=[False, True])
    pairs = []
    for a, b in itertools.combinations(raters, 2):
        common = [u for u in by_unit.values() if a in u and b in u]
        xa, xb = [u[a] for u in common], [u[b] for u in common]
        pairs.append({"raters": [a, b], "n": len(common),
                      "kappa": _r(cohen_kappa(xa, xb, categories=[1, 2, 3, 4])),
                      "kappa_quadratic": _r(cohen_kappa(xa, xb, categories=[1, 2, 3, 4], weights="quadratic")),
                      "kappa_binary_ge3": _r(cohen_kappa([v >= 3 for v in xa], [v >= 3 for v in xb],
                                                         categories=[False, True])),
                      "percent_agreement": _r(percent_agreement(xa, xb))})

    def avg(key: str) -> float | None:
        vals = [p[key] for p in pairs if p[key] is not None and p["n"] > 0]
        return _r(mean(vals)) if vals else None

    return {"raters": raters, "units_rated_by_2plus": fl["units"],
            "fleiss_kappa": _r(fl["kappa"]), "fleiss_p_observed": _r(fl["p_observed"]),
            "fleiss_p_expected": _r(fl["p_expected"]), "fleiss_kappa_binary_ge3": _r(flb["kappa"]),
            "cohen_pairwise": pairs, "cohen_mean": avg("kappa"), "cohen_quadratic_mean": avg("kappa_quadratic"),
            "cohen_binary_mean": avg("kappa_binary_ge3")}


def analyze_ratings(rows: list[dict[str, str]], key: dict[str, Any], *, n_boot: int = 2000,
                    seed: int = 0) -> dict[str, Any]:
    ratings, counts = parse_ratings(rows, key)
    main = [r for r in ratings if not r.flagged]
    items = {it["code"]: it for it in key["rating"]}
    opt_of = {(it["code"], o["label"]): o for it in key["rating"] for o in it["options"]}
    unit_vals: dict[tuple[str, str], list[int]] = defaultdict(list)
    for r in main:
        if r.value is not None:
            unit_vals[(r.item, r.option)].append(r.value)
    unit_mean = {u: mean(v) for u, v in unit_vals.items()}

    def group_stats(units: list[tuple[str, str]]) -> dict[str, Any]:
        units = [u for u in units if u in unit_mean]
        vals = [(items[u[0]]["inscription_id"], unit_mean[u]) for u in units]
        plaus = [(c, 1.0 if v >= 3 else 0.0) for c, v in vals]
        ci = cluster_bootstrap_ci(vals, n_boot=n_boot, seed=seed)
        cip = cluster_bootstrap_ci(plaus, n_boot=n_boot, seed=seed)
        return {"units": len(vals), "inscriptions": len({c for c, _ in vals}),
                "mean_rating": _r(mean([v for _, v in vals])), "mean_rating_ci95": [_r(ci[0]), _r(ci[1])],
                "share_plausible_ge3": _r(mean([v for _, v in plaus])), "share_plausible_ci95": [_r(cip[0]), _r(cip[1])]}

    all_units = list(opt_of)
    groups = {
        "edition_fill (masked)": [u for u in all_units if opt_of[u]["origin"] == "expert"],
        "ai (masked)": [u for u in all_units if opt_of[u]["origin"] == "ai" and items[u[0]]["kind"] == "masked"],
        "ai (blank)": [u for u in all_units if opt_of[u]["origin"] == "ai" and items[u[0]]["kind"] == "blank"],
    }
    for g in ("llm", "retrieval", "ngram", "ontology"):
        us = [u for u in all_units if opt_of[u]["origin"] == "ai" and _source_group(opt_of[u]) == g]
        if us:
            groups[f"ai by source: {g}"] = us
    by_group = {name: group_stats(us) for name, us in groups.items()}

    # masked: edition fill vs best AI option, per item
    paired = []
    for code, it in items.items():
        if it["kind"] != "masked":
            continue
        exp = [unit_mean[(code, o["label"])] for o in it["options"]
               if o["origin"] == "expert" and (code, o["label"]) in unit_mean]
        ai = [unit_mean[(code, o["label"])] for o in it["options"]
              if o["origin"] == "ai" and (code, o["label"]) in unit_mean]
        if exp and ai:
            paired.append((it["inscription_id"], exp[0], max(ai)))
    diffs = [(c, e - a) for c, e, a in paired]
    ci = cluster_bootstrap_ci(diffs, n_boot=n_boot, seed=seed)
    masked = {"items": len(paired),
              "mean_edition_minus_best_ai": _r(mean([d for _, d in diffs])),
              "mean_edition_minus_best_ai_ci95": [_r(ci[0]), _r(ci[1])],
              "share_best_ai_rated_at_least_edition": _r(mean([1.0 if a >= e else 0.0 for _, e, a in paired])),
              "edition_fill_also_proposed_by_ai": sum(1 for it in items.values() if it["kind"] == "masked"
                                                      for o in it["options"] if o.get("also_proposed_by_ai"))}
    # per rater: how often the edition's fill gets the rater's top score (ties count) on masked items
    per_rater: dict[str, list[float]] = defaultdict(list)
    by_rater_item: dict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for r in main:
        if r.value is not None:
            by_rater_item[(r.rater, r.item)][r.option] = r.value
    for (rater, code), opts in by_rater_item.items():
        it = items[code]
        if it["kind"] != "masked":
            continue
        exp = [o["label"] for o in it["options"] if o["origin"] == "expert"]
        if exp and exp[0] in opts:
            per_rater[rater].append(1.0 if opts[exp[0]] >= max(opts.values()) else 0.0)
    masked["edition_fill_top_rated_by_rater"] = {k: _r(mean(v)) for k, v in sorted(per_rater.items())}

    # blank: items where at least one AI proposal has mean rating >= 3
    blank_items = [it for it in items.values() if it["kind"] == "blank"]
    hits = []
    for it in blank_items:
        ms = [unit_mean[(it["code"], o["label"])] for o in it["options"] if (it["code"], o["label"]) in unit_mean]
        if ms:
            hits.append((it["inscription_id"], 1.0 if max(ms) >= 3 else 0.0))
    cib = cluster_bootstrap_ci(hits, n_boot=n_boot, seed=seed)
    blank = {"items": len(hits), "share_with_a_plausible_ai_proposal": _r(mean([h for _, h in hits])),
             "ci95": [_r(cib[0]), _r(cib[1])]}

    # calibration: AI confidence vs mean expert rating
    conf_pairs = [(opt_of[u]["confidence"], unit_mean[u]) for u in all_units
                  if opt_of[u]["origin"] == "ai" and isinstance(opt_of[u].get("confidence"), (int, float))
                  and u in unit_mean]
    calibration = {"units": len(conf_pairs),
                   "spearman_ai_confidence_vs_mean_rating": _r(spearman([c for c, _ in conf_pairs],
                                                                        [v for _, v in conf_pairs]))}
    return {
        "counts": {**counts, "ratings": len(ratings), "flagged_ratings": sum(1 for r in ratings if r.flagged),
                   "main_set_ratings": sum(1 for r in main if r.value is not None)},
        "agreement": _agreement(main), "agreement_incl_flagged": _agreement(ratings),
        "by_group": by_group, "masked": masked, "blank": blank, "calibration": calibration,
    }


# -------------------------------------------------------------------------------------------- reading -------
def _to_iso(answer: str) -> str:
    return tamil_to_iso(answer) if looks_tamil(answer) else answer


def score_answer(answer: str, target: str) -> tuple[bool, float]:
    """(exact match on the scoring form, CER clipped to 1). An empty answer is wrong with CER 1."""
    t = letters(target)
    h = letters(_to_iso(answer or ""))
    if not h:
        return False, 1.0
    return h == t, min(1.0, Levenshtein.distance(t, h) / max(1, len(t)))


def analyze_reading(rows: list[dict[str, str]], key: dict[str, Any], *, n_boot: int = 2000,
                    seed: int = 0) -> dict[str, Any]:
    items = {it["code"]: it for it in key["reading"]}
    seen: set[tuple[str, str]] = set()
    recs: list[dict[str, Any]] = []
    flagged = 0
    for r in rows:
        rater, code, cond = r["rater_id"].strip(), r["item_code"].strip(), r["condition"].strip()
        where = f"{r.get('_file', '?')}: rater {rater} item {code}"
        if code not in items:
            raise SheetError(f"{where}: not in this packet's key")
        if cond not in ("unaided", "ai_assisted"):
            raise SheetError(f"{where}: condition {cond!r}")
        if (rater, code) in seen:
            raise SheetError(f"{where}: answered twice")
        seen.add((rater, code))
        if _yes(r.get("consulted_edition_before_answering_y")) or _yes(r.get("knew_this_text_y")):
            flagged += 1
            continue
        ans = (r.get("your_restoration") or "").strip()
        ok, cer = score_answer(ans, items[code]["target"])
        secs = (r.get("seconds_taken") or "").strip()
        conf = (r.get("your_confidence_1_to_4") or "").strip()
        recs.append({"rater": rater, "item": code, "cond": cond, "answered": bool(ans), "correct": ok, "cer": cer,
                     "seconds": float(secs) if secs.replace(".", "", 1).isdigit() else None,
                     "confidence": int(conf) if conf in ("1", "2", "3", "4") else None})

    def cond_stats(cond: str) -> dict[str, Any]:
        rs = [x for x in recs if x["cond"] == cond]
        acc = [(x["item"], 1.0 if x["correct"] else 0.0) for x in rs]
        ci = cluster_bootstrap_ci(acc, n_boot=n_boot, seed=seed)
        secs = [x["seconds"] for x in rs if x["seconds"] is not None]
        confs = [x["confidence"] for x in rs if x["confidence"] is not None]
        return {"answers": len(rs), "answered_share": _r(mean([1.0 if x["answered"] else 0.0 for x in rs])),
                "exact_match": _r(mean([a for _, a in acc])), "exact_match_ci95": [_r(ci[0]), _r(ci[1])],
                "cer_clipped": _r(mean([x["cer"] for x in rs])),
                "median_seconds": _r(statistics.median(secs), 1) if secs else None,
                "mean_confidence": _r(mean(confs)) if confs else None}

    # paired by item: mean accuracy with AI minus without, over items seen in both conditions
    by_item: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for x in recs:
        by_item[x["item"]][x["cond"]].append(1.0 if x["correct"] else 0.0)
    item_diffs = [(code, mean(d["ai_assisted"]) - mean(d["unaided"])) for code, d in by_item.items()
                  if d["ai_assisted"] and d["unaided"]]
    ci = cluster_bootstrap_ci(item_diffs, n_boot=n_boot, seed=seed)
    pos = sum(1 for _, d in item_diffs if d > 0)
    neg = sum(1 for _, d in item_diffs if d < 0)
    by_rater: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for x in recs:
        by_rater[x["rater"]][x["cond"]].append(1.0 if x["correct"] else 0.0)
    rater_diffs = {k: _r(mean(v["ai_assisted"]) - mean(v["unaided"])) for k, v in sorted(by_rater.items())
                   if v["ai_assisted"] and v["unaided"]}
    rp = sum(1 for d in rater_diffs.values() if d and d > 0)
    rn = sum(1 for d in rater_diffs.values() if d and d < 0)
    # AI alone: the top suggestion on the same items
    ai_alone = [score_answer(it["suggestions"][0]["text"] if it["suggestions"] else "", it["target"])[0]
                for it in items.values()]
    return {
        "counts": {"rows": len(rows), "flagged_excluded": flagged, "scored": len(recs)},
        "unaided": cond_stats("unaided"), "ai_assisted": cond_stats("ai_assisted"),
        "ai_alone_top1_exact_match": _r(mean([1.0 if a else 0.0 for a in ai_alone])) if ai_alone else None,
        "paired_items": {"items": len(item_diffs), "mean_diff_assisted_minus_unaided": _r(mean([d for _, d in item_diffs])),
                         "ci95": [_r(ci[0]), _r(ci[1])], "items_better_with_ai": pos, "items_worse_with_ai": neg,
                         "sign_test_p": _r(sign_test_p(pos, neg))},
        "per_rater_diff_assisted_minus_unaided": rater_diffs, "raters_sign_test_p": _r(sign_test_p(rp, rn)),
    }


# --------------------------------------------------------------------------------------------- report -------
def analyze(paths: list[Path], key: dict[str, Any], *, n_boot: int = 2000, seed: int = 0) -> dict[str, Any]:
    sheets = collect_sheets(paths)
    raters = sorted({r["rater_id"].strip() for rows in sheets.values() for r in rows})
    out: dict[str, Any] = {"packet": key["meta"], "raters": raters,
                           "synthetic": bool(raters) and all(r.startswith(SYNTHETIC_PREFIX) for r in raters)}
    if any(r.startswith(SYNTHETIC_PREFIX) for r in raters) and not out["synthetic"]:
        raise SheetError("synthetic (SYN-) and real raters mixed in one analysis")
    if sheets["rating"]:
        out["rating"] = analyze_ratings(sheets["rating"], key, n_boot=n_boot, seed=seed)
    if sheets["reading"]:
        out["reading"] = analyze_reading(sheets["reading"], key, n_boot=n_boot, seed=seed)
    return out


def _fmt(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, list):
        return "[" + ", ".join(_fmt(x) for x in v) + "]"
    return str(v)


def to_markdown(res: dict[str, Any]) -> str:
    m = res["packet"]
    lines = ["# Expert validation results", ""]
    if res["synthetic"]:
        lines += [("> **SYNTHETIC RATINGS.** Generated by `python -m ezhuthu.expert synth` to test the analysis. "
                  "These numbers say nothing about restoration quality and must not be cited."), ""]
    lines += [(f"- Packet: kit v{m.get('kit_version')}, seed {m.get('seed')}, {m.get('n_rating')} rating items "
              f"({m.get('n_rating_masked')} masked, {m.get('n_rating_blank')} blank), {m.get('n_reading')} reading items."),
              f"- Proposals: router `{m.get('router')}`, ranking {m.get('ranking', '-')}.",
              f"- Raters: {len(res['raters'])} ({', '.join(res['raters'])}).", ""]
    if "rating" in res:
        r = res["rating"]
        a = r["agreement"]
        lines += ["## Blind plausibility ratings", "",
                  f"Counts: {json.dumps(r['counts'])}", "",
                  "### Inter-rater agreement (main set)", "",
                  "| measure | value |", "|---|---|",
                  f"| Fleiss' kappa, 4 categories ({a['units_rated_by_2plus']} units) | {_fmt(a['fleiss_kappa'])} |",
                  f"| Fleiss' kappa, plausible (>=3) vs not | {_fmt(a['fleiss_kappa_binary_ge3'])} |",
                  f"| Cohen's kappa, mean over rater pairs | {_fmt(a['cohen_mean'])} |",
                  f"| Cohen's kappa, quadratic weights, mean | {_fmt(a['cohen_quadratic_mean'])} |",
                  f"| Fleiss' kappa incl. flagged ratings | {_fmt(r['agreement_incl_flagged']['fleiss_kappa'])} |", "",
                  "| rater pair | n | kappa | quadratic | binary | % agree |", "|---|---|---|---|---|---|"]
        lines += [f"| {p['raters'][0]} / {p['raters'][1]} | {p['n']} | {_fmt(p['kappa'])} | "
                  f"{_fmt(p['kappa_quadratic'])} | {_fmt(p['kappa_binary_ge3'])} | {_fmt(p['percent_agreement'])} |"
                  for p in a["cohen_pairwise"]]
        lines += ["", "### Plausibility by origin (unit = one option, mean over raters; CI = bootstrap over inscriptions)",
                  "", "| group | units | inscriptions | mean rating (95% CI) | share >= 3 (95% CI) |", "|---|---|---|---|---|"]
        lines += [f"| {g} | {s['units']} | {s['inscriptions']} | {_fmt(s['mean_rating'])} {_fmt(s['mean_rating_ci95'])} | "
                  f"{_fmt(s['share_plausible_ge3'])} {_fmt(s['share_plausible_ci95'])} |" for g, s in r["by_group"].items()]
        mk, bl, ca = r["masked"], r["blank"], r["calibration"]
        lines += ["", "### Masked restorations (edition fill known)", "",
                  (f"- Items: {mk['items']}. Mean (edition fill - best AI option): {_fmt(mk['mean_edition_minus_best_ai'])} "
                  f"{_fmt(mk['mean_edition_minus_best_ai_ci95'])}."),
                  (f"- Share of items where the best AI option is rated at least as high as the edition fill: "
                  f"{_fmt(mk['share_best_ai_rated_at_least_edition'])}."),
                  f"- Edition fill also among the AI proposals (shown once): {mk['edition_fill_also_proposed_by_ai']} items.",
                  (f"- Share of items where each rater gave the edition fill their top score: "
                  f"{json.dumps(mk['edition_fill_top_rated_by_rater'])}."), "",
                  "### Blank passages (no expert fill exists)", "",
                  (f"- Items: {bl['items']}. Share with at least one AI proposal rated plausible (mean >= 3): "
                  f"{_fmt(bl['share_with_a_plausible_ai_proposal'])} {_fmt(bl['ci95'])}."), "",
                  "### Calibration", "",
                  (f"- Spearman (AI confidence vs mean rating) over {ca['units']} AI options: "
                  f"{_fmt(ca['spearman_ai_confidence_vs_mean_rating'])}."), ""]
    if "reading" in res:
        rd = res["reading"]
        lines += ["## Reading study (with / without AI suggestions)", "", f"Counts: {json.dumps(rd['counts'])}", "",
                  "| condition | answers | answered | exact match (95% CI, items) | CER clipped | median s | confidence |",
                  "|---|---|---|---|---|---|---|"]
        for c in ("unaided", "ai_assisted"):
            s = rd[c]
            lines.append(f"| {c} | {s['answers']} | {_fmt(s['answered_share'])} | {_fmt(s['exact_match'])} "
                         f"{_fmt(s['exact_match_ci95'])} | {_fmt(s['cer_clipped'])} | {_fmt(s['median_seconds'])} | "
                         f"{_fmt(s['mean_confidence'])} |")
        p = rd["paired_items"]
        lines += ["", f"- AI alone (top suggestion), same items: {_fmt(rd['ai_alone_top1_exact_match'])}.",
                  (f"- Paired by item ({p['items']} items in both conditions): assisted - unaided = "
                  f"{_fmt(p['mean_diff_assisted_minus_unaided'])} {_fmt(p['ci95'])}; better {p['items_better_with_ai']}, "
                  f"worse {p['items_worse_with_ai']}, sign test p = {_fmt(p['sign_test_p'])}."),
                  (f"- Per rater (different items per condition): {json.dumps(rd['per_rater_diff_assisted_minus_unaided'])}; "
                  f"sign test p = {_fmt(rd['raters_sign_test_p'])}."), ""]
    lines += [("Wording rule: say an AI proposal \"was rated plausible by N epigraphists\" or \"matches the edition\", "
              "never \"correct\"."), ""]
    return "\n".join(lines)
