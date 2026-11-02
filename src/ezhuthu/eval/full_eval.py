"""Full evaluation (issue #26): choose everything on VAL, then score TEST once.

    # 1. VAL, live LLM runs on a seeded VAL sample (Sonnet; Sonnet->Opus always escalating; Opus; decider variants)
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.full_eval val --n 120 --max-live-calls 320
    # 2. VAL decisions (0 Bedrock calls): strategy, escalation threshold, |llm-sonnet / |llm-opus calibration
    python -m ezhuthu.eval.full_eval decide --retrieval-report <calibrate JSON> [--write-calibration]
    # 3. TEST, every configuration once (needs a clean, committed tree)
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.full_eval test --max-live-calls 900

Per-item rows go to ``<out>/rows/<config>.jsonl`` (committed, so every number can be re-derived), LLM replies to
``.cache/llm`` (re-scoring is free). Every row of an LLM configuration lists its LLM calls with tokens and the
latency of the original call, so cost and latency are computed per configuration whether or not the replies were
cached. The test step refuses to run when ``src/`` or ``config/`` has uncommitted changes.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import os
import random
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..agent.baselines import copy_best_parallel, ngram_fill
from ..agent.calibration import CalibrationTable, fit, fit_threshold, variant_key
from ..agent.config import live_enabled, load_models_config, repo_root
from ..agent.data import BenchmarkItem, data_source, load_items
from ..agent.decider import HttpDecider, NoDecider
from ..agent.llm import PRICE_PER_MTOK, BedrockLLM, BudgetedLLM, RateLimiter, short_name
from ..agent.restorer import Restorer
from .metrics import canon, ece
from .run import code_provenance, evaluate_items, git_commit
from .stats import bootstrap_ci, paired

log = logging.getLogger(__name__)
SEED = 26
VAL_DIR = "2026-11-02-val-selection"
TEST_DIR = "2026-11-02-test-eval"
ESCALATION_GRID = (0.0, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.01)
LLM_STRATEGIES = ("self-report", "prerank", "choice-topk:3", "choice-topk:5", "noul-topk:3")
DECIDER_STRATEGIES = ("choice-all", "choice-topk", "noul-topk")


# ---------------------------------------------------------------------------------------------- running -------
def seeded_sample(items: list[BenchmarkItem], n: int, seed: int = SEED) -> list[BenchmarkItem]:
    """``n`` items drawn without replacement (seeded), returned in benchmark order."""
    if n >= len(items):
        return list(items)
    ids = set(random.Random(seed).sample(sorted(it.id for it in items), n))
    return [it for it in items if it.id in ids]


def parse_strategy(spec: str | None) -> tuple[str | None, int | None]:
    if not spec:
        return None, None
    s, _, k = spec.partition(":")
    return s, (int(k) if k else None)


# Account quotas (heisenberg, us-east-1 cross-region inference, checked 2026-11-02): Sonnet 4.6 10 requests/min,
# Opus 4.6 5 requests/min. Pacing each model at its quota keeps throttling (and retries) rare.
MODEL_RPM = {"sonnet": 10.0, "opus": 5.0}


class PacedBedrockLLM(BedrockLLM):
    """BedrockLLM with one rate limiter per model (cache hits are never paced)."""

    def __init__(self, *, rpm: float, **kw: Any):
        super().__init__(rpm=None, **kw)
        self.limiters = {m: RateLimiter(min(rpm, r) if rpm else r) for m, r in MODEL_RPM.items()}

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024):
        model_id = self.config.model_id(role)
        if self.cache.get(self.cache.key(model_id, system, prompt, max_tokens)) is None:
            lim = self.limiters.get(short_name(model_id))
            if lim is not None:
                lim.acquire()
        return super().complete(role, system, prompt, max_tokens=max_tokens)


class Runner:
    """Shares the retrieval index, n-gram model, LLM client (one ledger, one budget) and decider across runs."""

    def __init__(self, *, live: bool, max_live_calls: int, rpm: float, decider_url: str | None = None):
        os.environ.setdefault("EZHUTHU_ONTOLOGY", "direct")  # same lookup API as the MCP server, in process
        self.cfg = load_models_config()
        # 8 attempts (full-jitter backoff, cap 30 s): other teams share the account's Bedrock quota
        self.llm = BudgetedLLM(PacedBedrockLLM(rpm=rpm, retry_attempts=8), max_live_calls) if live else None
        self.http = HttpDecider(decider_url)
        self.prov = code_provenance()  # at start: the code this process imported
        self.probe = Restorer(decider=NoDecider(), calibration=CalibrationTable())
        _ = self.probe.index, self.probe.ngram

    def restorer(self, *, strategy: str | None = None, use_ontology: bool = True, escalate_below: float | None = None,
                 calibration: CalibrationTable | None = None) -> Restorer:
        strat, k = parse_strategy(strategy)
        settings = self.cfg.restorer.with_(strategy=strat, top_k=k)
        cfg = self.cfg
        if escalate_below is not None:
            cfg = dataclasses.replace(cfg, routing=dataclasses.replace(cfg.routing,
                                                                       escalate_if_confidence_below=escalate_below))
        uses_decider = settings.strategy in DECIDER_STRATEGIES or (settings.strategy_llm or "") in DECIDER_STRATEGIES
        if uses_decider and not self.http.available():
            raise RuntimeError(f"strategy {strategy} needs the local decider at {self.http.base_url}")
        r = Restorer(llm=self.llm, decider=self.http if uses_decider else NoDecider(), use_ontology=use_ontology,
                     settings=settings, config=cfg, corpus=self.probe.corpus,
                     calibration=calibration if calibration is not None else CalibrationTable())
        r.__dict__["index"], r.__dict__["ngram"] = self.probe.index, self.probe.ngram
        return r

    def run(self, name: str, items: list[BenchmarkItem], *, router: str, out: Path, workers: int = 1,
            **kw: Any) -> list[dict[str, Any]]:
        t0 = time.perf_counter()
        exhausted0 = self.llm.exhausted if self.llm else 0
        if router in ("baseline-copy", "baseline-ngram"):
            rows = baseline_rows(self.probe, items, router)
        else:
            res = evaluate_items(items, router=router, restorer=self.restorer(**kw), llm=self.llm, workers=workers)
            rows = res["items"]
        meta = {"config": name, "router": router, **{k: v for k, v in kw.items() if k != "calibration"},
                "calibration": (str(kw["calibration"].path) if kw.get("calibration") is not None
                                and kw["calibration"].path else None),
                "seconds": round(time.perf_counter() - t0, 1),
                "budget_refusals": (self.llm.exhausted - exhausted0) if self.llm else 0,
                "data_commit": git_commit(data_source().path), **self.prov,
                "decider": (self.http.health() or {}).get("model") if self.http.available() else None,
                "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
        for r in rows:
            r["config"] = name
        save_rows(out / "rows" / f"{name}.jsonl", rows, meta)
        log.info("%s: n=%d top1=%.4f (%.0fs)", name, len(rows), sum(r["top1_correct"] for r in rows) / max(1, len(rows)),
                 meta["seconds"])
        return rows


def pre_escalates(r: Restorer, it: BenchmarkItem) -> bool:
    """Whether ``restore_gap(router="routed")`` asks Opus first for this item (same rule, retrieval only)."""
    rt, st = r.config.routing, r.settings
    found = r.retrieve_parallels(it.left, it.right, it.gap_chars, k=max(st.parallels_k, st.prompt_parallels),
                                 exclude_inscription=it.inscription_id)
    pars = found[: st.prompt_parallels]
    good = any(p.fill and p.score >= 50 for p in pars)
    return r._estimate_len(it.gap_chars, pars) > rt.escalate_if_gap_chars_over or (rt.escalate_if_no_parallel
                                                                                   and not good)


def baseline_rows(probe: Restorer, items: list[BenchmarkItem], router: str) -> list[dict[str, Any]]:
    rows = []
    for it in items:
        t0 = time.perf_counter()
        if router == "baseline-copy":
            cands = copy_best_parallel(probe, it.left, it.right, it.gap_chars, exclude_inscription=it.inscription_id)
        else:
            cands = ngram_fill(probe, it.left, it.right, it.gap_chars, k=20)
        top = cands[0][0] if cands else None
        rows.append({"id": it.id, "target": it.target, "top1": top, "confidence": cands[0][1] if cands else 0.0,
                     "top1_correct": bool(top) and canon(top) == canon(it.target),
                     "in_top20": any(canon(t) == canon(it.target) for t, _ in cands[:20]),
                     "cer": _cer(it.target, top), "abstained": not cands, "hard": it.hard, "age_set": it.age_set,
                     "candidates": [[t, c] for t, c in cands[:20]],
                     "latency_ms": round((time.perf_counter() - t0) * 1000, 1)})
    return rows


def _cer(target: str, hyp: str | None) -> float:
    from rapidfuzz.distance import Levenshtein

    t, h = canon(target), canon(hyp or "")
    return round(Levenshtein.distance(t, h) / max(1, len(t)), 4)


def save_rows(path: Path, rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": meta}, ensure_ascii=False) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def load_rows(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    return lines[0]["_meta"], lines[1:]


# ---------------------------------------------------------------------------------------------- metrics -------
def llm_short(row: dict[str, Any], cfg) -> str | None:
    used = row.get("models_used") or []
    if cfg.llm.get("escalate") in used:
        return "opus"
    if cfg.llm.get("default") in used:
        return "sonnet"
    return None


def row_key(row: dict[str, Any], cfg, top_k: int) -> str | None:
    """The calibration key the restorer would look up for this row (decider model, strategy, k, LLM)."""
    if not row.get("decider_model") or not row.get("strategy"):
        return None
    return variant_key(row["decider_model"], row["strategy"], top_k, llm_short(row, cfg))


def cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """LLM calls, tokens and list-price USD for the configuration as run (every call, cached or not), plus the
    calls that were live (billed) in this run."""
    agg: dict[str, dict[str, float]] = {}
    live = 0
    for r in rows:
        for c in r.get("llm_calls") or []:
            a = agg.setdefault(c["model"], {"calls": 0, "input_tokens": 0, "output_tokens": 0})
            a["calls"] += 1
            a["input_tokens"] += c["input_tokens"]
            a["output_tokens"] += c["output_tokens"]
            live += not c["cached"]
    usd = sum(a["input_tokens"] / 1e6 * PRICE_PER_MTOK[m][0] + a["output_tokens"] / 1e6 * PRICE_PER_MTOK[m][1]
              for m, a in agg.items())
    n = max(1, len(rows))
    return {"by_model": agg, "calls": sum(int(a["calls"]) for a in agg.values()), "live_calls_this_run": live,
            "usd": round(usd, 4), "usd_per_item": round(usd / n, 5),
            "opus_items": sum(1 for r in rows if any(c["model"] == "opus" for c in r.get("llm_calls") or []))}


def latency(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-item latency as if every LLM reply were live: wall time outside LLM calls + original call latencies."""
    xs = []
    for r in rows:
        calls = r.get("llm_calls") or []
        xs.append(max(0.0, float(r.get("latency_ms") or 0.0) - float(r.get("llm_wall_ms") or 0.0))
                  + sum(c["latency_ms"] for c in calls))
    if not xs:
        return {}
    xs.sort()
    return {"p50_ms": round(statistics.median(xs), 1), "p90_ms": round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1),
            "mean_ms": round(sum(xs) / len(xs), 1)}


