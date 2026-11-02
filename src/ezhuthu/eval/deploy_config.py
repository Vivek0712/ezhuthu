"""Deployed restorer configuration: choose it on VAL, calibrate it, score it once on TEST.

The cloud app (AgentCore runtime) runs whatever ``config/models.yaml`` ``restorer:`` says, with the hosted v19
decider when Secrets Manager ``ezhuthu/decider-api-key`` exists and with no decider otherwise. This module compares
the candidate configurations on the same VAL items under a rule fixed before scoring (``RULE`` below, also in the
report), fits the chosen configuration's calibration on VAL, and scores it once on TEST.

    # 1. VAL runs (LLM replies from .cache/llm first; new Bedrock calls capped). Hosted runs need the decider key.
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.deploy_config val --max-live-calls 220
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.deploy_config val-hosted --max-hosted-calls 300
    # 2. Choose by the rule + fit the calibration (0 model calls); --write-calibration updates calibration.json
    python -m ezhuthu.eval.deploy_config choose --write-calibration
    # 3. TEST, the chosen configuration once (committed code only)
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.deploy_config test --max-live-calls 80
    # 4. Report (0 model calls)
    python -m ezhuthu.eval.deploy_config report

Rows: ``eval/reports/2026-11-02-deployed-config/rows/*.jsonl``. The hosted decider key is read by
``HostedDecider`` from Secrets Manager and never printed or logged.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import random
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..agent.calibration import CalibrationTable, fit, variant_key
from ..agent.config import RestorerSettings, live_enabled, load_models_config, repo_root
from ..agent.data import BenchmarkItem, data_source, load_items
from ..agent.decider import Decider, NoDecider, hosted_decider
from ..agent.restorer import Restorer
from .full_eval import (
    Runner,
    baseline_rows,
    by_subset,
    cost,
    llm_short,
    load_rows,
    save_rows,
    seeded_sample,
    summarize,
    vs,
)
from .run import code_provenance, evaluate_items, git_commit
from .stats import paired

log = logging.getLogger(__name__)
SEED = 26
OUT_DIR = "2026-11-02-deployed-config"
REPORT = "2026-11-02-deployed-config"
VAL_N = 280  # LLM selection set: the issue #26 VAL sample (120, seed 26) + 160 more VAL items (seed 26)
HOSTED_N = 120  # hosted-decider set: the issue #26 VAL sample itself (its Sonnet and Opus replies are cached)
NGRAM_THRESHOLD = 0.9103  # 5-gram baseline abstain threshold, fitted on full VAL in issue #26 (val-selection.md)
PROXY_LIMIT_MS = 27_000  # the cloud proxy's per-request limit (contracts/restore-api.md)

# Pre-registered (committed before any of these variants was scored on VAL).
RULE = ("Stage 1: on the same VAL items (the 280-item selection set), the decider-free variant with the most top-1 "
        "matches wins; a tie in matches goes to the lower estimated USD per gap, then the lower p50 latency. "
        "Stage 2: the hosted-v19 variant replaces the stage-1 winner only if it has strictly more top-1 matches on "
        "the 120-item hosted set (a subset of the selection set); otherwise the decider-free winner (cheaper, "
        "faster, no external dependency) stands. No escalation threshold, n-gram threshold or strategy parameter "
        "is re-tuned; the n-gram gate uses the issue #26 full-VAL 5-gram threshold 0.9103.")

# Each variant: restorer settings over config/models.yaml as shipped at the start of this issue (strategy
# self-report for retrieval-only gaps, top_k 3, ngram_k 3), the router, and whether it needs the hosted decider.
VARIANTS: dict[str, dict[str, Any]] = {
    "ngram": {"label": "a. Character 5-gram only (no LLM, no decider)", "router": "baseline-ngram"},
    "hybrid-gate": {"label": "b1. 5-gram gate (fill the 5-gram when its share >= 0.9103), else routed + prerank",
                    "router": "routed", "settings": {"strategy_llm": "prerank", "ngram_gate": NGRAM_THRESHOLD}},
    "hybrid-prerank": {"label": "b2. Routed + prerank with the 5-gram share as a noisy-OR term",
                       "router": "routed", "settings": {"strategy_llm": "prerank", "ngram_prerank": True}},
    "routed-prerank": {"label": "c. Routed + prerank (no decider)", "router": "routed",
                       "settings": {"strategy_llm": "prerank"}},
    "routed-selfreport": {"label": "e. Routed + self-report (the cloud runtime without a decider)",
                          "router": "routed", "settings": {"strategy_llm": "self-report"}},
    "routed-hosted-v19": {"label": "d. Routed + hosted v19 `choice-topk:3` (5-gram prerank + 5-gram slot)",
                          "router": "routed", "hosted": True,
                          "settings": {"strategy_llm": "choice-topk", "top_k": 3, "ngram_prerank": True,
                                       "ngram_slot": True}},
}
STAGE1 = ("ngram", "hybrid-gate", "hybrid-prerank", "routed-prerank", "routed-selfreport")
# Sonnet-only runs of the decider-free LLM variants: the source of their |llm-sonnet calibration entries (as in
# issue #26: a routed run has too few gaps that Sonnet alone answers for an n >= 100 fit).
SONNET_ONLY = ("hybrid-prerank", "routed-prerank", "routed-selfreport")


def selection_items(split_items: list[BenchmarkItem], n: int = VAL_N) -> list[BenchmarkItem]:
    """The issue #26 seeded 120-item VAL sample plus ``n - 120`` more VAL items (seeded), in benchmark order;
    nested, so the hosted set (the 120) is a subset."""
    base = {it.id for it in seeded_sample(split_items, HOSTED_N, SEED)}
    rest = sorted(it.id for it in split_items if it.id not in base)
    extra = set(random.Random(SEED).sample(rest, max(0, min(len(rest), n - len(base)))))
    return [it for it in split_items if it.id in base or it.id in extra]


def hosted_items(split_items: list[BenchmarkItem]) -> list[BenchmarkItem]:
    return seeded_sample(split_items, HOSTED_N, SEED)


NGRAM_OFF = {"ngram_prerank": False, "ngram_slot": False, "ngram_gate": None}


def variant_settings(base: RestorerSettings, name: str) -> RestorerSettings:
    """``base`` with the 5-gram options off, then the variant's own settings (so a run is the same before and
    after config/models.yaml adopts a variant)."""
    return dataclasses.replace(base, **{**NGRAM_OFF, **VARIANTS[name].get("settings", {})})


# ---------------------------------------------------------------------------------------------- hosted ---------
class TimedDecider:
    """Wraps a decider: per-thread log of call latency (HTTP only) and client-side pacing waits, plus a hard cap on
    calls. Over the cap it raises (the run aborts rather than mixing fallback rows into a hosted variant)."""

    def __init__(self, inner: Decider, max_calls: int):
        self.inner = inner
        self.max_calls = max_calls
        self.calls = 0
        self.refused = 0
        self._lock = threading.Lock()
        self._local = threading.local()
        if hasattr(inner, "_sleep"):
            real = inner._sleep

            def sleep(s: float) -> None:
                self.log().append({"wait_ms": round(s * 1000, 1)})
                real(s)
            inner._sleep = sleep

    def log(self) -> list[dict[str, Any]]:
        if not hasattr(self._local, "log"):
            self._local.log = []
        return self._local.log

    def reset(self) -> list[dict[str, Any]]:
        out, self._local.log = self.log(), []
        return out

    def _call(self, fn, *a, **kw):
        with self._lock:
            if self.calls >= self.max_calls:
                self.refused += 1
                raise RuntimeError(f"hosted decider call cap {self.max_calls} reached")
            self.calls += 1
        t0 = time.perf_counter()
        try:
            return fn(*a, **kw)
        finally:  # pacing waits inside the call are logged by sleep(); decider_timing subtracts them
            self.log().append({"call_ms": round((time.perf_counter() - t0) * 1000, 1)})

    def choice(self, *a, **kw):
        return self._call(self.inner.choice, *a, **kw)

    def noul(self, *a, **kw):
        return self._call(self.inner.noul, *a, **kw)

    def available(self) -> bool:
        return self.inner.available()

    def health(self):
        return self.inner.health() if hasattr(self.inner, "health") else None


def decider_timing(log_: list[dict[str, Any]]) -> dict[str, Any]:
    """Decider calls of one gap: count, HTTP latency (call time minus the pacing waits inside it), pacing waits."""
    waits = [x["wait_ms"] for x in log_ if "wait_ms" in x]
    calls = [x["call_ms"] for x in log_ if "call_ms" in x]
    wait_total = sum(waits)
    return {"decider_calls": len(calls), "decider_wait_ms": round(wait_total, 1),
            "decider_http_ms": round(max(0.0, sum(calls) - wait_total), 1)}


# ---------------------------------------------------------------------------------------------- running --------
class DeployRunner(Runner):
    def make(self, name: str, *, decider: Decider | None = None, calibration: CalibrationTable | None = None,
             sonnet_only: bool = False) -> Restorer:
        settings = variant_settings(self.cfg.restorer, name)
        r = Restorer(llm=self.llm, decider=decider or NoDecider(), use_ontology=True, settings=settings,
                     config=self.cfg, corpus=self.probe.corpus,
                     calibration=calibration if calibration is not None else CalibrationTable())
        r.__dict__["index"], r.__dict__["ngram"] = self.probe.index, self.probe.ngram
        return r

    def run_variant(self, name: str, items: list[BenchmarkItem], *, out: Path, router: str | None = None,
                    workers: int = 4, decider: TimedDecider | None = None,
                    calibration: CalibrationTable | None = None, tag: str | None = None) -> list[dict[str, Any]]:
        spec = VARIANTS[name]
        router = router or spec["router"]
        tag = tag or name
        t0 = time.perf_counter()
        exhausted0 = self.llm.exhausted if self.llm else 0
        if router == "baseline-ngram":
            rows = baseline_rows(self.probe, items, router)
        else:
            r = self.make(name, decider=decider, calibration=calibration)

            def one(it: BenchmarkItem) -> dict[str, Any]:
                if decider is not None:
                    decider.reset()
                row = evaluate_items([it], router=router, restorer=r, llm=self.llm, workers=1)["items"][0]
                if decider is not None:
                    row.update(decider_timing(decider.reset()))
                return row

            if workers <= 1:
                rows = [one(it) for it in items]
            else:
                with ThreadPoolExecutor(workers) as ex:
                    rows = list(ex.map(one, items))
        meta = {"config": tag, "variant": name, "label": spec["label"], "router": router,
                "settings": VARIANTS[name].get("settings", {}),
                "seconds": round(time.perf_counter() - t0, 1),
                "budget_refusals": (self.llm.exhausted - exhausted0) if self.llm else 0,
                "data_commit": git_commit(data_source().path), **self.prov,
                "decider": getattr(getattr(decider, "inner", None), "model", None),
                "decider_calls": decider.calls if decider else 0,
                "calibration": str(calibration.path) if calibration is not None and calibration.path else None,
                "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
        for row in rows:
            row["config"] = tag
        save_rows(out / "rows" / f"{tag}.jsonl", rows, meta)
        log.info("%s: n=%d top1=%.4f (%.0fs)", tag, len(rows),
                 sum(x["top1_correct"] for x in rows) / max(1, len(rows)), meta["seconds"])
        return rows


def _ledger(R: Runner, path: Path, extra: dict[str, Any]) -> None:
    usage = R.llm.inner.ledger.to_dict() if R.llm else {}
    path.write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted if R.llm else 0, **extra},
                               indent=1), encoding="utf-8")
    print(json.dumps({"usage": usage, **extra}))


def cmd_val(args) -> int:
    if not live_enabled():
        print("the VAL LLM runs may call Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    out = Path(args.out) / OUT_DIR
    R = DeployRunner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    allv = load_items("val")
    items = selection_items(allv)
    log.info("VAL selection set: %d items", len(items))
    R.run_variant("ngram", allv, out=out, tag="val-full-ngram")  # full VAL (443), 0 model calls
    R.run_variant("ngram", items, out=out, tag="val-ngram")
    # Sonnet first (cheap, fast quota), then the routed runs (Opus), cached replies first throughout.
    for name in SONNET_ONLY:
        R.run_variant(name, items, out=out, router="sonnet", tag=f"val-sonnet-{name}", workers=args.workers)
    for name in ("routed-selfreport", "routed-prerank", "hybrid-prerank", "hybrid-gate"):
        R.run_variant(name, items, out=out, tag=f"val-{name}", workers=args.workers)
    _ledger(R, out / "usage-val.json", {"max_live_calls": args.max_live_calls, "n": len(items)})
    return 0


def cmd_val_hosted(args) -> int:
    out = Path(args.out) / OUT_DIR
    R = DeployRunner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    hd = TimedDecider(hosted_decider(R.cfg), args.max_hosted_calls)
    if not hd.available():
        print("hosted decider not reachable (key or service); nothing scored", file=sys.stderr)
        return 2
    items = hosted_items(load_items("val"))
    R.run_variant("routed-hosted-v19", items, out=out, tag="val-routed-hosted-v19", decider=hd,
                  workers=args.workers)
    _ledger(R, out / "usage-val-hosted.json", {"hosted_calls": hd.calls, "hosted_refused": hd.refused,
                                                "max_hosted_calls": args.max_hosted_calls, "n": len(items)})
    return 0


# ---------------------------------------------------------------------------------------------- choosing -------
def gap_latency_ms(row: dict[str, Any]) -> float:
    """One gap as the cloud would serve it: local compute + original LLM latencies + decider HTTP latencies (the
    eval's client-side pacing between *different* gaps is excluded; within one gap a second hosted call waits for
    the 6 s pacing interval only if the LLM call between the two took less)."""
    calls = row.get("llm_calls") or []
    llm = sum(c["latency_ms"] for c in calls)
    local = max(0.0, float(row.get("latency_ms") or 0.0) - float(row.get("llm_wall_ms") or 0.0)
                - float(row.get("decider_http_ms") or 0.0) - float(row.get("decider_wait_ms") or 0.0))
    dec = float(row.get("decider_http_ms") or 0.0)
    if (row.get("decider_calls") or 0) >= 2 and calls:
        dec += max(0.0, 6000.0 - calls[-1]["latency_ms"])
    return local + llm + dec


def latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    xs = sorted(gap_latency_ms(r) for r in rows)
    if not xs:
        return {}
    return {"p50_ms": round(statistics.median(xs), 1), "p90_ms": round(xs[min(len(xs) - 1, int(0.9 * len(xs)))], 1),
            "max_ms": round(xs[-1], 1), "over_proxy_limit": sum(1 for x in xs if x > PROXY_LIMIT_MS)}


def fill_decisions(rows: list[dict[str, Any]], sonnet_rows: list[dict[str, Any]] | None, cfg, *, top_k: int,
                   folds: int = 5) -> dict[str, Any]:
    """Fit the calibration entries the runtime would look up for these rows (VAL only) and report coverage and
    selective accuracy in-sample and out-of-fold (5 folds by item). ``|llm-sonnet`` entries are fitted on the
    Sonnet-only rows (when given), the other keys on the rows themselves; keys under the minimum-sample guard stay
    raw (threshold ``routing.abstain_if_confidence_below``), exactly as the restorer would. 5-gram-gated rows fill
    by construction (their share passed the gate)."""
    rs = cfg.restorer
    guard = (rs.calibration_min_n, rs.calibration_min_positives)

    def key(r: dict[str, Any]) -> str | None:
        if r.get("strategy") == "ngram-gate":
            return None
        return variant_key(r["decider_model"], r["strategy"], top_k, llm_short(r, cfg)) if r.get(
            "decider_model") and r.get("strategy") else None

    def fit_groups(train_rows: list[dict[str, Any]], train_sonnet: list[dict[str, Any]] | None):
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in train_rows:
            k = key(r)
            if k and not (train_sonnet is not None and k.endswith("|llm-sonnet")):
                groups.setdefault(k, []).append(r)
        for r in train_sonnet or []:
            k = key(r)
            if k and k.endswith("|llm-sonnet"):
                groups.setdefault(k, []).append(r)
        return {k: fit([float(x.get("raw_confidence") or 0.0) for x in g], [bool(x["top1_correct"]) for x in g])
                for k, g in groups.items()}

    def decide(r: dict[str, Any], entries) -> tuple[bool, float]:
        if r.get("error"):
            return False, 0.0
        if r.get("strategy") == "ngram-gate":
            return True, float(r.get("raw_confidence") or 0.0)
        raw = float(r.get("raw_confidence") or 0.0)
        e = entries.get(key(r))
        if e is None or e.provisional(*guard):
            return raw >= cfg.routing.abstain_if_confidence_below, raw
        c = e.apply(raw)
        return c >= e.threshold, c

    entries = fit_groups(rows, sonnet_rows)
    ins = [decide(r, entries) for r in rows]
    ids = sorted({r["id"] for r in rows})
    random.Random(13).shuffle(ids)
    fold_of = {i: n % folds for n, i in enumerate(ids)}
    oof: dict[str, tuple[bool, float]] = {}
    for f in range(folds):
        tr = [r for r in rows if fold_of[r["id"]] != f]
        trs = [r for r in sonnet_rows if fold_of.get(r["id"], -1) != f] if sonnet_rows is not None else None
        e = fit_groups(tr, trs)
        for r in rows:
            if fold_of[r["id"]] == f:
                oof[r["id"]] = decide(r, e)

    def cov(dec: list[bool]) -> dict[str, Any]:
        k = sum(dec)
        right = sum(1 for d, r in zip(dec, rows, strict=True) if d and r["top1_correct"])
        return {"coverage": round(k / max(1, len(rows)), 4), "filled": k, "filled_matching": right,
                "selective_accuracy": round(right / k, 4) if k else None}

    return {"entries": {k: {**dataclasses.asdict(e), "provisional": e.provisional(*guard)} for k, e in entries.items()},
            "in_sample": cov([d for d, _ in ins]), "cross_validated": cov([oof[r["id"]][0] for r in rows]),
            "keys_used": sorted({k for r in rows if (k := key(r))})}


def variant_summary(rows: list[dict[str, Any]], base: dict[str, list[dict[str, Any]]], **fills: Any) -> dict[str, Any]:
    s = summarize(rows, n_boot=1000)
    c = cost(rows)
    return {"n": len(rows), "top1": s["top1"], "top1_matching": sum(1 for r in rows if r["top1_correct"]),
            "top1_ci": s["top1_ci"], "top20": s["top20"], "cer_clipped": s["cer_clipped"],
            "errors": s["errors"], "cost": c, "latency": latency_summary(rows),
            "llm_skipped": sum(1 for r in rows if r.get("strategy") == "ngram-gate"),
            "decider_calls": sum(int(r.get("decider_calls") or 0) for r in rows),
            "vs": {b: paired([bool(r["top1_correct"]) for r in rows],
                             [bool({x["id"]: x for x in br}[r["id"]]["top1_correct"]) for r in rows])
                   for b, br in base.items()},
            **fills}


def cmd_choose(args) -> int:
    out = Path(args.out) / OUT_DIR
    cfg = load_models_config()
    rows = {p.stem: load_rows(p)[1] for p in sorted((out / "rows").glob("val-*.jsonl"))}
    n280 = {r["id"] for r in rows["val-ngram"]}
    n120 = {r["id"] for r in rows["val-routed-hosted-v19"]} if "val-routed-hosted-v19" in rows else set()
    assert n120 <= n280, "the hosted set must be a subset of the selection set"
    ngram_val = rows["val-ngram"]
    dec: dict[str, Any] = {"rule": RULE, "n_selection": len(n280), "n_hosted": len(n120), "variants": {}}

    def fills_for(name: str, rs: list[dict[str, Any]], *, restrict: set[str] | None = None) -> dict[str, Any]:
        if name == "ngram":
            dec_ = [(not r["abstained"]) and r["confidence"] >= NGRAM_THRESHOLD for r in rs]
            k = sum(dec_)
            right = sum(1 for d, r in zip(dec_, rs, strict=True) if d and r["top1_correct"])
            c = {"coverage": round(k / len(rs), 4), "filled": k, "filled_matching": right,
                 "selective_accuracy": round(right / k, 4) if k else None}
            return {"threshold": NGRAM_THRESHOLD, "in_sample": c, "cross_validated": c,
                    "note": "issue #26 full-VAL 5-gram threshold (not refitted)"}
        son = rows.get(f"val-sonnet-{name}")
        if son is not None and restrict is not None:
            son = [r for r in son if r["id"] in restrict]
        top_k = VARIANTS[name].get("settings", {}).get("top_k", cfg.restorer.top_k)
        return fill_decisions(rs, son, cfg, top_k=top_k)

    # Stage 1: decider-free variants on the selection set
    for name in STAGE1:
        rs = rows[f"val-{name}"]
        assert {r["id"] for r in rs} == n280, f"{name}: not the selection set"
        dec["variants"][name] = variant_summary(rs, {"ngram": ngram_val}, abstain=fills_for(name, rs))

    def stage1_key(n: str) -> tuple:
        v = dec["variants"][n]
        return (-v["top1_matching"], v["cost"]["usd_per_item"], v["latency"].get("p50_ms", 0.0))

    stage1 = min(STAGE1, key=stage1_key)
    dec["stage1"] = {"ranking": sorted(STAGE1, key=stage1_key), "winner": stage1}
    chosen = stage1
    # Stage 2: hosted v19 vs the stage-1 winner on the hosted set
    if n120:
        hosted = rows["val-routed-hosted-v19"]
        sub = {n: [r for r in rows[f"val-{n}"] if r["id"] in n120] for n in STAGE1}
        dec["hosted_set"] = {n: variant_summary(sub[n], {"ngram": sub["ngram"]},
                                                abstain=fills_for(n, sub[n], restrict=n120)) for n in STAGE1}
        dec["variants"]["routed-hosted-v19"] = variant_summary(
            hosted, {"ngram": sub["ngram"], stage1: sub[stage1]}, abstain=fills_for("routed-hosted-v19", hosted))
        h, w = dec["variants"]["routed-hosted-v19"]["top1_matching"], dec["hosted_set"][stage1]["top1_matching"]
        dec["stage2"] = {"hosted_matching": h, "stage1_winner_matching": w, "n": len(n120),
                         "paired": paired([r["top1_correct"] for r in hosted],
                                          [{x["id"]: x for x in sub[stage1]}[r["id"]]["top1_correct"] for r in hosted]),
                         "hosted_wins": h > w}
        if h > w:
            chosen = "routed-hosted-v19"
    dec["chosen"] = chosen
    # Calibration entries for the chosen configuration (VAL only), under the keys the runtime looks up
    if chosen != "ngram":
        crs = rows[f"val-{chosen}"]
        fd = fills_for(chosen, crs)
        now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
        dec["calibration"] = {}
        for k, e in fd["entries"].items():
            src = "Sonnet-only run" if k.endswith("|llm-sonnet") and f"val-sonnet-{chosen}" in rows else "routed run"
            dec["calibration"][k] = {**e, "fitted_at": now, "note": f"deployed-config issue: VAL {src}, "
                                     f"{'selection set (280)' if chosen in STAGE1 else 'hosted set (120)'}, "
                                     f"ontology on, n={e['n']}"}
    (out / "decisions.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.write_calibration and dec.get("calibration"):
        path = Path(args.calibration_file)
        t = CalibrationTable.load(path)
        from ..agent.calibration import Calibration

        fields = Calibration.__dataclass_fields__
        for k, e in dec["calibration"].items():
            if k in t.entries:
                print(f"replacing calibration entry {k}", file=sys.stderr)
            t.entries[k] = Calibration(**{f: v for f, v in e.items() if f in fields})
        raw = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(t.to_json(raw.get("note", "")), encoding="utf-8")
    print(json.dumps({"stage1": dec["stage1"], "stage2": dec.get("stage2"), "chosen": chosen,
                      "calibration": {k: (v["n"], v["positives"], v["threshold"], v["provisional"])
                                      for k, v in dec.get("calibration", {}).items()}}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------------------------- TEST -----------
def cmd_test(args) -> int:
    prov = code_provenance()
    if prov["code_dirty"] and not args.allow_dirty:
        print("refusing to score TEST from uncommitted code (src/ or config/ dirty); commit first", file=sys.stderr)
        return 2
    if not live_enabled():
        print("TEST may call Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    out = Path(args.out) / OUT_DIR
    dec = json.loads((out / "decisions.json").read_text(encoding="utf-8"))
    chosen = dec["chosen"]
    if (out / "rows" / "test-deployed.jsonl").exists() and not args.force:
        print("TEST was already scored for the deployed config; it is scored once", file=sys.stderr)
        return 2
    R = DeployRunner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    items = load_items("test")
    if chosen == "ngram":
        R.run_variant("ngram", items, out=out, tag="test-deployed")
    else:
        shipped = R.cfg.restorer
        if variant_settings(shipped, chosen) != shipped:
            print(f"config/models.yaml restorer settings are not the chosen variant {chosen}; update it first",
                  file=sys.stderr)
            return 2
        cal = CalibrationTable.load(shipped.calibration, min_n=shipped.calibration_min_n,
                                    min_positives=shipped.calibration_min_positives)
        hd = TimedDecider(hosted_decider(R.cfg), args.max_hosted_calls) if VARIANTS[chosen].get("hosted") else None
        R.run_variant(chosen, items, out=out, tag="test-deployed", decider=hd, calibration=cal,
                      workers=args.workers)
    _ledger(R, out / "usage-test.json", {"max_live_calls": args.max_live_calls, "chosen": chosen})
    return 0


# ---------------------------------------------------------------------------------------------- report ---------
GAP_BUCKETS = (("1 letter", 1, 1), ("2-3 letters", 2, 3), ("4+ letters", 4, 10 ** 6))


def gap_length_table(test: list[dict[str, Any]], base: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Top-1 by gap length (Tamil letters) for the deployed rows and the PR #31 rows, on the same TEST items."""
    gl = {it.id: it.gap_chars for it in load_items("test")}
    out: dict[str, Any] = {}
    for name, rows in (("deployed", test), *base.items()):
        out[name] = {}
        for lab, lo, hi in GAP_BUCKETS:
            xs = [r for r in rows if lo <= (gl.get(r["id"]) or 0) <= hi]
            out[name][lab] = {"n": len(xs), "top1": round(sum(r["top1_correct"] for r in xs) / max(1, len(xs)), 4)}
    return out


