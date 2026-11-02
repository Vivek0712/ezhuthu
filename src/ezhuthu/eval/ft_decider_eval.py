"""Fine-tuned restoration decider: choose a variant on VAL through the restorer, then score it once on TEST.

The fine-tuned deciders (issue #37; ``eval/reports/2026-11-02-ft-decider.md``) are served locally
(``strands-decider serve`` / ``sparrow-decider serve``) and called one request at a time through ``HttpDecider``.

    # 1. VAL: every variant on the deployed-config selection set (280 VAL gaps, routed Sonnet -> Opus, ontology on;
    #    LLM replies from .cache/llm first, new Bedrock calls capped). Decider URLs by label:
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval val --decider ft2b=http://127.0.0.1:8791 \\
        --decider base2b=http://127.0.0.1:8771 --decider sparrow-tiny-ft=http://127.0.0.1:8793 \\
        --decider sparrow-nano-ft=http://127.0.0.1:8794 --max-live-calls 150
    # 2. choose by RULE (0 model calls); Sonnet-only VAL run of the chosen variant (its |llm-sonnet calibration)
    python -m ezhuthu.eval.ft_decider_eval choose
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval val-sonnet --decider ft2b=... --max-live-calls 20
    python -m ezhuthu.eval.ft_decider_eval calibrate [--write-calibration]
    # 3. TEST once, router sonnet on the cached Sonnet replies (refuses any new Bedrock call), committed code only
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval test --decider ft2b=... --decider base2b=...
    # 4. numbers for the report (0 model calls)
    python -m ezhuthu.eval.ft_decider_eval summary

Rows: ``eval/reports/2026-11-02-finetuned-decider/rows/*.jsonl``; references (Sonnet self-confidence, the deployed
configuration, hosted v19) are read from ``2026-11-02-deployed-config/rows`` and never re-run here.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..agent.calibration import Calibration, CalibrationTable
from ..agent.config import RestorerSettings, live_enabled, load_models_config, repo_root
from ..agent.data import BenchmarkItem, data_source, load_items
from ..agent.decider import Decider, HttpDecider, NoDecider
from ..agent.restorer import Restorer
from .deploy_config import (
    NGRAM_OFF,
    DeployRunner,
    TimedDecider,
    decider_timing,
    fill_decisions,
    latency_summary,
    selection_items,
    variant_summary,
)
from .full_eval import cost, load_rows, save_rows, summarize
from .run import code_provenance, evaluate_items, git_commit
from .stats import paired

log = logging.getLogger(__name__)
OUT_DIR = "2026-11-02-finetuned-decider"
DEPLOYED_DIR = "2026-11-02-deployed-config"

# The restorer settings of config/models.yaml as deployed (ngram_prerank on, no 5-gram slot, top_k 3), with the
# decider strategy for LLM-answered gaps; "slot" adds the 5-gram slot (the hosted-v19 VAL run's settings, so that
# comparison differs only in the decider); "plain" turns the 5-gram pre-rank term off (the settings the
# fine-tuning rows were recorded with).
DEPLOYED = {"top_k": 3, "ngram_prerank": True, "ngram_slot": False}
SLOT = {"top_k": 3, "ngram_prerank": True, "ngram_slot": True}
PLAIN = {"top_k": 3, "ngram_prerank": False, "ngram_slot": False}

VARIANTS: dict[str, dict[str, Any]] = {
    # fine-tuned candidates
    "ft2b-choice3": {"decider": "ft2b", "settings": {**DEPLOYED, "strategy_llm": "choice-topk"}, "candidate": True,
                     "label": "fine-tuned 2B, choice-topk:3"},
    "ft2b-noul3": {"decider": "ft2b", "settings": {**DEPLOYED, "strategy_llm": "noul-topk"}, "candidate": True,
                   "label": "fine-tuned 2B, noul-topk:3"},
    "ft2b-choice3-slot": {"decider": "ft2b", "settings": {**SLOT, "strategy_llm": "choice-topk"}, "candidate": True,
                          "label": "fine-tuned 2B, choice-topk:3 + 5-gram slot (hosted-v19 run settings)"},
    "ft2b-choice3-plain": {"decider": "ft2b", "settings": {**PLAIN, "strategy_llm": "choice-topk"},
                           "candidate": True, "label": "fine-tuned 2B, choice-topk:3, no 5-gram pre-rank term"},
    "sparrow-tiny-ft-choice3": {"decider": "sparrow-tiny-ft", "settings": {**DEPLOYED, "strategy_llm": "choice-topk"},
                                "candidate": True, "label": "fine-tuned Sparrow tiny, choice-topk:3"},
    "sparrow-nano-ft-choice3": {"decider": "sparrow-nano-ft", "settings": {**DEPLOYED, "strategy_llm": "choice-topk"},
                                "candidate": True, "label": "fine-tuned Sparrow nano (static), choice-topk:3"},
    # references run here (same settings as the candidates)
    "base2b-choice3": {"decider": "base2b", "settings": {**DEPLOYED, "strategy_llm": "choice-topk"},
                       "label": "base 2B v1-2610, choice-topk:3"},
    "base2b-noul3": {"decider": "base2b", "settings": {**DEPLOYED, "strategy_llm": "noul-topk"},
                     "label": "base 2B v1-2610, noul-topk:3"},
    "selfreport": {"decider": None, "settings": {**DEPLOYED, "strategy_llm": "self-report"},
                   "label": "Sonnet/Opus self-confidence (no decider)"},
    "hybrid-prerank": {"decider": None, "settings": {**DEPLOYED, "strategy_llm": "prerank"},
                       "label": "deployed: pre-rank with the 5-gram term (no decider)"},
}
CANDIDATES = tuple(n for n, v in VARIANTS.items() if v.get("candidate"))
VAL_RUN = (*CANDIDATES, "base2b-choice3", "base2b-noul3")
# References already on the selection set (deployed-config issue): read, never re-run.
DEPLOYED_REFS = {"hybrid-prerank": "val-hybrid-prerank", "selfreport": "val-routed-selfreport",
                 "routed-prerank": "val-routed-prerank", "hosted-v19-slot": "val-routed-hosted-v19",
                 "ngram": "val-ngram"}

# Pre-registered (committed before any of these variants was run through the restorer on VAL).
RULE = ("Chosen fine-tuned variant: among the candidates, the most top-1 matches on the 280-gap VAL selection set "
        "(routed Sonnet -> Opus, ontology on, escalation unchanged at 0.6 on the raw top-1); ties go to fewer "
        "decider calls, then the lower p50 latency per gap. Rows where the decider failed and the restorer fell "
        "back to self-report count as misses. Only the chosen variant is scored on TEST (once). The deployed "
        "default (hybrid-prerank, 100/280) would change only if the chosen variant had strictly more VAL matches "
        "AND could be served by the cloud runtime; the runtime cannot serve a local checkpoint, so this run adds "
        "the model to config/models.yaml disabled in either case and reports whether it was eligible.")


def parse_deciders(specs: list[str]) -> dict[str, str]:
    out = {}
    for s in specs:
        label, _, url = s.partition("=")
        if not url:
            raise SystemExit(f"--decider takes label=url, got {s!r}")
        out[label] = url
    return out


def variant_settings(base: RestorerSettings, name: str) -> RestorerSettings:
    return dataclasses.replace(base, **{**NGRAM_OFF, **VARIANTS[name]["settings"]})


def fallback_rows(rows: list[dict[str, Any]], name: str) -> int:
    """Rows of a decider variant where the decider did not answer (the restorer fell back to self-report)."""
    if VARIANTS.get(name, {}).get("decider") is None:
        return 0
    return sum(1 for r in rows if str(r.get("decider_model") or "").startswith("fallback:") or r.get("error"))


def scored(rows: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    """Rows with decider fallbacks counted as misses (RULE)."""
    if VARIANTS.get(name, {}).get("decider") is None:
        return rows
    return [r if not str(r.get("decider_model") or "").startswith("fallback:") else {**r, "top1_correct": False}
            for r in rows]


def choose(summaries: dict[str, dict[str, Any]], candidates: tuple[str, ...] = CANDIDATES) -> tuple[str, list[str]]:
    """RULE: most top-1 matches, then fewer decider calls, then lower p50 latency. Returns (winner, ranking)."""
    def key(n: str) -> tuple:
        s = summaries[n]
        return (-s["top1_matching"], s["decider_calls"], s["latency"].get("p50_ms", 0.0))
    ranking = sorted((n for n in candidates if n in summaries), key=key)
    if not ranking:
        raise ValueError("no candidate variant has VAL rows")
    return ranking[0], ranking


class Runner(DeployRunner):
    def make_variant(self, name: str, decider: Decider | None, calibration: CalibrationTable | None) -> Restorer:
        r = Restorer(llm=self.llm, decider=decider or NoDecider(), use_ontology=True,
                     settings=variant_settings(self.cfg.restorer, name), config=self.cfg, corpus=self.probe.corpus,
                     calibration=calibration if calibration is not None else CalibrationTable())
        r.__dict__["index"], r.__dict__["ngram"] = self.probe.index, self.probe.ngram
        return r

    def run_named(self, name: str, items: list[BenchmarkItem], *, router: str, out: Path, tag: str,
                  decider: TimedDecider | None, calibration: CalibrationTable | None = None) -> list[dict[str, Any]]:
        t0 = time.perf_counter()
        exhausted0 = self.llm.exhausted if self.llm else 0
        r = self.make_variant(name, decider, calibration)
        rows = []
        for it in items:  # one request at a time (local decider servers are single-stream)
            if decider is not None:
                decider.reset()
            row = evaluate_items([it], router=router, restorer=r, llm=self.llm, workers=1)["items"][0]
            if decider is not None:
                row.update(decider_timing(decider.reset()))
            row["config"] = tag
            rows.append(row)
        health = decider.health() if decider is not None else None
        meta = {"config": tag, "variant": name, "label": VARIANTS[name]["label"], "router": router,
                "settings": VARIANTS[name]["settings"], "seconds": round(time.perf_counter() - t0, 1),
                "budget_refusals": (self.llm.exhausted - exhausted0) if self.llm else 0,
                "data_commit": git_commit(data_source().path), **self.prov,
                "decider": (health or {}).get("model"), "decider_url": getattr(getattr(decider, "inner", None),
                                                                               "base_url", None),
                "decider_calls": decider.calls if decider else 0, "decider_fallback_rows": fallback_rows(rows, name),
                "calibration": str(calibration.path) if calibration is not None and calibration.path else None,
                "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
        save_rows(out / "rows" / f"{tag}.jsonl", rows, meta)
        log.info("%s: n=%d top1=%.4f fallbacks=%d refusals=%d (%.0fs)", tag, len(rows),
                 sum(x["top1_correct"] for x in rows) / max(1, len(rows)), meta["decider_fallback_rows"],
                 meta["budget_refusals"], meta["seconds"])
        return rows


def timed(name: str, urls: dict[str, str]) -> TimedDecider | None:
    label = VARIANTS[name]["decider"]
    if label is None:
        return None
    if label not in urls:
        raise SystemExit(f"{name} needs --decider {label}=<url>")
    d = TimedDecider(HttpDecider(urls[label], timeout=120), 10 ** 6)
    if not d.available():
        raise SystemExit(f"decider {label} at {urls[label]} is not reachable")
    return d


def out_dir(args) -> Path:
    return Path(args.out) / OUT_DIR


def cmd_val(args) -> int:
    if not live_enabled():
        print("routed VAL runs may call Bedrock (escalations): set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    urls = parse_deciders(args.decider)
    out = out_dir(args)
    names = args.only.split(",") if args.only else list(VAL_RUN)
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    items = selection_items(load_items("val"))
    log.info("VAL selection set: %d items", len(items))
    for name in names:
        if (out / "rows" / f"val-{name}.jsonl").exists() and not args.force:
            log.info("skip %s (rows exist)", name)
            continue
        R.run_named(name, items, router="routed", out=out, tag=f"val-{name}", decider=timed(name, urls))
    _ledger(R, out / f"usage-val-{args.ledger_tag}.json", {"max_live_calls": args.max_live_calls, "n": len(items),
                                                           "variants": names})
    return 0


def _ledger(R: Runner, path: Path, extra: dict[str, Any]) -> None:
    usage = R.llm.inner.ledger.to_dict() if R.llm else {}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"usage": usage, "budget_refusals": R.llm.exhausted if R.llm else 0, **extra},
                               indent=1), encoding="utf-8")
    print(json.dumps({"usage": usage, **extra}))


def load_val(out: Path) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    own = {p.stem[len("val-"):]: load_rows(p)[1] for p in sorted((out / "rows").glob("val-*.jsonl"))
           if not p.stem.startswith("val-sonnet-")}
    dep = out.parent / DEPLOYED_DIR / "rows"
    refs = {k: load_rows(dep / f"{v}.jsonl")[1] for k, v in DEPLOYED_REFS.items() if (dep / f"{v}.jsonl").exists()}
    return own, refs


def val_summaries(out: Path) -> dict[str, Any]:
    own, refs = load_val(out)
    cfg = load_models_config()
    ids = {r["id"] for r in refs["ngram"]}
    res: dict[str, Any] = {"n_selection": len(ids), "variants": {}, "references": {}}
    base = {k: refs[k] for k in ("hybrid-prerank", "selfreport")}
    for name, rows in own.items():
        assert {r["id"] for r in rows} == ids, f"{name}: not the selection set"
        rs = scored(rows, name)
        s = variant_summary(rs, {**base, "base2b-choice3": own["base2b-choice3"]} if "base2b-choice3" in own
                            else base, abstain=fill_decisions(rs, None, cfg, top_k=3))
        s["decider_fallback_rows"] = fallback_rows(rows, name)
        s["label"] = VARIANTS[name]["label"]
        res["variants"][name] = s
    for name, rows in refs.items():
        sub = {k: [r for r in v if r["id"] in {x["id"] for x in rows}] for k, v in own.items()}
        res["references"][name] = {
            "n": len(rows), "top1": round(sum(r["top1_correct"] for r in rows) / len(rows), 4),
            "top1_matching": sum(1 for r in rows if r["top1_correct"]), "cost": cost(rows),
            "latency": latency_summary(rows),
            "vs_variants": {k: paired([bool(r["top1_correct"]) for r in scored(v, k)],
                                      [bool({x["id"]: x for x in rows}[r["id"]]["top1_correct"]) for r in v])
                            for k, v in sub.items()}}
    return res


def cmd_choose(args) -> int:
    out = out_dir(args)
    res = val_summaries(out)
    winner, ranking = choose(res["variants"])
    dep = res["references"]["hybrid-prerank"]["top1_matching"]
    w = res["variants"][winner]["top1_matching"]
    dec = {"rule": RULE, "ranking": ranking, "chosen": winner,
           "matches": {n: res["variants"][n]["top1_matching"] for n in ranking},
           "deployed_matching": dep, "eligible_to_replace_deployed": w > dep, "deployed_default_changed": False,
           "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    (out / "decisions.json").write_text(json.dumps(dec, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dec, ensure_ascii=False))
    return 0


def chosen(out: Path) -> str:
    return json.loads((out / "decisions.json").read_text(encoding="utf-8"))["chosen"]


def cmd_val_sonnet(args) -> int:
    """Sonnet-only VAL run of the chosen variant on the selection set: the population of its |llm-sonnet entry
    (as in the deployed-config issue: a routed run has too few gaps Sonnet alone answers)."""
    if not live_enabled():
        print("set EZHUTHU_LIVE=1 (cached replies first; new calls capped)", file=sys.stderr)
        return 2
    out = out_dir(args)
    name = chosen(out)
    R = Runner(live=True, max_live_calls=args.max_live_calls, rpm=args.rpm, quota_share=args.quota_share)
    items = selection_items(load_items("val"))
    R.run_named(name, items, router="sonnet", out=out, tag=f"val-sonnet-{name}",
                decider=timed(name, parse_deciders(args.decider)))
    _ledger(R, out / "usage-val-sonnet.json", {"max_live_calls": args.max_live_calls, "variant": name})
    return 0


def cmd_calibrate(args) -> int:
    """Fit the chosen variant's calibration entries on VAL (|llm-opus from the routed run, |llm-sonnet from the
    Sonnet-only run), with in-sample and 5-fold out-of-fold coverage; optionally write them."""
    out = out_dir(args)
    name = chosen(out)
    cfg = load_models_config()
    rows = load_rows(out / "rows" / f"val-{name}.jsonl")[1]
    sp = out / "rows" / f"val-sonnet-{name}.jsonl"
    son = load_rows(sp)[1] if sp.exists() else None
    fd = fill_decisions(scored(rows, name), scored(son, name) if son else None, cfg, top_k=3)
    now = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    fields = Calibration.__dataclass_fields__
    entries = {k: {**{f: v for f, v in e.items() if f in fields}, "fitted_at": now, "split": "val",
                   "note": f"finetuned-decider issue: VAL selection set (280), {name}, "
                           f"{'Sonnet-only run' if k.endswith('|llm-sonnet') and son else 'routed run'}, "
                           f"ontology on, n={e['n']}"}
               for k, e in fd["entries"].items()}
    res = {"variant": name, "fill_decisions": fd, "entries": entries}
    (out / "calibration.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if args.write_calibration:
        path = Path(args.calibration_file)
        t = CalibrationTable.load(path)
        for k, e in entries.items():
            t.entries[k] = Calibration(**{f: v for f, v in e.items() if f in fields})
        raw = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(t.to_json(raw.get("note", "")), encoding="utf-8")
    print(json.dumps({k: (v["n"], v["positives"], v["threshold"]) for k, v in fd["entries"].items()} |
                     {"in_sample": fd["in_sample"], "cv5": fd["cross_validated"]}, ensure_ascii=False))
    return 0


TEST_RUN = ("{chosen}", "base2b-choice3", "selfreport", "hybrid-prerank")


def cmd_test(args) -> int:
    prov = code_provenance()
    if prov["code_dirty"] and not args.allow_dirty:
        print("refusing to score TEST from uncommitted code (src/ or config/ dirty); commit first", file=sys.stderr)
        return 2
    if not live_enabled():
        print("set EZHUTHU_LIVE=1 (the run reads the reply cache; it refuses every new Bedrock call)",
              file=sys.stderr)
        return 2
    out = out_dir(args)
    name = chosen(out)
    names = [n.format(chosen=name) for n in TEST_RUN]
    urls = parse_deciders(args.decider)
    cfg = load_models_config()
    cal = CalibrationTable.load(cfg.restorer.calibration, min_n=cfg.restorer.calibration_min_n,
                                min_positives=cfg.restorer.calibration_min_positives)
    R = Runner(live=True, max_live_calls=0)  # cached Sonnet replies only: any new call is refused and counted
    items = load_items("test")
    for n in names:
        if (out / "rows" / f"test-sonnet-{n}.jsonl").exists() and not args.force:
            print(f"TEST rows for {n} exist; TEST is scored once", file=sys.stderr)
            continue
        R.run_named(n, items, router="sonnet", out=out, tag=f"test-sonnet-{n}", decider=timed(n, urls),
                    calibration=cal)
    _ledger(R, out / "usage-test.json", {"max_live_calls": 0, "variants": names})
    return 0


def test_summaries(out: Path) -> dict[str, Any]:
    name = chosen(out)
    loaded = {p.stem[len("test-sonnet-"):]: load_rows(p) for p in sorted((out / "rows").glob("test-sonnet-*.jsonl"))}
    rows = {n: rs for n, (_, rs) in loaded.items()}
    res: dict[str, Any] = {"chosen": name, "variants": {}}
    for n, rs in rows.items():
        sc = scored(rs, n)
        s = summarize(sc)
        res["variants"][n] = {
            "label": VARIANTS[n]["label"], **s, "top1_matching": sum(1 for r in sc if r["top1_correct"]),
            "hard": summarize([r for r in sc if r["hard"]]), "decider_fallback_rows": fallback_rows(rs, n),
            "llm_budget_refusals": loaded[n][0].get("budget_refusals"),
            "llm_live_calls": cost(rs)["live_calls_this_run"],
            "calibration_keys": sorted({r.get("calibration") for r in rs if r.get("calibration")}),
            "vs_chosen": None if n == name else {
                sub: paired([bool(r["top1_correct"]) for r in scored(rows[name], name) if sel(r)],
                            [bool({x["id"]: x for x in sc}[r["id"]]["top1_correct"]) for r in rows[name] if sel(r)])
                for sub, sel in (("full", lambda r: True), ("hard", lambda r: r["hard"]))}}
    return res


def cmd_summary(args) -> int:
    out = out_dir(args)
    res = {"val": val_summaries(out)}
    if (out / "decisions.json").exists():
        res["decisions"] = json.loads((out / "decisions.json").read_text(encoding="utf-8"))
    if any((out / "rows").glob("test-sonnet-*.jsonl")):
        res["test"] = test_summaries(out)
    (out / "summary.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {n: (v.get("top1_matching"), v.get("n")) for n, v in res[k].get("variants", {}).items()}
                      for k in ("val", "test") if k in res}, ensure_ascii=False))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    root = repo_root() or Path.cwd()
    v = sub.add_parser("val")
    v.add_argument("--max-live-calls", type=int, default=150)
    v.add_argument("--only", default=None, help="comma-separated variant names (default: all VAL variants)")
    v.add_argument("--ledger-tag", default="routed")
    v.add_argument("--force", action="store_true")
    vs = sub.add_parser("val-sonnet")
    vs.add_argument("--max-live-calls", type=int, default=20)
    c = sub.add_parser("choose")
    cal = sub.add_parser("calibrate")
    cal.add_argument("--write-calibration", action="store_true")
    cal.add_argument("--calibration-file", default=str(Path(__file__).resolve().parents[1] / "agent" /
                                                           "calibration.json"))
    t = sub.add_parser("test")
    t.add_argument("--allow-dirty", action="store_true", help="never for a reported run")
    t.add_argument("--force", action="store_true", help="re-score (only to repair a failed run; say so)")
    s = sub.add_parser("summary")
    for p in (v, vs, c, cal, t, s):
        p.add_argument("--out", default=str(root / "eval" / "reports"))
    for p in (v, vs, t):
        p.add_argument("--decider", action="append", default=[], help="label=url, e.g. ft2b=http://127.0.0.1:8791")
    for p in (v, vs):
        p.add_argument("--rpm", type=float, default=None)
        p.add_argument("--quota-share", type=float, default=1.0)
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return {"val": cmd_val, "val-sonnet": cmd_val_sonnet, "choose": cmd_choose, "calibrate": cmd_calibrate,
            "test": cmd_test, "summary": cmd_summary}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