def filled(row: dict[str, Any], threshold: float | None) -> bool:
    """Pipeline rows carry their own fill/abstain decision (VAL calibration threshold); baseline rows fill when
    they have a candidate whose confidence reaches the VAL-fitted ``threshold``."""
    if threshold is None:
        return not row["abstained"]
    return (not row["abstained"]) and row["confidence"] >= threshold


def summarize(rows: list[dict[str, Any]], *, threshold: float | None = None, n_boot: int = 2000) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0}
    ok = [bool(r["top1_correct"]) for r in rows]
    t20 = [bool(r["in_top20"]) for r in rows]
    cer_c = [min(1.0, float(r["cer"])) for r in rows]
    conf = [float(r["confidence"]) for r in rows]
    fill = [filled(r, threshold) for r in rows]
    k = sum(fill)
    sel = [o for o, f in zip(ok, fill, strict=True) if f]
    return {
        "n": n, "top1": round(sum(ok) / n, 4), "top1_ci": bootstrap_ci([float(x) for x in ok], n_boot=n_boot),
        "top20": round(sum(t20) / n, 4), "top20_ci": bootstrap_ci([float(x) for x in t20], n_boot=n_boot),
        "cer": round(sum(float(r["cer"]) for r in rows) / n, 4), "cer_clipped": round(sum(cer_c) / n, 4),
        "cer_clipped_ci": bootstrap_ci(cer_c, n_boot=n_boot), "cer_median": round(statistics.median(
            float(r["cer"]) for r in rows), 4),
        "ece": round(ece(conf, ok), 4), "coverage": round(k / n, 4),
        "coverage_ci": bootstrap_ci([float(f) for f in fill], n_boot=n_boot),
        "selective_accuracy": round(sum(sel) / k, 4) if k else None, "filled": k,
        "filled_matching": sum(sel), "errors": sum(1 for r in rows if r.get("error")),
    }