def build_report(out_dir: Path) -> dict[str, Any]:
    reports = out_dir.parent
    dec = json.loads((out_dir / "decisions.json").read_text(encoding="utf-8"))
    meta, test = load_rows(out_dir / "rows" / "test-deployed.jsonl")
    t31 = reports / "2026-11-02-test-eval" / "rows"
    base = {n: load_rows(t31 / f"{n}.jsonl")[1] for n in ("copy", "ngram", "routed")}
    ngram_meta = json.loads((reports / "2026-11-02-test-eval.json").read_text(encoding="utf-8"))
    cfg = load_models_config()
    chosen = dec["chosen"]
    thr = None
    if chosen == "ngram":
        thr = NGRAM_THRESHOLD
    res = {"chosen": chosen, "label": VARIANTS[chosen]["label"], "meta": meta,
           "by_subset": by_subset(test, threshold=thr), "cost": cost(test), "latency": latency_summary(test),
           "vs": {n: vs(test, b) for n, b in base.items()},
           "llm_skipped": sum(1 for r in test if r.get("strategy") == "ngram-gate"),
           "escalated": sum(1 for r in test if r.get("escalated")),
           "calibration_keys": sorted({r.get("calibration") or "none (raw)" for r in test
                                       if r.get("strategy") != "ngram-gate"}),
           "decider_calls": sum(int(r.get("decider_calls") or 0) for r in test),
           "test31": {n: ngram_meta["configs"][n]["by_subset"]["full"] for n in ("copy", "ngram", "routed")},
           "by_gap_length": gap_length_table(test, base),
           "models": cfg.llm, "decisions": dec}
    return res


