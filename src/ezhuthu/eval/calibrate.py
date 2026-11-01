"""Fit per-decider calibration on the VAL split and compare decider variants (issue #22).

    python -m ezhuthu.eval.calibrate --split val --router none --no-ontology \\
        --variants choice-all,choice-topk:3,choice-topk:5,noul-topk:3,prerank,fallback --name val-calibration

Every variant runs the same restorer on the same items (retrieval and n-gram are deterministic, LLM replies come
from the ``.cache/llm`` cache after the first variant, so variants after the first make no Bedrock calls; the
``--max-live-calls`` budget is a hard cap). Per variant it records the raw top-1 confidence and whether the top-1
matches the expert, fits Platt scaling + an abstain threshold (``ezhuthu.agent.calibration``), and reports
in-sample and 5-fold cross-validated numbers, plus a paired comparison with the copy baseline on the same items.

Only ``--split val`` is accepted: the test split is never used to fit anything.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from ..agent.baselines import copy_best_parallel
from ..agent.calibration import CalibrationTable, cross_validated, fit, variant_key
from ..agent.config import PACKAGE_DIR, live_enabled, load_models_config, repo_root
from ..agent.data import data_source, load_items
from ..agent.decider import Decider, HttpDecider, NoDecider
from ..agent.llm import BedrockLLM, BudgetedLLM
from ..agent.restorer import Restorer
from .metrics import canon, coverage_curve, ece
from .run import git_commit

log = logging.getLogger(__name__)


def parse_variants(spec: str) -> list[tuple[str, str, int]]:
    """``choice-topk:3`` -> (label, strategy, k). ``fallback`` = no decider (LLM self-report / retrieval)."""
    out = []
    for v in [x.strip() for x in spec.split(",") if x.strip()]:
        strat, _, k = v.partition(":")
        out.append((v, strat, int(k) if k else 5))
    return out


def run_variant(items, *, restorer: Restorer, router: str) -> list[dict[str, Any]]:
    rows = []
    for it in items:
        t0 = time.perf_counter()
        try:
            g = restorer.restore_gap(it.left, it.right, it.gap_chars, router=router, max_candidates=20,
                                     exclude_inscription=it.inscription_id, dynasty=it.dynasty)
        except Exception as exc:  # noqa: BLE001 - one bad item must not kill the run
            rows.append({"id": it.id, "error": f"{type(exc).__name__}: {str(exc)[:160]}", "raw": 0.0,
                         "correct": False, "oracle": False, "hard": it.hard})
            continue
        top = g.candidates[0] if g.candidates else None
        rows.append({
            "id": it.id, "target": it.target, "hard": it.hard, "top1": top.text if top else None,
            "raw": float(top.raw_confidence if top and top.raw_confidence is not None else 0.0),
            "correct": bool(top and canon(top.text) == canon(it.target)),
            "oracle": any(canon(c.text) == canon(it.target) for c in g.candidates),
            "decider_model": g.decider_model, "llm": any(m in g.models_used for m in restorer.config.llm.values()),
            "llm_truncated": g.llm_truncated, "llm_retries": g.llm_retries,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        })
    return rows


def summarize_variant(rows: list[dict[str, Any]], key: str, fitted) -> dict[str, Any]:
    raw = [r["raw"] for r in rows]
    ok = [r["correct"] for r in rows]
    n = len(rows)
    cal = [fitted.apply(c) for c in raw]
    fill_in = [c >= fitted.threshold for c in cal]
    cv_cal, cv_fill = cross_validated(raw, ok)

    def sel(fill):
        k = sum(fill)
        return {"coverage": round(k / n, 4) if n else None,
                "accuracy": round(sum(o for o, f in zip(ok, fill, strict=True) if f) / k, 4) if k else None,
                "net_right_minus_wrong": sum((1 if o else -1) for o, f in zip(ok, fill, strict=True) if f)}

    lat = sorted(r.get("latency_ms", 0.0) for r in rows if "latency_ms" in r)
    return {
        "key": key, "n": n, "errors": sum(1 for r in rows if r.get("error")),
        "top1": round(sum(ok) / n, 4) if n else None,
        "oracle": round(sum(r["oracle"] for r in rows) / n, 4) if n else None,
        "raw_mean_top1_conf": round(sum(raw) / n, 4) if n else None,
        "raw_max_top1_conf": round(max(raw), 4) if raw else None,
        "ece_raw": round(ece(raw, ok), 4), "ece_calibrated_in_sample": round(ece(cal, ok), 4),
        "ece_calibrated_cv5": round(ece(cv_cal, ok), 4),
        "at_raw_0.5": sel([c >= 0.5 for c in raw]), "at_fitted_in_sample": sel(fill_in),
        "at_fitted_cv5": sel(cv_fill), "coverage_raw": coverage_curve(raw, ok),
        "calibration": {"a": fitted.a, "b": fitted.b, "threshold": fitted.threshold},
        "llm_truncated": sum(int(r.get("llm_truncated") or 0) for r in rows),
        "llm_retries": sum(int(r.get("llm_retries") or 0) for r in rows),
        "latency_ms_p50": lat[len(lat) // 2] if lat else None,
    }


def paired_vs_copy(rows: list[dict[str, Any]], copy_ok: dict[str, bool]) -> dict[str, int]:
    both = only_v = only_c = 0
    for r in rows:
        v, c = r["correct"], copy_ok.get(r["id"], False)
        both += v and c
        only_v += v and not c
        only_c += c and not v
    return {"both": both, "only_variant": only_v, "only_copy": only_c}


def write_report(out_dir: Path, name: str, meta: dict[str, Any], results: dict[str, Any]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.date.today().isoformat()}-{name}"
    (out_dir / f"{stem}.json").write_text(json.dumps({"meta": meta, "variants": results}, ensure_ascii=False,
                                                     indent=1), encoding="utf-8")
    L = [f"# Dev-set note: restorer decider variants and calibration ({meta['split']} split)", "",
         ("> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are "
         "optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite "
         "as restoration quality."), "",
         f"- Date: {meta['date']}", f"- Items: {meta['n']} ({meta['split']}/{meta['subset']}, limit {meta['limit']})",
         (f"- Router: `{meta['router']}`; ontology: {'on' if meta['use_ontology'] else 'off'}; "
         f"decider: {meta['decider']}"),
         f"- Data: `{meta['data_dir']}`" + (f" ({meta['data_commit']})" if meta.get("data_commit") else ""),
         f"- Command: `{meta['command']}`"]
    if meta.get("usage"):
        u = meta["usage"]
        L.append(f"- Bedrock: {u['calls']} live calls, {u['cached_calls']} cached, estimated ${u['estimated_cost_usd']}"
                 f" (budget {meta.get('max_live_calls')}, exhausted on {meta.get('budget_exhausted', 0)} requests)")
    L += ["", f"Copy baseline on the same items: top-1 {meta['copy_top1']}.", "",
          ("| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | "
          "ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | "
          "trunc / retries | p50 ms |"),
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def fmt(x):
        return "-" if x is None else x

    for label, r in results.items():
        s = r["summary"]
        L.append(f"| {label} | {s['top1']} | {s['oracle']} | {r['vs_copy']['only_variant']} / "
                 f"{r['vs_copy']['only_copy']} | {s['raw_mean_top1_conf']} / {s['raw_max_top1_conf']} | "
                 f"{s['ece_raw']} | {s['ece_calibrated_cv5']} | {s['at_raw_0.5']['coverage']} / "
                 f"{fmt(s['at_raw_0.5']['accuracy'])} | {s['at_fitted_cv5']['coverage']} / "
                 f"{fmt(s['at_fitted_cv5']['accuracy'])} | {s['calibration']['threshold']} | "
                 f"{s['llm_truncated']} / {s['llm_retries']} | {s['latency_ms_p50']} |")
    L += ["", "Variant keys written to the calibration file:", ""]
    L += [f"- `{r['summary']['key']}`: a={r['summary']['calibration']['a']}, b={r['summary']['calibration']['b']}, "
          f"threshold={r['summary']['calibration']['threshold']} (n={r['summary']['n']})" for r in results.values()]
    if meta.get("notes"):
        L += ["", "## Notes", ""] + [f"- {n}" for n in meta["notes"]]
    mp = out_dir / f"{stem}.md"
    mp.write_text("\n".join(L) + "\n", encoding="utf-8")
    return mp


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="val")
    ap.add_argument("--subset", default="full", choices=["full", "hard", "age"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--router", default="none", choices=["none", "sonnet"])
    ap.add_argument("--variants", default="choice-all,choice-topk:3,choice-topk:5,noul-topk:3,prerank,fallback")
    ap.add_argument("--no-ontology", action="store_true")
    ap.add_argument("--decider-url", default=None)
    ap.add_argument("--max-live-calls", type=int, default=40)
    ap.add_argument("--rpm", type=float, default=20.0)
    ap.add_argument("--calibration-out", default=str(PACKAGE_DIR / "calibration.json"))
    ap.add_argument("--no-write-calibration", action="store_true")
    ap.add_argument("--name", default="val-calibration")
    ap.add_argument("--out", default=None)
    ap.add_argument("--note", action="append", default=[])
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if args.split != "val":
        print("calibration is fitted on the VAL split only (never test/train)", file=sys.stderr)
        return 2
    if args.router == "sonnet" and not live_enabled():
        print("router sonnet calls Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2

    cfg = load_models_config()
    llm = BudgetedLLM(BedrockLLM(rpm=args.rpm), args.max_live_calls) if args.router == "sonnet" else None
    http = HttpDecider(args.decider_url)
    if not http.available():
        print(f"decider at {http.base_url} not reachable", file=sys.stderr)
        return 2
    src = data_source()
    items = load_items(args.split, subset=args.subset, limit=args.limit, src=src)
    probe = Restorer(decider=NoDecider(), use_ontology=not args.no_ontology, calibration=CalibrationTable())
    copy_ok = {}
    for it in items:
        c = copy_best_parallel(probe, it.left, it.right, it.gap_chars, exclude_inscription=it.inscription_id)
        copy_ok[it.id] = bool(c) and canon(c[0][0]) == canon(it.target)

    table = CalibrationTable.load(args.calibration_out)
    results: dict[str, Any] = {}
    decider_model = (http.health() or {}).get("model", "strands-decider")
    for label, strat, k in parse_variants(args.variants):
        dec: Decider = NoDecider() if strat == "fallback" else http
        settings = cfg.restorer.with_(strategy="choice-topk" if strat == "fallback" else strat, top_k=k)
        r = Restorer(llm=llm, decider=dec, use_ontology=not args.no_ontology, settings=settings,
                     calibration=CalibrationTable(), corpus=probe.corpus)
        r.__dict__["index"], r.__dict__["ngram"] = probe.index, probe.ngram  # share the built indexes
        t0 = time.perf_counter()
        rows = run_variant(items, restorer=r, router=args.router)
        used_llm = any(row.get("llm") for row in rows)
        model = next((row["decider_model"] for row in rows if row.get("decider_model")), decider_model)
        key = variant_key(model, settings.strategy, k, used_llm)
        fitted = fit([row["raw"] for row in rows], [row["correct"] for row in rows], split="val",
                     fitted_at=dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                     note=f"{args.router} router, ontology {'off' if args.no_ontology else 'on'}, n={len(rows)}")
        summ = summarize_variant(rows, key, fitted)
        results[label] = {"summary": summ, "vs_copy": paired_vs_copy(rows, copy_ok), "rows": rows,
                          "seconds": round(time.perf_counter() - t0, 1)}
        table.entries[key] = fitted
        log.info("%s: top1 %s raw-mean %s key %s (%.0fs)", label, summ["top1"], summ["raw_mean_top1_conf"], key,
                 results[label]["seconds"])

    if not args.no_write_calibration:
        Path(args.calibration_out).write_text(table.to_json(), encoding="utf-8")
    meta = {
        "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "split": args.split, "subset": args.subset,
        "limit": args.limit, "n": len(items), "router": args.router, "use_ontology": not args.no_ontology,
        "decider": decider_model, "data_dir": str(src.path), "data_commit": git_commit(src.path),
        "copy_top1": round(sum(copy_ok.values()) / max(1, len(copy_ok)), 4),
        "usage": llm.ledger.to_dict() if llm else None, "max_live_calls": args.max_live_calls,
        "budget_exhausted": llm.exhausted if llm else 0, "notes": args.note,
        "calibration_file": None if args.no_write_calibration else args.calibration_out,
        "command": "python -m ezhuthu.eval.calibrate " + " ".join(argv if argv is not None else sys.argv[1:]),
    }
    root = repo_root() or Path.cwd()
    mp = write_report(Path(args.out) if args.out else root / "eval" / "reports", args.name, meta, results)
    print(json.dumps({label: {k: r["summary"][k] for k in ("top1", "raw_mean_top1_conf", "key")}
                      for label, r in results.items()} | {"report": str(mp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