def by_subset(rows: list[dict[str, Any]], **kw: Any) -> dict[str, Any]:
    return {"full": summarize(rows, **kw), "hard": summarize([r for r in rows if r["hard"]], **kw),
            "age": summarize([r for r in rows if r["age_set"]], **kw)}


def vs(rows: list[dict[str, Any]], base: list[dict[str, Any]]) -> dict[str, Any]:
    """Paired McNemar on top-1 against ``base`` over the items both configurations scored."""
    b = {r["id"]: r for r in base}
    common = [r for r in rows if r["id"] in b]
    out = {}
    for sub, pred in (("full", lambda r: True), ("hard", lambda r: r["hard"]), ("age", lambda r: r["age_set"])):
        xs = [r for r in common if pred(r)]
        out[sub] = {"n": len(xs), **paired([bool(r["top1_correct"]) for r in xs],
                                           [bool(b[r["id"]]["top1_correct"]) for r in xs])}
    return out


# ---------------------------------------------------------------------------------------------- VAL -----------
def cmd_val(args) -> int:
    if not live_enabled():
        print("the VAL LLM runs call Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    out = Path(args.out) / VAL_DIR
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm)
    items = seeded_sample(load_items("val"), args.n)
    log.info("VAL sample: %d items (seed %d)", len(items), SEED)
    R.run("val-copy", items, router="baseline-copy", out=out)
    R.run("val-prerank", items, router="none", out=out)
    R.run("val-sonnet", items, router="sonnet", out=out, workers=args.workers)
    R.run("val-routed-always", items, router="routed", out=out, workers=args.workers, escalate_below=1.01)
    R.run("val-opus", items, router="opus", out=out, workers=args.workers)
    for strat in LLM_STRATEGIES[1:]:
        R.run(f"val-sonnet-{strat.replace(':', 'k')}", items, router="sonnet", out=out, strategy=strat)
    usage = R.llm.inner.ledger.to_dict()
    (out / "usage.json").write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted,
                                                "max_live_calls": args.max_live_calls}, indent=1), encoding="utf-8")
    print(json.dumps(usage))
    return 0


