"""Full evaluation (issue #26): choose everything on VAL, then score TEST once.

    # 1. VAL, live LLM runs on a seeded VAL sample (Sonnet; Sonnet->Opus always escalating; Opus; decider variants)
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.full_eval val --n 120 --max-live-calls 320
    # 2. VAL decisions (0 Bedrock calls): strategy, escalation threshold, |llm-sonnet / |llm-opus calibration
    python -m ezhuthu.eval.full_eval decide --retrieval-report <calibrate JSON> [--write-calibration]
    # 3. TEST, every configuration once (needs a clean, committed tree). Optionally warm the reply cache first,
    #    one process per model (Sonnet and Opus have separate quotas), with no decider:
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.full_eval warm --split test --router sonnet --max-live-calls 480
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.full_eval test --max-live-calls 900
    # 4. Report (0 Bedrock calls), from the committed rows, preface and appendix
    python -m ezhuthu.eval.full_eval report

Bedrock pacing: every live call waits for its model's limiter, at the account quota (``MODEL_RPM``) times
``--quota-share``. Limiters are per process: two processes calling the same model at once must split the quota
(``--quota-share 0.5`` each). ``--rpm`` only lowers the rate further.

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
import re
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
# The strategies the VAL runs compare against (the config before issue #26's choices): retrieval-only gaps ranked by
# prerank, LLM gaps by the LLM's own probability. Every other VAL variant is named explicitly.
VAL_BASELINE = {"retrieval": "prerank", "llm": "self-report"}


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


def model_rates(rpm: float | None = None, quota_share: float = 1.0) -> dict[str, float]:
    """Requests a minute per model: its account quota times ``quota_share``, lowered to ``rpm`` when given."""
    if not 0 < quota_share <= 1:
        raise ValueError("quota_share must be in (0, 1]")
    return {m: min(rpm, r * quota_share) if rpm else r * quota_share for m, r in MODEL_RPM.items()}


class PacedBedrockLLM(BedrockLLM):
    """BedrockLLM with one rate limiter per model (cache hits are never paced). The limiters live in this process:
    another process calling the same model needs its own share of the quota (``quota_share``)."""

    def __init__(self, *, rpm: float | None = None, quota_share: float = 1.0, **kw: Any):
        super().__init__(rpm=None, **kw)
        self.rates = model_rates(rpm, quota_share)
        self.limiters = {m: RateLimiter(r) for m, r in self.rates.items()}

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024):
        model_id = self.config.model_id(role)
        if self.cache.get(self.cache.key(model_id, system, prompt, max_tokens)) is None:
            lim = self.limiters.get(short_name(model_id))
            if lim is not None:
                lim.acquire()
        return super().complete(role, system, prompt, max_tokens=max_tokens)


class Runner:
    """Shares the retrieval index, n-gram model, LLM client (one ledger, one budget) and decider across runs."""

    def __init__(self, *, live: bool, max_live_calls: int, rpm: float | None = None, quota_share: float = 1.0,
                 decider_url: str | None = None):
        os.environ.setdefault("EZHUTHU_ONTOLOGY", "direct")  # same lookup API as the MCP server, in process
        self.cfg = load_models_config()
        # 8 attempts (full-jitter backoff, cap 30 s): other teams share the account's Bedrock quota
        self.llm = (BudgetedLLM(PacedBedrockLLM(rpm=rpm, quota_share=quota_share, retry_attempts=8), max_live_calls)
                    if live else None)
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
        log.info("start %s: %d items, router %s", name, len(items), router)
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
    out.mkdir(parents=True, exist_ok=True)
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    items = seeded_sample(load_items("val"), args.n)
    log.info("VAL sample: %d items (seed %d)", len(items), SEED)
    # Strategies are pinned (VAL_BASELINE), not read from config/models.yaml: the config holds the strategies these
    # runs choose, so a re-run after the choice would otherwise score the chosen strategy as the baseline.
    R.run("val-copy", items, router="baseline-copy", out=out)
    R.run("val-prerank", items, router="none", out=out, strategy=VAL_BASELINE["retrieval"])
    R.run("val-sonnet", items, router="sonnet", out=out, workers=args.workers, strategy=VAL_BASELINE["llm"])
    R.run("val-routed-always", items, router="routed", out=out, workers=args.workers, escalate_below=1.01,
          strategy=VAL_BASELINE["llm"])
    R.run("val-opus", items, router="opus", out=out, workers=args.workers, strategy=VAL_BASELINE["llm"])
    for strat in LLM_STRATEGIES[1:]:
        R.run(f"val-sonnet-{strat.replace(':', 'k')}", items, router="sonnet", out=out, strategy=strat)
    usage = R.llm.inner.ledger.to_dict()
    (out / args.ledger).write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted,
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
    opus_rows = rows["val-opus"]
    if best != "self-report":
        # Replay the routed (always-escalate) and Opus runs with the chosen strategy: every LLM reply is cached, so
        # this makes 0 Bedrock calls (the budget is 0: a cache miss would be refused, not billed).
        R = Runner(live=True, max_live_calls=0)
        items = seeded_sample(load_items("val"), n)
        slug = best.replace(":", "k")
        always = R.run(f"val-routed-always-{slug}", items, router="routed", out=out, strategy=best,
                       escalate_below=1.01)
        opus_rows = R.run(f"val-opus-{slug}", items, router="opus", out=out, strategy=best)
        sonnet = strat_rows[best]
        if R.llm.exhausted:
            raise RuntimeError(f"{R.llm.exhausted} LLM replies were not cached; the replay is not exact")
        dec["notes"].append(f"VAL picked {best} for LLM gaps: the escalation grid and the LLM calibration below use "
                            f"its rows (val-sonnet-{slug}, val-routed-always-{slug}, val-opus-{slug}; replayed from "
                            "the cache, 0 Bedrock calls). Its raw top-1 is the decider's probability.")

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
                         "opus_only_top1": round(sum(r["top1_correct"] for r in opus_rows) / n, 4),
                         "sonnet_only_top1": round(sum(r["top1_correct"] for r in sonnet) / n, 4)}
    cur = next(g for g in grid if g["threshold"] == cfg.routing.escalate_if_confidence_below)
    dec["escalation"]["at_current"] = cur

    # 3. calibration: |llm-sonnet from the Sonnet-only rows, |llm-opus from the routed rows (chosen t) where Opus
    # answered. Keys exactly as the restorer computes them.
    routed = simulate_routed(sonnet, always, chosen_t)
    entries: dict[str, Any] = {}
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    groups: dict[str, list[dict]] = {}
    best_k = parse_strategy(best)[1] or cfg.restorer.top_k
    for src, rs in (("sonnet", sonnet), ("routed", routed)):
        for r in rs:
            key = row_key(r, cfg, best_k)
            if key and (key.endswith("|llm-sonnet") and src == "sonnet" or key.endswith("|llm-opus") and src == "routed"):
                groups.setdefault(key, []).append(r)
    for s in LLM_STRATEGIES[1:]:  # decider/prerank variants on the Sonnet pools (for the decider-variant test run)
        if s == best:  # already in its group above
            continue
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
    R = Runner(live=False, max_live_calls=0)
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
    want_llm = dec["llm_strategy"]["chosen"]
    want_ret = {"fallback": "self-report"}.get(dec["retrieval_strategy"]["chosen"],
                                               dec["retrieval_strategy"]["chosen"])
    got_llm = f"{cfg.restorer.strategy_llm}:{cfg.restorer.top_k}" if cfg.restorer.strategy_llm in (
        "choice-topk", "noul-topk") else cfg.restorer.strategy_llm
    if got_llm != want_llm or cfg.restorer.strategy != want_ret.split(":")[0]:
        print(f"config/models.yaml restorer strategies ({cfg.restorer.strategy} / {got_llm}) differ from the VAL "
              f"decisions ({want_ret} / {want_llm}); update it first", file=sys.stderr)
        return 2
    out = Path(args.out) / TEST_DIR
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
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

    hinted = [it for it in items if R.probe.ontology.hints_for_gap(it.left, it.right)]
    log.info("test: %d of %d gaps get an ontology hint", len(hinted), len(items))

    def lane_a() -> None:  # retrieval only (0 Bedrock calls); the decider row is decider-bound
        R.run("copy", items, router="baseline-copy", out=out)
        R.run("ngram", items, router="baseline-ngram", out=out)
        R.run("prerank", items, router="none", out=out, strategy="prerank", calibration=cal)
        if cfg.restorer.strategy != "prerank":  # the shipped retrieval-only strategy, when VAL chose another
            R.run("retrieval-default", items, router="none", out=out, calibration=cal)
        R.run(f"retrieval-decider-{ret_dec.replace(':', 'k')}", items, router="none", out=out, strategy=ret_dec,
              calibration=cal)

    def lane_b() -> None:  # Sonnet (10 requests/min)
        R.run("sonnet", items, router="sonnet", out=out, workers=w, calibration=cal)
        # Ablation: a gap with no ontology hint has byte-identical restorer input with the ontology on or off (no
        # hint in the prompt, no ontology candidate), so only the hinted gaps are re-run without the ontology.
        R.run("sonnet-noonto-hinted", hinted, router="sonnet", out=out, workers=w, calibration=cal,
              use_ontology=False)

    def lane_c() -> None:  # Opus (5 requests/min): warm the cache without the decider, then the scored sample
        ids = {it.id for it in sample}
        warm = sample + [it for it in pre if it.id not in ids]
        R.run("_opus-warmup", warm, router="opus", out=Path(".cache") / "runs" / "warmup", workers=w,
              strategy="self-report", calibration=CalibrationTable())
        R.run("opus-sample100", sample, router="opus", out=out, workers=w, calibration=cal)

    def guarded(fn):
        def run() -> None:
            try:
                fn()
            except Exception:
                log.exception("lane %s failed", fn.__name__)
                raise
        return run

    with ThreadPoolExecutor(3) as ex:
        futs = [ex.submit(guarded(f)) for f in (lane_a, lane_b, lane_c)]
        for f in futs:
            f.result()
    R.run("routed", items, router="routed", out=out, workers=w, calibration=cal)
    if llm_dec != dec["llm_strategy"]["chosen"]:  # else the shipped "sonnet" row already is the decider row
        R.run(f"sonnet-decider-{llm_dec.replace(':', 'k')}", items, router="sonnet", out=out,
              strategy=llm_dec, calibration=cal)
    usage = R.llm.inner.ledger.to_dict()
    (out / args.ledger).write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted,
                                                "max_live_calls": args.max_live_calls, **prov}, indent=1),
                                    encoding="utf-8")
    print(json.dumps(usage))
    return 0


# ---------------------------------------------------------------------------------------------- warm-up -------
def cmd_warm(args) -> int:
    """Fill ``.cache/llm`` with one model's replies before a scored run, without the decider (the LLM prompts do not
    depend on the ranking strategy, so the scored run replays them byte for byte). Nothing here is scored: the rows go
    to ``.cache/runs/warmup`` and only the usage ledger is kept, in ``<split dir>/usage-warm-<name>.json``.

    ``--split test``: every TEST gap (``--hinted-noonto``: the ontology-hinted gaps with the ontology off, as the
    ablation row asks them; ``--router opus``: the seeded 100-gap sample plus the gaps that pre-escalate).
    ``--split val``: the seeded VAL sample of ``--n``. ``--reverse`` walks the items backwards, so a concurrent scored
    run meets the warm-up halfway; give each process its share of the quota (``--quota-share``)."""
    if not live_enabled():
        print("warming the cache calls Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    prov = code_provenance()
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    if args.split == "test":
        items = load_items("test")
        if args.router == "opus":
            sample_ids = {it.id for it in seeded_sample(items, 100)}
            items = [it for it in items if it.id in sample_ids or pre_escalates(R.probe, it)]
        split_dir = TEST_DIR
    else:
        items = seeded_sample(load_items("val"), args.n)
        split_dir = VAL_DIR
    if args.hinted_noonto:
        items = [it for it in items if R.probe.ontology.hints_for_gap(it.left, it.right)]
    if args.reverse:
        items = list(reversed(items))
    name = f"{args.split}-{args.router}" + ("-noonto-hinted" if args.hinted_noonto else "")
    R.run(f"_warm-{name}", items, router=args.router, out=Path(args.cache_out), workers=args.workers,
          strategy="self-report", calibration=CalibrationTable(), use_ontology=not args.hinted_noonto)
    led = {"usage": R.llm.inner.ledger.to_dict(), "budget_refusals": R.llm.exhausted,
           "max_live_calls": args.max_live_calls, "items": len(items), "router": args.router,
           "rates_rpm": R.llm.inner.rates, **prov}
    path = Path(args.out) / split_dir / f"usage-warm-{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(led, indent=1), encoding="utf-8")
    print(json.dumps(led["usage"]))
    return 0


# ---------------------------------------------------------------------------------------------- report --------
CONFIG_LABELS = {
    "copy": "Copy baseline (best length-ok parallel)", "ngram": "Character 5-gram baseline",
    "prerank": "Retrieval only, prerank (no LLM, no decider)",
    "retrieval-default": "Retrieval only, VAL-chosen strategy",
    "sonnet": "Sonnet 4.6 (VAL-chosen config, local 2B decider, ontology on)", "sonnet-noonto-hinted": "Sonnet 4.6, ontology off (ablation; the 88 hinted gaps)",
    "routed": "Routed Sonnet 4.6 -> Opus 4.6 (VAL-chosen config, local 2B decider)",
    "sonnet-prerank": "Sonnet 4.6 candidates, prerank instead of the decider",
    "routed-prerank": "Routed, prerank instead of the decider", "opus-sample100": "Opus 4.6 only (seeded 100-item sample)",
}


def strategy_from_slug(slug: str) -> str:
    """``choice-topkk3`` (file-name form, ':' -> 'k') -> ``choice-topk:3``."""
    m = re.match(r"^(.*-topk)k(\d+)$", slug)
    return f"{m.group(1)}:{m.group(2)}" if m else slug


def _label(name: str) -> str:
    if name.startswith("retrieval-decider-"):
        return f"Retrieval only, 2B decider `{strategy_from_slug(name.removeprefix('retrieval-decider-'))}`"
    if name.startswith("sonnet-decider-"):
        return f"Sonnet 4.6 candidates, 2B decider `{strategy_from_slug(name.removeprefix('sonnet-decider-'))}`"
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
        [n for n in ("sonnet", "sonnet-noonto-hinted") if n in rows] + [n for n in rows if n.startswith("sonnet-decider-")] + \
        [n for n in ("sonnet-prerank", "routed", "routed-prerank", "opus-sample100") if n in rows]
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
            # gaps whose only LLM calls are Opus: routed sent them to Opus without asking Sonnet (pre-escalation)
            "pre_escalated": sum(1 for r in rs if r.get("llm_calls") and all(c["model"] == "opus" for c in r["llm_calls"])),
            "abstain_threshold": (base_thr.get(n) if n in base_thr else
                                  sorted({r.get("abstain_below") for r in rs if r.get("abstain_below") is not None})),
            "calibration_keys": sorted({r.get("calibration") or "none (raw)" for r in rs if "calibration" in r}),
        }
    sample_ids = {r["id"] for r in rows.get("opus-sample100", [])}
    if sample_ids:
        res["sample100"] = {n: summarize([r for r in rows[n] if r["id"] in sample_ids], threshold=base_thr.get(n))
                            for n in names}
        res["sample100_vs_opus"] = {n: vs([r for r in rows[n] if r["id"] in sample_ids], rows["opus-sample100"])
                                    for n in names if n != "opus-sample100"}
    pairs = {}
    if "sonnet" in rows and "sonnet-noonto-hinted" in rows:
        pairs["ontology_on_vs_off"] = vs(rows["sonnet"], rows["sonnet-noonto-hinted"])
        off = {r["id"]: r for r in rows["sonnet-noonto-hinted"]}
        pairs["ontology_top1_changed"] = sum(1 for r in rows["sonnet"] if r["id"] in off
                                             and r["top1"] != off[r["id"]]["top1"])
    for n in names:
        if n.startswith("retrieval-decider-"):
            pairs[f"{n}_vs_prerank"] = vs(rows[n], rows["prerank"])
        if n.startswith("sonnet-decider-"):
            pairs[f"{n}_vs_sonnet"] = vs(rows[n], rows["sonnet"])
    if "routed" in rows:
        pairs["routed_vs_sonnet"] = vs(rows["routed"], rows["sonnet"])
        pairs["routed_vs_ngram"] = vs(rows["routed"], rows["ngram"])
        pairs["routed_vs_prerank"] = vs(rows["routed"], rows["prerank"])
    for a, b in (("sonnet", "sonnet-prerank"), ("routed", "routed-prerank")):
        if a in rows and b in rows:
            pairs[f"{a}_decider_vs_prerank"] = vs(rows[a], rows[b])
        pairs["sonnet_vs_prerank"] = vs(rows["sonnet"], rows["prerank"])
    res["paired"] = pairs
    # gap length (Tamil letters): 68% of TEST gaps are a single letter (VAL: 46%), so top-1 is reported per bucket
    glen = {it.id: it.gap_chars for it in load_items("test")}
    buckets = (("1 letter", 1, 1), ("2-3 letters", 2, 3), ("4+ letters", 4, 10 ** 6))
    res["by_gap_length"] = {n: {b: summarize([r for r in rows[n] if lo <= glen.get(r["id"], 0) <= hi], n_boot=500)
                                for b, lo, hi in buckets} for n in names}
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
        (f"- Code: code_dirty={str(bool(pv['code_dirty_any'])).lower()} for every configuration; commits "
         f"{', '.join('`' + c[:7] + '`' for c in pv['code_commits'] if c)}. Each rows file names its own commit; "
         "the run history (first pass, repairs, re-scores) is under \"How this run went\"."),
        f"- Models (config/models.yaml): default `{res['models']['default']}`, escalate `{res['models']['escalate']}`.",
        (f"- Local decider: `{res['decider']}` (strands-decider 0.2.0, `strands-decider serve`, mps). The hosted "
         "v19 decider (decider-cloud) was not part of this evaluation."),
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
    if res.get("by_gap_length"):
        bl = list(next(iter(res["by_gap_length"].values())))
        L += ["", "### Top-1 by gap length (Tamil letters)", "",
              ("68% of TEST gaps are a single letter (VAL: 46%), which is why every system scores higher on TEST than on "
              "VAL; read the longer-gap columns for restoration of words."), "",
              "| configuration | " + " | ".join(f"{b} (n={res['by_gap_length'][names[0]][b]['n']})" for b in bl) + " |",
              "|---|" + "---|" * len(bl)]
        for n in names:
            cells = []
            for b in bl:
                s_ = res["by_gap_length"][n][b]
                cells.append("-" if not s_.get("n") else _ci(s_, "top1"))
            L.append(f"| {res['configs'][n]['label']} | " + " | ".join(cells) + " |")
    L += ["", "## Paired comparisons (exact McNemar on top-1, full test)", "",
          "| comparison | n | only first right | only second right | p |", "|---|---|---|---|---|"]
    for k, v in res["paired"].items():
        if isinstance(v, dict) and "full" in v:
            f = v["full"]
            L.append(f"| {k.replace('_', ' ')} | {f['n']} | {f['only_a']} | {f['only_b']} | {_p(f['p_mcnemar'])} |")
    if "ontology_top1_changed" in res["paired"]:
        n_h = res["paired"]["ontology_on_vs_off"]["full"]["n"]
        L += ["", (f"Ontology ablation: {n_h} of 413 test gaps get at least one ontology hint; only those were re-run "
                   "with the ontology off (the other gaps have byte-identical restorer input either way: no hint in the "
                   f"prompt, no ontology candidate). The ontology changed Sonnet's top-1 fill on "
                   f"{res['paired']['ontology_top1_changed']} of the {n_h}.")]
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
    raw = [res["configs"][n]["label"] for n in names if "none (raw)" in res["configs"][n]["calibration_keys"]]
    if raw:
        L += ["", (f"Not comparable: {'; '.join(raw)}. Some of its gaps have no calibration entry for the strategy and "
                   "LLM that answered (`none (raw)`: e.g. no `prerank|...|llm-opus` entry was fitted on VAL), so they "
                   "fill or abstain at the raw 0.5 threshold; its coverage and selective accuracy are therefore not "
                   "comparable with the calibrated rows'. Its top-1, top-20 and CER are.")]
    led = res.get("live_call_ledgers")
    if led:
        L += ["", "## Live Bedrock calls by ledger", "", led.get("note", ""), "",
              "| phase | split | how it ran | ledger | Sonnet | Opus | total |", "|---|---|---|---|---|---|---|"]
        for e in led["entries"]:
            L.append(f"| {e['phase']} | {e['split']} | {e['how']} | {e['source']} | {e['sonnet']} | {e['opus']} | "
                     f"{e['sonnet'] + e['opus']} |")
        t = led["totals"]
        L += [f"| **all** | | | | {t['sonnet']} | {t['opus']} | {t['sonnet'] + t['opus']} |", ""]
        L += [f"- {x}" for x in led.get("checks", [])]
    return "\n".join(L) + "\n"


def cmd_report(args) -> int:
    root = Path(args.out)
    dec = json.loads((root / VAL_DIR / "decisions.json").read_text(encoding="utf-8"))
    res = build_report(root / TEST_DIR, dec)
    usage_p = root / TEST_DIR / "usage.json"
    if usage_p.exists():
        res["usage_test_run"] = json.loads(usage_p.read_text(encoding="utf-8"))
    led_p = root / TEST_DIR / "usage-ledgers.json"
    if led_p.exists():
        res["live_call_ledgers"] = json.loads(led_p.read_text(encoding="utf-8"))
    preface = Path(args.preface) if args.preface else root / TEST_DIR / "preface.md"
    appendix = Path(args.appendix) if args.appendix else root / TEST_DIR / "appendix.md"
    pre = preface.read_text(encoding="utf-8").splitlines() if preface.exists() else []
    (root / f"{TEST_DIR}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    md = render_test_md(res, title="Full TEST evaluation (2026-11-02)", preface=pre)
    if appendix.exists():
        md += "\n" + appendix.read_text(encoding="utf-8")
    (root / f"{TEST_DIR}.md").write_text(md, encoding="utf-8")
    print(root / f"{TEST_DIR}.md")
    return 0


def render_val_md(dec: dict[str, Any], metas: dict[str, dict]) -> str:
    """VAL selection report: every choice the TEST run uses, with the VAL evidence behind it."""
    m = next(iter(metas.values()), {})
    L = ["# VAL selection for the full test evaluation (2026-11-02, issue #26)", "",
         ("> **VAL split only (development data).** Everything the TEST run uses was chosen here, by the rules "
         "stated below, before TEST was scored. These numbers are not restoration quality and must not be cited "
         "as such; in-sample calibration numbers are optimistic."), "",
         (f"- LLM runs: seeded VAL sample of {dec['n']} items (seed {dec['seed']}), ontology on (train-only build), "
         "gap lengths in Tamil letters. Per-item rows: `2026-11-02-val-selection/rows/*.jsonl`."),
         (f"- Data commit `{m.get('data_commit')}`; code commits "
         f"{', '.join(sorted({'`' + (x.get('code_commit') or '?')[:7] + '`' for x in metas.values()}))}; "
         f"code_dirty={str(any(x.get('code_dirty') for x in metas.values())).lower()}."),
         f"- Decider: `{m.get('decider')}` (local, strands-decider 0.2.0).", ""]
    rs = dec.get("retrieval_strategy")
    if rs:
        L += ["## 1. Retrieval-only gaps (no LLM): strategy", "",
              (f"Full VAL, n = {rs['n']}, retrieval + copy floor + 5-gram + ontology candidates. Copy baseline top-1 "
              f"{rs['copy_top1']}. Rule: {rs['rule']}."), "",
              "| variant | top-1 | target in candidates | vs copy (only variant / only copy) | vs chosen (only / only, p) |",
              "|---|---|---|---|---|"]
        for v, t in rs["table"].items():
            vb = rs["vs_best"].get(v)
            vtxt = "chosen" if vb is None else f"{vb['only_a']} / {vb['only_b']}, p={_p(vb['p_mcnemar'])}"
            L.append(f"| {v} | {t['top1']} | {t['oracle']} | {t['vs_copy']['only_variant']} / {t['vs_copy']['only_copy']} "
                     f"| {vtxt} |")
        L += ["", ("`fallback` is restorer strategy `self-report` with no LLM fill: each retrieval candidate scores "
                   "best parallel match x share of parallels agreeing (halved when the length is off); no decider "
                   "call.")]
        L += ["", (f"Chosen: **{rs['chosen']}**. Best decider variant (scored on TEST as the decider row): "
              f"**{rs['decider_variant']}**."), ""]
    ls = dec["llm_strategy"]
    L += ["## 2. Gaps where an LLM answered: strategy", "",
          (f"Sonnet 4.6 candidate pools on the VAL sample (the Sonnet replies are cached, so every variant ranks the "
          f"same pools). Rule: {ls['rule']}."), "",
          "| strategy | top-1 [95% CI] | top-20 | ECE (raw) | vs self-report (only / only, p) |", "|---|---|---|---|---|"]
    for k, t in ls["table"].items():
        v = ls["vs_self_report"].get(k)
        vtxt = "-" if v is None else f"{v['only_a']} / {v['only_b']}, p={_p(v['p_mcnemar'])}"
        L.append(f"| {k} | {_ci(t, 'top1')} | {t['top20']} | {t['ece']} | {vtxt} |")
    L += ["", f"Chosen: **{ls['chosen']}**. Best decider variant on LLM pools: **{dec['llm_decider_variant']}**.", ""]
    es = dec["escalation"]
    L += ["## 3. Escalation threshold (Sonnet 4.6 -> Opus 4.6)", "",
          ("Simulated exactly from two runs on the same items: Sonnet only, and routed with escalation after every "
          "Sonnet answer (threshold 1.01); a gap that pre-escalates (no parallel scoring >= 50, or a gap over 12 "
          f"letters) goes to Opus first whatever the threshold. Rule: {es['rule']}."), "",
          f"Sonnet only: top-1 {es['sonnet_only_top1']}; Opus only: {es['opus_only_top1']}.", "",
          "| raw threshold | top-1 | gaps that use Opus | pre-escalated | est. USD per gap | vs copy (only / only, p) |",
          "|---|---|---|---|---|---|"]
    for g in es["grid"]:
        mark = " (chosen)" if g["threshold"] == es["chosen"] else (" (was)" if g["threshold"] == es["current"] else "")
        v = g["vs_copy"]
        L.append(f"| {g['threshold']}{mark} | {g['top1']} ({g['top1_matching']}/{dec['n']}) | {g['opus_items']} "
                 f"({g['opus_share']}) | {g['pre_escalated']} | {g['usd_per_item']} | {v['only_a']} / {v['only_b']}, "
                 f"p={_p(v['p_mcnemar'])} |")
    L += ["", (f"Chosen: **{es['chosen']}** (config/models.yaml `routing.escalate_if_confidence_below`; was "
          f"{es['current']}). At {es['current']}, {es['at_current']['opus_items']} of {dec['n']} VAL gaps "
          f"({es['at_current']['opus_share']}) use Opus, {es['at_current']['pre_escalated']} of them by pre-escalation."),
          "", "## 4. Calibration entries written to `src/ezhuthu/agent/calibration.json`", "",
          "| key | n | positives | a | b | abstain threshold | used by the restorer |", "|---|---|---|---|---|---|---|"]
    for k, c in dec["calibration"].items():
        L.append(f"| `{k}` | {c['n']} | {c['positives']} | {c['a']} | {c['b']} | {c['threshold']} | "
                 f"{'no (provisional)' if c['provisional'] else 'yes'} |")
    bt = dec.get("baseline_thresholds", {})
    if bt:
        L += ["", "Baseline abstain thresholds (raw confidence, fitted on full VAL, used for coverage on TEST): "
              + "; ".join(f"{k} {v['threshold']} (VAL top-1 {v['val_top1']}, n={v['n']})" for k, v in bt.items()) + "."]
    if dec.get("notes"):
        L += ["", "## Notes", ""] + [f"- {x}" for x in dec["notes"]]
    return "\n".join(L) + "\n"


def cmd_val_report(args) -> int:
    root = Path(args.out)
    dec = json.loads((root / VAL_DIR / "decisions.json").read_text(encoding="utf-8"))
    metas = {p.stem: load_rows(p)[0] for p in sorted((root / VAL_DIR / "rows").glob("*.jsonl"))}
    (root / f"{VAL_DIR}.md").write_text(render_val_md(dec, metas), encoding="utf-8")
    print(root / f"{VAL_DIR}.md")
    return 0


def cmd_repair(args) -> int:
    """Re-run, from the LLM cache, every TEST configuration whose first pass lost items to Bedrock throttling (an
    ``error`` row, scored as wrong + abstained). Nothing is re-chosen: same configuration, same calibration, same
    items; answered items replay their cached replies, so only the lost calls are made live. The rows file keeps the
    first pass's error ids in its meta."""
    if not live_enabled():
        print("set EZHUTHU_LIVE=1 (the lost calls are live)", file=sys.stderr)
        return 2
    prov = code_provenance()
    if prov["code_dirty"]:
        print("refusing to repair from uncommitted code", file=sys.stderr)
        return 2
    out = Path(args.out) / TEST_DIR
    cfg = load_models_config()
    cal = CalibrationTable.load(cfg.restorer.calibration, min_n=cfg.restorer.calibration_min_n,
                               min_positives=cfg.restorer.calibration_min_positives)
    R = Runner(live=True, max_live_calls=args.max_live_calls, quota_share=args.quota_share)
    by_id = {it.id: it for it in load_items("test")}
    for p in sorted((out / "rows").glob("*.jsonl")):
        meta, rows = load_rows(p)
        bad = [r["id"] for r in rows if r.get("error")]
        if not bad:
            continue
        kw = {k: meta[k] for k in ("strategy", "use_ontology", "escalate_below") if meta.get(k) is not None}
        items = [by_id[r["id"]] for r in rows]
        log.info("repair %s: %d error rows of %d", p.stem, len(bad), len(rows))
        new = R.run(p.stem, items, router=meta["router"], out=out, workers=args.workers, calibration=cal, **kw)
        nmeta, nrows = load_rows(p)
        nmeta["first_pass"] = {"error_ids": bad, "code_commit": meta.get("code_commit"),
                               "date": meta.get("date"), "seconds": meta.get("seconds")}
        changed = sum(1 for a, b in zip(rows, new, strict=True) if a["id"] not in bad and a["top1"] != b["top1"])
        nmeta["first_pass"]["non_error_rows_changed"] = changed
        save_rows(p, nrows, nmeta)
    usage = R.llm.inner.ledger.to_dict()
    (out / "usage-repair.json").write_text(json.dumps({"usage": usage, **prov}, indent=1), encoding="utf-8")
    print(json.dumps(usage))
    return 0