def _cell(text: str) -> str:
    """Escape ``|`` for a markdown table cell (calibration keys contain it)."""
    return text.replace("|", "\\|")


def _pv(p: float) -> str:
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"


def _usd(c: dict[str, Any]) -> str:
    return f"{c['usd_per_item']:.5f}"


def _lat(lt: dict[str, Any]) -> str:
    if not lt:
        return "-"
    return f"{lt['p50_ms'] / 1000:.1f} / {lt['p90_ms'] / 1000:.1f} / {lt['max_ms'] / 1000:.1f} ({lt['over_proxy_limit']})"


def _cov(f: dict[str, Any]) -> str:
    sa = "-" if f["selective_accuracy"] is None else f"{f['selective_accuracy']:.4f}"
    return f"{f['coverage']:.4f} / {sa} ({f['filled_matching']}/{f['filled']})"


def _calls(c: dict[str, Any]) -> str:
    bm = c["by_model"]
    return f"{int(bm.get('sonnet', {}).get('calls', 0))} / {int(bm.get('opus', {}).get('calls', 0))}"


def val_table(variants: dict[str, dict[str, Any]], names: list[str], vs_name: str) -> list[str]:
    lines = ["| variant | n | top-1 [95% CI] | matches | top-20 | vs " + vs_name + " (only / only, p) | LLM calls "
             "(Sonnet / Opus) | gaps with no LLM call | decider calls | est. USD per gap | latency p50 / p90 / max s "
             "(gaps over 27 s) | coverage / selective acc., in-sample | same, 5-fold out-of-fold |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        v = variants[n]
        p = v["vs"].get(vs_name)
        pv = "-" if p is None or n == vs_name else f"{p['only_a']} / {p['only_b']}, p={_pv(p['p_mcnemar'])}"
        ci = v["top1_ci"]
        lines.append(f"| {VARIANTS[n]['label']} | {v['n']} | {v['top1']:.4f} [{ci[0]}, {ci[1]}] | {v['top1_matching']} "
                     f"| {v['top20']:.4f} | {pv} | {_calls(v['cost'])} | {v['llm_skipped']} | {v['decider_calls']} "
                     f"| {_usd(v['cost'])} | {_lat(v['latency'])} | {_cov(v['abstain']['in_sample'])} "
                     f"| {_cov(v['abstain']['cross_validated'])} |")
    return lines


def render_md(res: dict[str, Any], preface: str, appendix: str) -> str:
    dec = res["decisions"]
    f = res["by_subset"]["full"]
    L = [preface.rstrip(), "", "## VAL: stage 1 (selection set, same items)", ""]
    L += val_table(dec["variants"], list(STAGE1), "ngram")
    L += ["", (f"Ranking by the rule: {', '.join(dec['stage1']['ranking'])}. Stage-1 winner: "
               f"**{dec['stage1']['winner']}**."), ""]
    if "stage2" in dec:
        s2 = dec["stage2"]
        L += ["## VAL: stage 2 (hosted set, 120 items, same items)", ""]
        hs = {**dec["hosted_set"], "routed-hosted-v19": dec["variants"]["routed-hosted-v19"]}
        L += val_table(hs, [*STAGE1, "routed-hosted-v19"], "ngram")
        p = s2["paired"]
        L += ["", (f"Hosted v19 {s2['hosted_matching']} vs stage-1 winner {s2['stage1_winner_matching']} matches "
                   f"of {s2['n']} (only hosted / only winner: {p['only_a']} / {p['only_b']}, p = "
                   f"{_pv(p['p_mcnemar'])}); hosted wins: {s2['hosted_wins']}."), ""]
    L += [f"**Chosen: {res['label']}** (`{res['chosen']}`).", ""]
    if dec.get("calibration"):
        L += ["### Calibration entries fitted for it (VAL only)", "",
              "| key | n | positives | a | b | abstain threshold | used by the runtime |", "|---|---|---|---|---|---|---|"]
        for k, e in sorted(dec["calibration"].items()):
            L.append(f"| `{_cell(k)}` | {e['n']} | {e['positives']} | {e['a']} | {e['b']} | {e['threshold']} | "
                     f"{'no (provisional)' if e['provisional'] else 'yes'} |")
        L.append("")
    L += ["## TEST: the deployed configuration, scored once (413 gaps)", ""]
    L += ["| configuration | n | top-1 [95% CI] | top-20 | CER clipped | ECE | coverage | selective acc. |",
          "|---|---|---|---|---|---|---|---|"]

    def trow(label: str, s: dict[str, Any]) -> str:
        sa = "-" if s["selective_accuracy"] is None else f"{s['selective_accuracy']:.4f} ({s['filled_matching']}/{s['filled']})"
        return (f"| {label} | {s['n']} | {s['top1']:.4f} [{s['top1_ci'][0]}, {s['top1_ci'][1]}] | {s['top20']:.4f} | "
                f"{s['cer_clipped']:.4f} | {s['ece']:.4f} | {s['coverage']:.4f} | {sa} |")

    L.append(trow(f"**Deployed: {res['label']}**", f))
    for n, lab in (("copy", "Copy baseline (PR #31 row)"), ("ngram", "Character 5-gram baseline (PR #31 row)"),
                   ("routed", "Routed + local 2B decider (PR #31 measured pipeline)")):
        L.append(trow(lab, res["test31"][n]))
    L += ["", "Hard subset and age subset (deployed configuration):", "",
          "| subset | n | top-1 [95% CI] | coverage | selective acc. |", "|---|---|---|---|---|"]
    for sub in ("hard", "age"):
        s = res["by_subset"][sub]
        sa = "-" if s["selective_accuracy"] is None else f"{s['selective_accuracy']:.4f}"
        L.append(f"| {sub} | {s['n']} | {s['top1']:.4f} [{s['top1_ci'][0]}, {s['top1_ci'][1]}] | {s['coverage']:.4f} "
                 f"| {sa} |")
    L += ["", "Paired exact McNemar on top-1 (same 413 gaps; only deployed right / only the other right):", "",
          "| vs | n | only deployed | only other | p |", "|---|---|---|---|---|"]
    for n, lab in (("copy", "copy baseline"), ("ngram", "character 5-gram"), ("routed", "PR #31 routed row")):
        v = res["vs"][n]["full"]
        L.append(f"| {lab} | {v['n']} | {v['only_a']} | {v['only_b']} | {_pv(v['p_mcnemar'])} |")
    gl = res["by_gap_length"]
    L += ["", "Top-1 by gap length (Tamil letters), same TEST gaps:", "",
          "| configuration | " + " | ".join(f"{lab} (n={gl['deployed'][lab]['n']})" for lab, _, _ in GAP_BUCKETS) + " |",
          "|---|---|---|---|"]
    for n, lab in (("deployed", "Deployed"), ("copy", "Copy baseline"), ("ngram", "Character 5-gram"),
                   ("routed", "PR #31 routed + local 2B")):
        L.append(f"| {lab} | " + " | ".join(f"{gl[n][b]['top1']:.4f}" for b, _, _ in GAP_BUCKETS) + " |")
    c, lt = res["cost"], res["latency"]
    L += ["", "| cost and latency (deployed, TEST) | value |", "|---|---|",
          f"| LLM calls (Sonnet / Opus) | {_calls(c)} |", f"| gaps that used Opus | {c['opus_items']} |",
          f"| gaps filled by the 5-gram gate with no LLM call | {res['llm_skipped']} |",
          f"| hosted decider calls | {res['decider_calls']} |",
          f"| est. USD (per gap) | {c['usd']} ({_usd(c)}) |",
          f"| latency per gap p50 / p90 / max s (gaps over 27 s) | {_lat(lt)} |",
          f"| calibration keys applied | {', '.join('`' + _cell(k) + '`' for k in res['calibration_keys'])} |", ""]
    L.append(appendix.rstrip())
    return "\n".join(L) + "\n"


def cmd_report(args) -> int:
    out = Path(args.out) / OUT_DIR
    res = build_report(out)
    (Path(args.out) / f"{REPORT}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    pre = (out / "preface.md").read_text(encoding="utf-8") if (out / "preface.md").exists() else f"# {REPORT}\n"
    app = (out / "appendix.md").read_text(encoding="utf-8") if (out / "appendix.md").exists() else ""
    (Path(args.out) / f"{REPORT}.md").write_text(render_md(res, pre, app), encoding="utf-8")
    print(json.dumps({k: res["by_subset"]["full"][k] for k in ("n", "top1", "top1_ci", "coverage",
                                                               "selective_accuracy", "ece")}))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    root = repo_root() or Path.cwd()
    v = sub.add_parser("val")
    v.add_argument("--max-live-calls", type=int, default=220)
    vh = sub.add_parser("val-hosted")
    vh.add_argument("--max-live-calls", type=int, default=0)
    vh.add_argument("--max-hosted-calls", type=int, default=300)
    c = sub.add_parser("choose")
    c.add_argument("--write-calibration", action="store_true")
    c.add_argument("--calibration-file", default=str(Path(__file__).resolve().parents[1] / "agent" /
                                                         "calibration.json"))
    t = sub.add_parser("test")
    t.add_argument("--max-live-calls", type=int, default=80)
    t.add_argument("--max-hosted-calls", type=int, default=300)
    t.add_argument("--allow-dirty", action="store_true", help="never for a reported run")
    t.add_argument("--force", action="store_true", help="re-score (only to repair a failed run; say so in the report)")
    rp = sub.add_parser("report")
    for p in (v, vh, c, t, rp):
        p.add_argument("--out", default=str(root / "eval" / "reports"))
    for p in (v, vh, t):
        p.add_argument("--rpm", type=float, default=None)
        p.add_argument("--quota-share", type=float, default=1.0)
        p.add_argument("--workers", type=int, default=4)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return {"val": cmd_val, "val-hosted": cmd_val_hosted, "choose": cmd_choose, "test": cmd_test,
            "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