def simulate_routed(sonnet: list[dict], always: list[dict], t: float) -> list[dict]:
    """Routed rows at escalation threshold ``t`` from the Sonnet-only run and the always-escalate run: a gap that
    pre-escalates starts on Opus (the always-escalate row has only Opus calls); otherwise Sonnet's raw top-1 below
    ``t`` escalates (always-escalate row), else the Sonnet row stands. Exact, because the LLM replies are cached
    and the restorer is deterministic given them."""
    a = {r["id"]: r for r in always}
    out = []
    for s in sonnet:
        b = a[s["id"]]
        pre = bool(b.get("llm_calls")) and all(c["model"] == "opus" for c in b["llm_calls"])
        raw = s.get("raw_confidence") or 0.0
        out.append(b if pre or raw < t else s)
    return out


def cmd_decide(args) -> int:
    """VAL decisions, 0 Bedrock calls: strategy for LLM gaps, escalation threshold, LLM calibration entries."""
    out = Path(args.out) / VAL_DIR
    cfg = load_models_config()
    rows = {p.stem: load_rows(p)[1] for p in sorted((out / "rows").glob("*.jsonl"))}
    sonnet, always = rows["val-sonnet"], rows["val-routed-always"]
    n = len(sonnet)
    dec: dict[str, Any] = {"n": n, "seed": SEED, "notes": []}

    # 1. strategy once an LLM answered: highest VAL top-1 (ties: the cheaper, decider-free one listed first)
    strat_rows = {"self-report": sonnet} | {s: rows[f"val-sonnet-{s.replace(':', 'k')}"] for s in LLM_STRATEGIES[1:]}
    table = {s: summarize(r, n_boot=500) for s, r in strat_rows.items()}
    best = max(LLM_STRATEGIES, key=lambda s: (table[s]["top1"], -LLM_STRATEGIES.index(s)))
    dec["llm_strategy"] = {"table": {s: {k: table[s][k] for k in ("top1", "top1_ci", "top20", "ece")}
                                     for s in LLM_STRATEGIES},
                           "vs_self_report": {s: paired([r["top1_correct"] for r in strat_rows[s]],
                                                       [r["top1_correct"] for r in sonnet]) for s in LLM_STRATEGIES[1:]},
                           "chosen": best,
                           "rule": "highest VAL top-1 on the Sonnet candidate pools; ties go to the decider-free "
                                   "strategy listed first (self-report, then prerank)"}
    deciders = [s for s in LLM_STRATEGIES if s.split(":")[0] in DECIDER_STRATEGIES]
    dec["llm_decider_variant"] = max(deciders, key=lambda s: (table[s]["top1"], -LLM_STRATEGIES.index(s)))
    if best != "self-report":
        dec["notes"].append(f"VAL picked {best} for LLM gaps; the escalation simulation below uses self-report "
                            "rows (re-run val-routed-always with that strategy before relying on it)")

    # 2. escalation threshold on the raw top-1 (self-report: Sonnet's own probability)
    copy = {r["id"]: r for r in rows["val-copy"]}
    grid = []
    for t in ESCALATION_GRID:
        sim = simulate_routed(sonnet, always, t)
        c = cost(sim)
        grid.append({"threshold": t, "top1": round(sum(r["top1_correct"] for r in sim) / n, 4),
                     "top1_matching": sum(r["top1_correct"] for r in sim),
                     "opus_items": c["opus_items"], "opus_share": round(c["opus_items"] / n, 4),
                     "usd_per_item": c["usd_per_item"],
                     "pre_escalated": sum(1 for r in sim if r.get("llm_calls")
                                          and all(x["model"] == "opus" for x in r["llm_calls"])),
                     "vs_copy": paired([r["top1_correct"] for r in sim], [copy[r["id"]]["top1_correct"] for r in sim])})
    top = max(g["top1"] for g in grid)
    near = [g for g in grid if g["top1"] >= top - 0.01]
    chosen_t = min(near, key=lambda g: (g["opus_items"], g["threshold"]))["threshold"]
    dec["escalation"] = {"grid": grid, "chosen": chosen_t, "current": cfg.routing.escalate_if_confidence_below,
                         "rule": "fewest Opus calls among thresholds whose VAL top-1 is within 1 percentage point of "
                                 "the best threshold's",
                         "opus_only_top1": round(sum(r["top1_correct"] for r in rows["val-opus"]) / n, 4),
                         "sonnet_only_top1": round(sum(r["top1_correct"] for r in sonnet) / n, 4)}
    cur = next(g for g in grid if g["threshold"] == cfg.routing.escalate_if_confidence_below)
    dec["escalation"]["at_current"] = cur

    # 3. calibration: |llm-sonnet from the Sonnet-only rows, |llm-opus from the routed rows (chosen t) where Opus
    # answered. Keys exactly as the restorer computes them.
    routed = simulate_routed(sonnet, always, chosen_t)
    entries: dict[str, Any] = {}
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    groups: dict[str, list[dict]] = {}
    for src, rs in (("sonnet", sonnet), ("routed", routed)):
        for r in rs:
            key = row_key(r, cfg, cfg.restorer.top_k)
            if key and (key.endswith("|llm-sonnet") and src == "sonnet" or key.endswith("|llm-opus") and src == "routed"):
                groups.setdefault(key, []).append(r)
    for s in LLM_STRATEGIES[1:]:  # decider/prerank variants on the Sonnet pools (for the decider-variant test run)
        _strat, k = parse_strategy(s)
        for r in strat_rows[s]:
            key = row_key(r, cfg, k or cfg.restorer.top_k)
            # a decider that failed falls back to self-report: those rows must not join the self-report entry
            if key and key.endswith("|llm-sonnet") and not key.startswith("fallback:"):
                groups.setdefault(key, []).append(r)
    for key, rs in sorted(groups.items()):
        c = fit([float(r.get("raw_confidence") or 0.0) for r in rs], [bool(r["top1_correct"]) for r in rs],
                split="val", fitted_at=now,
                note=f"VAL seeded sample (seed {SEED}), ontology on, n={len(rs)}; issue #26")
        entries[key] = c
    dec["calibration"] = {k: {**dataclasses.asdict(c), "provisional": c.provisional(cfg.restorer.calibration_min_n,
                                                                                   cfg.restorer.calibration_min_positives)}
                          for k, c in entries.items()}

    # 4. retrieval-only strategy (full VAL, from the calibrate report) and copy/n-gram VAL thresholds
    if args.retrieval_report:
        rep = json.loads(Path(args.retrieval_report).read_text(encoding="utf-8"))
        var = rep["variants"]
        order = ["prerank", "fallback", "choice-topk:3", "choice-topk:5", "noul-topk:3", "choice-all"]
        avail = [v for v in order if v in var]
        best_r = max(avail, key=lambda v: (var[v]["summary"]["top1"], -order.index(v)))
        dec_r = [v for v in avail if v.split(":")[0] in DECIDER_STRATEGIES]
        dec["retrieval_strategy"] = {
            "table": {v: {"top1": var[v]["summary"]["top1"], "oracle": var[v]["summary"]["oracle"],
                          "key": var[v]["summary"]["key"], "vs_copy": var[v]["vs_copy"]} for v in avail},
            "vs_best": {v: paired([r["correct"] for r in var[v]["rows"]], [r["correct"] for r in var[best_r]["rows"]])
                        for v in avail if v != best_r},
            "chosen": best_r, "decider_variant": max(dec_r, key=lambda v: var[v]["summary"]["top1"]) if dec_r else None,
            "copy_top1": rep["meta"]["copy_top1"], "n": rep["meta"]["n"], "report": args.retrieval_report,
            "rule": "highest full-VAL top-1 (n=443, retrieval candidates); ties go to the variant listed first"}
    R = Runner(live=False, max_live_calls=0, rpm=0)
    val_all = load_items("val")
    thr = {}
    for name in ("baseline-copy", "baseline-ngram"):
        rs = baseline_rows(R.probe, val_all, name)
        thr[name] = {"threshold": fit_threshold([r["confidence"] for r in rs], [r["top1_correct"] for r in rs]),
                     "val_top1": round(sum(r["top1_correct"] for r in rs) / len(rs), 4), "n": len(rs)}
    dec["baseline_thresholds"] = thr
    (out / "decisions.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.write_calibration:
        table_path = Path(args.calibration_file)
        t = CalibrationTable.load(table_path)
        if args.retrieval_calibration:
            rt = CalibrationTable.load(args.retrieval_calibration)
            t.entries.update({k: v for k, v in rt.entries.items() if k.endswith("|retrieval")})
        t.entries = {k: v for k, v in t.entries.items() if "|llm" not in k}  # the n=20 entries are replaced
        t.entries.update(entries)
        table_path.write_text(t.to_json(
            "Platt (a, b) and abstain threshold per decider variant; VAL split only (issue #26: Tamil-letter length "
            "unit, ontology on). Entries under restorer.calibration_min_n (100) items or calibration_min_positives "
            "(10) are provisional and ignored."), encoding="utf-8")
    print(json.dumps({"llm_strategy": best, "escalation": chosen_t,
                      "retrieval": dec.get("retrieval_strategy", {}).get("chosen"),
                      "calibration": {k: (v["n"], v["positives"], v["threshold"], v["provisional"])
                                      for k, v in dec["calibration"].items()}}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------------------------- TEST ----------
def cmd_test(args) -> int:
    prov = code_provenance()
    if prov["code_dirty"] and not args.allow_dirty:
        print("refusing to score TEST from uncommitted code (src/ or config/ dirty); commit first", file=sys.stderr)
        return 2
    if not live_enabled():
        print("TEST LLM configurations call Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    dec = json.loads((Path(args.out) / VAL_DIR / "decisions.json").read_text(encoding="utf-8"))
    cfg = load_models_config()
    if cfg.routing.escalate_if_confidence_below != dec["escalation"]["chosen"]:
        print("config/models.yaml routing threshold differs from the VAL decision; update it first", file=sys.stderr)
        return 2
    out = Path(args.out) / TEST_DIR
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm)
    cal = CalibrationTable.load(cfg.restorer.calibration, min_n=cfg.restorer.calibration_min_n,
                               min_positives=cfg.restorer.calibration_min_positives)
    items = load_items("test")
    sample = seeded_sample(items, 100)
    ret_dec = dec["retrieval_strategy"]["decider_variant"]
    llm_dec = dec["llm_decider_variant"]
    w = args.workers
    # Sonnet and Opus have separate Bedrock quotas, so three lanes run at once. Lane C asks Opus only for gaps the
    # routed run will send to Opus without asking Sonnet first (pre-escalation: no parallel scoring >= 50 or a gap
    # over 12 letters, decided from retrieval alone) and for the Opus-only sample; the routed run then replays them
    # from the cache and asks Opus live only for gaps escalated after Sonnet. No call is made twice.
    pre = [it for it in items if pre_escalates(R.probe, it)]
    log.info("test: %d of %d gaps pre-escalate to Opus", len(pre), len(items))

    def lane_a() -> None:
        R.run("copy", items, router="baseline-copy", out=out)
        R.run("ngram", items, router="baseline-ngram", out=out)
        R.run("prerank", items, router="none", out=out, strategy="prerank", calibration=cal)
        if cfg.restorer.strategy != "prerank":  # the shipped retrieval-only strategy, when VAL chose another
            R.run("retrieval-default", items, router="none", out=out, calibration=cal)
        R.run(f"retrieval-decider-{ret_dec.replace(':', 'k')}", items, router="none", out=out, strategy=ret_dec,
              calibration=cal)

    def lane_b() -> None:
        R.run("sonnet", items, router="sonnet", out=out, workers=w, calibration=cal)
        R.run("sonnet-noonto", items, router="sonnet", out=out, workers=w, calibration=cal, use_ontology=False)

    def lane_c() -> None:
        R.run("opus-sample100", sample, router="opus", out=out, workers=w, calibration=cal)
        ids = {it.id for it in sample}
        R.run("_opus-warmup-preescalated", [it for it in pre if it.id not in ids], router="opus",
              out=out / "_warmup", workers=w, calibration=cal)

    with ThreadPoolExecutor(3) as ex:
        for f in [ex.submit(lane_a), ex.submit(lane_b), ex.submit(lane_c)]:
            f.result()
    R.run("routed", items, router="routed", out=out, workers=w, calibration=cal)
    R.run(f"sonnet-decider-{llm_dec.replace(':', 'k')}", items, router="sonnet", out=out,
          strategy=llm_dec, calibration=cal)
    usage = R.llm.inner.ledger.to_dict()
    (out / "usage.json").write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted,
                                                "max_live_calls": args.max_live_calls, **prov}, indent=1),
                                    encoding="utf-8")
    print(json.dumps(usage))
    return 0