EXTRA_CONFIGS = {  # added after the main pass to answer "does the decider beat prerank on LLM candidates?"
    "sonnet-prerank": {"router": "sonnet", "strategy": "prerank"},
    "routed-prerank": {"router": "routed", "strategy": "prerank"},
}


def cmd_extra(args) -> int:
    """Score the shipped LLM pipelines with ``prerank`` instead of the decider, from the LLM cache. No setting is
    re-chosen; these rows only answer whether the 2B decider beats prerank on LLM candidates on TEST. A routed gap
    whose prerank top-1 is under the escalation threshold where the decider's was not needs a live Opus call."""
    if not live_enabled():
        print("set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    if code_provenance()["code_dirty"]:
        print("refusing to score from uncommitted code", file=sys.stderr)
        return 2
    out = Path(args.out) / TEST_DIR
    cfg = load_models_config()
    cal = CalibrationTable.load(cfg.restorer.calibration, min_n=cfg.restorer.calibration_min_n,
                               min_positives=cfg.restorer.calibration_min_positives)
    R = Runner(live=True, max_live_calls=args.max_live_calls, quota_share=args.quota_share)
    items = load_items("test")
    for name, kw in EXTRA_CONFIGS.items():
        R.run(name, items, out=out, workers=args.workers, calibration=cal, **kw)
    print(json.dumps({"usage": R.llm.inner.ledger.to_dict(), "budget_refusals": R.llm.exhausted}))
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
    w = sub.add_parser("warm")
    w.add_argument("--split", choices=["val", "test"], required=True)
    w.add_argument("--router", choices=["sonnet", "opus"], required=True)
    w.add_argument("--n", type=int, default=120, help="VAL sample size (seed 26)")
    w.add_argument("--hinted-noonto", action="store_true")
    w.add_argument("--reverse", action="store_true")
    w.add_argument("--max-live-calls", type=int, default=480)
    w.add_argument("--cache-out", default=str(Path(".cache") / "runs" / "warmup"))
    for p in (v, t, w):
        p.add_argument("--rpm", type=float, default=None, help="lower the per-model rate further (requests/min)")
        p.add_argument("--workers", type=int, default=4)
    for p in (v, d, t, w):
        p.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    ex = sub.add_parser("extra")
    ex.add_argument("--max-live-calls", type=int, default=60)
    ex.add_argument("--workers", type=int, default=3)
    ex.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    rp = sub.add_parser("repair")
    rp.add_argument("--max-live-calls", type=int, default=60)
    rp.add_argument("--workers", type=int, default=2)
    rp.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    for p in (v, t):
        p.add_argument("--ledger", default="usage.json",
                       help="usage ledger file name (a re-score must not overwrite the first run's ledger)")
    for p in (v, t, w, ex, rp):
        p.add_argument("--quota-share", type=float, default=1.0,
                       help="share of each model's account quota this process may use (0-1]")
    vr = sub.add_parser("val-report")
    vr.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    r = sub.add_parser("report")
    r.add_argument("--preface", default=None, help="markdown under the title (default: <test dir>/preface.md)")
    r.add_argument("--appendix", default=None, help="markdown appended at the end (default: <test dir>/appendix.md)")
    r.add_argument("--out", default=str((repo_root() or Path.cwd()) / "eval" / "reports"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("strands").setLevel(logging.WARNING)
    return {"val": cmd_val, "decide": cmd_decide, "test": cmd_test, "report": cmd_report,
            "val-report": cmd_val_report, "repair": cmd_repair,
            "extra": cmd_extra, "warm": cmd_warm}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
