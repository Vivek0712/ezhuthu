"""Evaluation harness.

    python -m ezhuthu.eval.run --split test --limit 300 --router routed [--subset hard] [--no-ontology]

Routers: ``routed`` (Sonnet 4.6 -> Opus 4.6 per config/models.yaml), ``sonnet``, ``opus``, ``none``
(retrieval + n-gram + ontology candidates ranked by the decider; no LLM), and the baselines
``baseline-copy``, ``baseline-ngram``, ``baseline-zeroshot``. LLM routers need ``EZHUTHU_LIVE=1``;
responses are cached under ``.cache/llm/``. Reports go to ``eval/reports/<date>-<name>.{json,md}``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..agent.baselines import copy_best_parallel, ngram_fill, zero_shot
from ..agent.config import live_enabled, repo_root
from ..agent.data import BenchmarkItem, data_source, load_items
from ..agent.decider import Decider, HttpDecider, NoDecider
from ..agent.llm import BedrockLLM, LLMClient
from ..agent.restorer import Restorer
from .metrics import Prediction, by_subset, summarize

log = logging.getLogger(__name__)
LLM_ROUTERS = ("routed", "sonnet", "opus")
ROUTERS = (*LLM_ROUTERS, "none", "baseline-copy", "baseline-ngram", "baseline-zeroshot")
MAX_WORKERS = 5  # Bedrock fan-out cap
FIXTURE_BANNER = ("> **SYNTHETIC FIXTURE DATA.** Smoke test of the harness only. These numbers say nothing about "
                  "restoration quality and must not be cited.")


def predict(item: BenchmarkItem, router: str, restorer: Restorer, llm: LLMClient | None, k: int = 20) -> dict:
    t0 = time.perf_counter()
    meta: dict[str, Any] = {}
    if router in (*LLM_ROUTERS, "none"):
        g = restorer.restore_gap(item.left, item.right, item.gap_chars, router=router, max_candidates=k,
                                 exclude_inscription=item.inscription_id, dynasty=item.dynasty)
        cands = [(c.text, c.confidence) for c in g.candidates]
        abstained = g.decision == "abstain"
        meta = {"decider_model": g.decider_model, "models_used": g.models_used, "escalated": g.escalated,
                "confidence_source": g.candidates[0].confidence_source if g.candidates else None}
    elif router == "baseline-copy":
        cands = copy_best_parallel(restorer, item.left, item.right, item.gap_chars,
                                   exclude_inscription=item.inscription_id, k=k)
        abstained = not cands
    elif router == "baseline-ngram":
        cands = ngram_fill(restorer, item.left, item.right, item.gap_chars, k=k)
        abstained = not cands
    elif router == "baseline-zeroshot":
        if llm is None:
            raise RuntimeError("baseline-zeroshot needs an LLM (EZHUTHU_LIVE=1)")
        cands = zero_shot(llm, item.left, item.right, item.gap_chars, k=k)
        abstained = not cands
    else:
        raise ValueError(f"unknown router {router!r}; choose from {ROUTERS}")
    return {"item": item, "candidates": cands, "abstained": abstained, "meta": meta,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}


def evaluate_items(items: list[BenchmarkItem], *, router: str, restorer: Restorer, llm: LLMClient | None = None,
                   workers: int = 1, k: int = 20) -> dict[str, Any]:
    workers = max(1, min(MAX_WORKERS, workers))
    if workers == 1:
        raw = [predict(it, router, restorer, llm, k) for it in items]
    else:
        with ThreadPoolExecutor(workers) as ex:
            raw = list(ex.map(lambda it: predict(it, router, restorer, llm, k), items))
    preds = [
        Prediction(item_id=r["item"].id, target=r["item"].target, candidates=tuple(t for t, _ in r["candidates"]),
                   confidence=float(r["candidates"][0][1]) if r["candidates"] else 0.0, abstained=r["abstained"],
                   hard=r["item"].hard, age_set=r["item"].age_set)
        for r in raw
    ]
    summary = summarize(preds)
    rows = [
        {"id": p.item_id, "target": p.target, "top1": p.top1, "confidence": round(p.confidence, 4),
         "top1_correct": p.top1_correct, "in_top20": p.in_top(20), "cer": round(p.cer, 4), "abstained": p.abstained,
         "hard": p.hard, "age_set": p.age_set, "candidates": [[t, round(c, 4)] for t, c in r["candidates"][:k]],
         "latency_ms": r["latency_ms"], **r["meta"]}
        for p, r in zip(preds, raw, strict=True)
    ]
    return {**summary, "by_subset": by_subset(preds), "by_router": {router: summary}, "items": rows}


def build_restorer(router: str, *, use_ontology: bool = True, decider: Decider | None = None,
                   llm: LLMClient | None = None) -> Restorer:
    return Restorer(llm=llm, decider=decider or NoDecider(), use_ontology=use_ontology)


def write_report(result: dict[str, Any], meta: dict[str, Any], out_dir: Path, name: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.date.today().isoformat()}-{name}"
    jp, mp = out_dir / f"{stem}.json", out_dir / f"{stem}.md"
    jp.write_text(json.dumps({"meta": meta, **result}, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# Eval: {name}", ""]
    if meta.get("data_is_fixture"):
        lines += [FIXTURE_BANNER, ""]
    lines += [f"- Date: {meta['date']}", f"- Router: `{meta['router']}`",
              f"- Split/subset: {meta['split']}/{meta['subset']}, n = {result['n']}", f"- Data: `{meta['data_dir']}`"
              + (f" (git {meta['data_commit'][:10]})" if meta.get("data_commit") else ""),
              f"- Decider: {meta['decider']}",
              f"- Ontology constraints/hints: {meta['use_ontology']}"
              + (f" ({meta['ontology']})" if meta.get("ontology") else ""),
              f"- Command: `{meta['command']}`", "", "| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |",
              "|---|---|---|---|---|---|---|---|---|"]
    for sub, s in result["by_subset"].items():
        if s["n"]:
            lines.append(f"| {sub} | {s['n']} | {s['top1']} | {s['top20']} | {s['cer']} | {s['cer_clipped']} | "
                         f"{s['cer_median']} | {s['ece']} | {s['abstain_rate']} |")
    lines += ["", "Coverage-accuracy (full):", "", "| threshold | coverage | accuracy |", "|---|---|---|"]
    for c in result["coverage"]:
        lines.append(f"| {c['threshold']} | {c['coverage']} | {c['accuracy']} |")
    if meta.get("usage"):
        u = meta["usage"]
        usage = (f"LLM usage: {u['calls']} live calls, {u['cached_calls']} cached; input tokens "
                 f"{u['input_tokens']}, output tokens {u['output_tokens']}; estimated cost "
                 f"${u['estimated_cost_usd']} ({u['price_basis']}).")
        lines += ["", usage]
    mp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return jp, mp


def git_commit(path: Path) -> str | None:
    """HEAD commit of the git checkout holding ``path`` (data provenance for reports), if any."""
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, check=True)
        return out.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--split", default="test", choices=["train", "val", "test"])
    ap.add_argument("--subset", default="full", choices=["full", "hard", "age"])
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--router", default="none", choices=ROUTERS)
    ap.add_argument("--no-ontology", action="store_true", help="ablation: no ontology candidates or hints")
    ap.add_argument("--decider-url", default=None, help="strands-decider serve URL (default $EZHUTHU_DECIDER_URL)")
    ap.add_argument("--no-decider", action="store_true", help="use fallback confidence instead of the decider")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--name", default=None)
    ap.add_argument("--out", default=None, help="report dir (default eval/reports)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    needs_llm = args.router in (*LLM_ROUTERS, "baseline-zeroshot")
    if needs_llm and not live_enabled():
        print(f"router {args.router} calls Bedrock: set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    llm = BedrockLLM() if needs_llm else None
    decider: Decider = NoDecider() if args.no_decider else HttpDecider(args.decider_url)
    if not args.no_decider and not decider.available():
        log.warning("decider at %s not reachable; confidences use the fallback", getattr(decider, "base_url", "?"))
        decider = NoDecider()
    restorer = build_restorer(args.router, use_ontology=not args.no_ontology, decider=decider, llm=llm)
    src = data_source()
    items = load_items(args.split, subset=args.subset, limit=args.limit, src=src)
    result = evaluate_items(items, router=args.router, restorer=restorer, llm=llm, workers=args.workers)
    health = decider.health() if isinstance(decider, HttpDecider) else None
    name = args.name or f"{args.router}-{args.split}-{args.subset}" + ("-noonto" if args.no_ontology else "") \
        + ("-fixture-smoke" if src.is_fixture else "")
    meta = {
        "date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "router": args.router, "split": args.split,
        "subset": args.subset, "limit": args.limit, "data_dir": str(src.path), "data_is_fixture": src.is_fixture,
        "data_commit": None if src.is_fixture else git_commit(src.path),
        "decider": (health or {}).get("model", "none (fallback confidence)"), "use_ontology": not args.no_ontology,
        "ontology": restorer.ontology.name if not args.no_ontology else None,
        "models": restorer.config.llm, "routing": vars(restorer.config.routing),
        "usage": llm.ledger.to_dict() if llm else None, "command": "python -m ezhuthu.eval.run " + " ".join(
            argv if argv is not None else sys.argv[1:]),
    }
    root = repo_root() or Path.cwd()
    _, mp = write_report(result, meta, Path(args.out) if args.out else root / "eval" / "reports", name)
    print(json.dumps({"n": result["n"], "top1": result["top1"], "top20": result["top20"], "cer": result["cer"],
                      "cer_clipped": result["cer_clipped"],
                      "ece": result["ece"], "report": str(mp)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