# ---------------------------------------------------------------------------------------------- report --------
CONFIG_LABELS = {
    "copy": "Copy baseline (best length-ok parallel)", "ngram": "Character 5-gram baseline",
    "prerank": "Retrieval only, prerank (no LLM, no decider)",
    "retrieval-default": "Retrieval only, shipped strategy",
    "sonnet": "Sonnet 4.6 (shipped pipeline, ontology on)", "sonnet-noonto": "Sonnet 4.6, ontology off (ablation)",
    "routed": "Routed Sonnet 4.6 -> Opus 4.6 (shipped)", "opus-sample100": "Opus 4.6 only (seeded 100-item sample)",
}


def _label(name: str) -> str:
    if name.startswith("retrieval-decider-"):
        return f"Retrieval only, 2B decider `{name.removeprefix('retrieval-decider-').replace('k', ':', 1)}`"
    if name.startswith("sonnet-decider-"):
        return f"Sonnet 4.6 candidates, 2B decider `{name.removeprefix('sonnet-decider-').replace('k', ':', 1)}`"
    return CONFIG_LABELS.get(name, name)


def _ci(s: dict[str, Any], key: str) -> str:
    ci = s.get(f"{key}_ci")
    return f"{s[key]} [{ci[0]}, {ci[1]}]" if ci else str(s.get(key))


def _p(x: float) -> str:
    return "<0.0001" if x < 0.0001 else f"{x:.4f}"


def build_report(out_dir: Path, dec: dict[str, Any]) -> dict[str, Any]:
    cfg = load_models_config()
    rows: dict[str, list[dict]] = {}
    metas: dict[str, dict] = {}
    order = ["copy", "ngram", "prerank", "retrieval-default"]
    for p in sorted((out_dir / "rows").glob("*.jsonl")):
        metas[p.stem], rows[p.stem] = load_rows(p)
    names = [n for n in order if n in rows] + [n for n in rows if n.startswith("retrieval-decider-")] + \
        [n for n in ("sonnet", "sonnet-noonto") if n in rows] + [n for n in rows if n.startswith("sonnet-decider-")] + \
        [n for n in ("routed", "opus-sample100") if n in rows]
    thr = dec.get("baseline_thresholds", {})
    base_thr = {"copy": thr.get("baseline-copy", {}).get("threshold"),
                "ngram": thr.get("baseline-ngram", {}).get("threshold")}
    copy = rows["copy"]
    res: dict[str, Any] = {"configs": {}}
    for n in names:
        rs = rows[n]
        res["configs"][n] = {
            "label": _label(n), "meta": metas[n], "by_subset": by_subset(rs, threshold=base_thr.get(n)),
            "vs_copy": vs(rs, copy) if n != "copy" else None, "cost": cost(rs), "latency": latency(rs),
            "escalated": sum(1 for r in rs if r.get("escalated")),
            "abstain_threshold": (base_thr.get(n) if n in base_thr else
                                  sorted({r.get("abstain_below") for r in rs if r.get("abstain_below") is not None})),
            "calibration_keys": sorted({r.get("calibration") or "none (raw)" for r in rs if "calibration" in r}),
        }
    sample_ids = {r["id"] for r in rows.get("opus-sample100", [])}
    if sample_ids:
        res["sample100"] = {n: summarize([r for r in rows[n] if r["id"] in sample_ids]) for n in names}
        res["sample100_vs_opus"] = {n: vs([r for r in rows[n] if r["id"] in sample_ids], rows["opus-sample100"])
                                    for n in names if n != "opus-sample100"}
    pairs = {}
    if "sonnet" in rows and "sonnet-noonto" in rows:
        pairs["ontology_on_vs_off"] = vs(rows["sonnet"], rows["sonnet-noonto"])
        off = {r["id"]: r for r in rows["sonnet-noonto"]}
        pairs["ontology_top1_changed"] = sum(1 for r in rows["sonnet"] if r["id"] in off
                                             and r["top1"] != off[r["id"]]["top1"])
    for n in names:
        if n.startswith("retrieval-decider-"):
            pairs[f"{n}_vs_prerank"] = vs(rows[n], rows["prerank"])
        if n.startswith("sonnet-decider-"):
            pairs[f"{n}_vs_sonnet"] = vs(rows[n], rows["sonnet"])
    if "routed" in rows:
        pairs["routed_vs_sonnet"] = vs(rows["routed"], rows["sonnet"])
        pairs["sonnet_vs_prerank"] = vs(rows["sonnet"], rows["prerank"])
    res["paired"] = pairs
    res["decisions"] = dec
    res["provenance"] = {k: metas[names[0]].get(k) for k in ("data_commit", "code_commit", "code_dirty")}
    res["provenance"]["code_dirty_any"] = any(m.get("code_dirty") for m in metas.values())
    res["provenance"]["code_commits"] = sorted({m.get("code_commit") for m in metas.values()})
    res["models"] = cfg.llm
    res["decider"] = next((m.get("decider") for m in metas.values() if m.get("decider")), None)
    return res


def render_test_md(res: dict[str, Any], *, title: str, preface: list[str]) -> str:
    pv = res["provenance"]
    L = [f"# {title}", ""] + preface + [
        "", "## Provenance", "",
        f"- Data: `benchmark/` at data commit `{pv['data_commit']}` (DHARMA-derived, CC BY-SA 4.0).",
        (f"- Code: `{pv['code_commit']}`, code_dirty={str(bool(pv['code_dirty_any'])).lower()} (every configuration "
        f"ran from {', '.join('`' + c[:7] + '`' for c in pv['code_commits'] if c)})."),
        f"- Models (config/models.yaml): default `{res['models']['default']}`, escalate `{res['models']['escalate']}`.",
        (f"- Local decider: `{res['decider']}` (strands-decider 0.2.0, `strands-decider serve`, mps). The hosted "
        "v19 decider (decider-cloud) is **not measured** here."),
        ("- Ontology: train-only build (`ontology/coverage.json` -> `splits.used = [train]`; all 862 source inscriptions "
        "are train in the current benchmark), direct lookup API (same functions the MCP server serves)."),
        ("- Every threshold, strategy and calibration below was chosen on VAL "
        "(`2026-11-02-val-selection.md`); TEST was scored once with them. Per-item rows: "
        "`2026-11-02-test-eval/rows/*.jsonl`."),
        "", "## Results on TEST (413 items)", "",
        ("Top-1 = the first candidate matches the expert restoration (normalised ISO, spaces ignored). Brackets: 95% "
        "percentile bootstrap CI (2,000 resamples of items). Coverage / selective accuracy: share of gaps the "
        "configuration fills at its VAL-fitted abstain threshold, and how often those fills match the expert. "
        "McNemar: exact two-sided test on paired top-1 against the copy baseline (only this config right / only "
        "copy right)."), ""]

    def table(sub: str, names: list[str]) -> list[str]:
        out = [("| configuration | n | top-1 [95% CI] | top-20 [95% CI] | CER mean / clipped | ECE | coverage | "
               "selective acc. | vs copy (only / only, p) |"), "|---|---|---|---|---|---|---|---|---|"]
        for n in names:
            c = res["configs"][n]
            s_ = c["by_subset"][sub]
            if not s_.get("n"):
                continue
            v = c["vs_copy"][sub] if c["vs_copy"] else None
            vtxt = f"{v['only_a']} / {v['only_b']}, p={_p(v['p_mcnemar'])}" if v else "-"
            sel = "-" if s_["selective_accuracy"] is None else f"{s_['selective_accuracy']} ({s_['filled_matching']}/{s_['filled']})"
            out.append(f"| {c['label']} | {s_['n']} | {_ci(s_, 'top1')} | {_ci(s_, 'top20')} | {s_['cer']} / "
                       f"{s_['cer_clipped']} | {s_['ece']} | {s_['coverage']} | {sel} | {vtxt} |")
        return out

    names = list(res["configs"])
    L += table("full", names)
    L += ["", "### Hard subset (317: no close parallel in another train inscription)", ""] + table("hard", names)
    L += ["", "### Age subset (51: Pallava + Uttiramerur collections)", ""] + table("age", names)
    if res.get("sample100"):
        L += ["", "### Seeded 100-item sample (seed 26), every configuration on the same items", "",
              "| configuration | top-1 [95% CI] | top-20 | CER clipped | coverage | selective acc. | vs Opus-only (only / only, p) |",
              "|---|---|---|---|---|---|---|"]
        for n in names:
            s_ = res["sample100"][n]
            v = res["sample100_vs_opus"].get(n, {}).get("full")
            vtxt = f"{v['only_a']} / {v['only_b']}, p={_p(v['p_mcnemar'])}" if v else "-"
            L.append(f"| {res['configs'][n]['label']} | {_ci(s_, 'top1')} | {s_['top20']} | {s_['cer_clipped']} | "
                     f"{s_['coverage']} | {s_['selective_accuracy']} | {vtxt} |")
    L += ["", "## Paired comparisons (exact McNemar on top-1, full test)", "",
          "| comparison | n | only first right | only second right | p |", "|---|---|---|---|---|"]
    for k, v in res["paired"].items():
        if isinstance(v, dict) and "full" in v:
            f = v["full"]
            L.append(f"| {k.replace('_', ' ')} | {f['n']} | {f['only_a']} | {f['only_b']} | {_p(f['p_mcnemar'])} |")
    if "ontology_top1_changed" in res["paired"]:
        L += ["", (f"The ontology changed Sonnet's top-1 fill on {res['paired']['ontology_top1_changed']} of 413 gaps "
              "(88 test gaps get at least one ontology hint).")]
    L += ["", "## Cost and latency", "",
          ("Calls and tokens are every LLM call the configuration makes (replies served from `.cache/llm` are counted "
          "with the tokens of the original call). USD: list prices in `ezhuthu.agent.llm.PRICE_PER_MTOK` (Sonnet "
          "$3/$15, Opus $5/$25 per MTok in/out), an estimate, not the bill. Latency per gap = local wall time outside "
          "LLM calls + the original latency of each LLM call (Apple M4 Pro; Bedrock us-east-1; throttling retries "
          "not included)."), "",
          "| configuration | LLM calls (Sonnet / Opus) | gaps that used Opus | input / output tokens | est. USD (per gap) | latency p50 / p90 (s) |",
          "|---|---|---|---|---|---|"]
    for n in names:
        c = res["configs"][n]
        bm = c["cost"]["by_model"]
        tok_in = sum(int(x["input_tokens"]) for x in bm.values())
        tok_out = sum(int(x["output_tokens"]) for x in bm.values())
        lat = c["latency"]
        L.append(f"| {c['label']} | {int(bm.get('sonnet', {}).get('calls', 0))} / {int(bm.get('opus', {}).get('calls', 0))} | "
                 f"{c['cost']['opus_items']} | {tok_in:,} / {tok_out:,} | {c['cost']['usd']} ({c['cost']['usd_per_item']}) | "
                 f"{round(lat.get('p50_ms', 0) / 1000, 2)} / {round(lat.get('p90_ms', 0) / 1000, 2)} |")
    L += ["", "## Abstain thresholds and calibration used", "",
          "| configuration | abstain threshold(s) | calibration entries applied |", "|---|---|---|"]
    for n in names:
        c = res["configs"][n]
        L.append(f"| {c['label']} | {c['abstain_threshold']} | {', '.join('`' + k + '`' for k in c['calibration_keys']) or '-'} |")
    return "\n".join(L) + "\n"


def cmd_report(args) -> int:
    root = Path(args.out)
    dec = json.loads((root / VAL_DIR / "decisions.json").read_text(encoding="utf-8"))
    res = build_report(root / TEST_DIR, dec)
    usage_p = root / TEST_DIR / "usage.json"
    if usage_p.exists():
        res["usage_test_run"] = json.loads(usage_p.read_text(encoding="utf-8"))
    pre = [line for line in Path(args.preface).read_text(encoding="utf-8").splitlines()] if args.preface else []
    (root / f"{TEST_DIR}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = render_test_md(res, title="Full TEST evaluation (2026-11-02)", preface=pre)
    if args.appendix:
        md += "\n" + Path(args.appendix).read_text(encoding="utf-8")
    (root / f"{TEST_DIR}.md").write_text(md, encoding="utf-8")
    print(root / f"{TEST_DIR}.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("val")
    v.add_argument("--n", type=int, default=120)
    v.add_argument("--max-live-calls", type=int, default=320)
    d = sub.add_parser("decide")
    d.add_argument("--retrieval-report", default=None, help="JSON written by python -m ezhuthu.eval.calibrate")
    d.add_argument("--retrieval-calibration", default=None, help="calibration JSON written by that run")
    d.add_argument("--write-calibration", action="store_true")
    d.add_argument("--calibration-file", default=str(Path(__file__).resolve().parents[1] / "agent" / "calibration.json"))
    t = sub.add_parser("test")
    t.add_argument("--max-live-calls", type=int, default=900)
    t.add_argument("--allow-dirty", action="store_true", help="never for a reported run")
    for p in (v, t):
        p.add_argument("--rpm", type=float, default=40.0)
        p.add_argument("--workers", type=int, default=4)
    for p in (v, d, t):
        p.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    r = sub.add_parser("report")
    r.add_argument("--preface", default=None, help="markdown lines to put under the title (headline, caveats)")
    r.add_argument("--appendix", default=None, help="markdown appended at the end")
    r.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("strands").setLevel(logging.WARNING)
    return {"val": cmd_val, "decide": cmd_decide, "test": cmd_test, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
