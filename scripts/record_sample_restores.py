"""Record what the live restorer returns for every try-it sample (eval/reports/2026-11-02-samples.md, rule 4).

Runs each gallery sample's ISO text once through EzhuthuService.restore (the deployed configuration in
config/models.yaml) and writes app/web/src/samples/recorded-restores.json, which the mock API replays and
scripts/build_samples.py summarises into each sample's `recorded` field. Live Bedrock calls are capped
(--max-live, default 40, cached replies do not count); the run stops rather than fall back to retrieval-only
candidates when the cap is reached. An existing recording is never overwritten without --force: the samples
are recorded once and reported as they came out.

Run: EZHUTHU_LIVE=1 AWS_PROFILE=heisenberg PYTHONPATH=src .venv/bin/python scripts/record_sample_restores.py
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _build_module():
    spec = importlib.util.spec_from_file_location("build_samples", REPO / "scripts" / "build_samples.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--max-live", type=int, default=40, help="cap on live (uncached) Bedrock calls")
    ap.add_argument("--force", action="store_true", help="overwrite an existing recording")
    args = ap.parse_args(argv)

    from ezhuthu.agent.config import live_enabled
    from ezhuthu.agent.llm import BedrockLLM, BudgetedLLM
    from ezhuthu.api.service import EzhuthuService

    b = _build_module()
    if b.RECORDED.exists() and not args.force:
        print(f"{b.RECORDED.relative_to(REPO)} exists; the samples are recorded once (use --force to redo)",
              file=sys.stderr)
        return 1
    if not live_enabled():
        print("EZHUTHU_LIVE=1 is required: the recording must be the live restorer", file=sys.stderr)
        return 1
    samples, _ = b.build(recorded={"samples": {}})
    inner = BedrockLLM()
    llm = BudgetedLLM(inner, args.max_live)
    svc = EzhuthuService(llm=llm, admin_token=None)
    cfg = svc.restorer.config
    out: dict = {"meta": {
        "date": dt.date.today().isoformat(),
        "what": "EzhuthuService.restore(text_iso, script='iso15919', max_candidates=5, allow_escalation=True), "
                "once per sample, deployed configuration (config/models.yaml)",
        "models": {k: cfg.llm[k] for k in ("default", "escalate")},
        "restorer": {"strategy": svc.restorer.settings.strategy, "strategy_llm": svc.restorer.settings.strategy_llm,
                     "ngram_prerank": svc.restorer.settings.ngram_prerank},
    }, "samples": {}}
    for s in samples:
        t0 = time.perf_counter()
        resp = svc.restore(s["text_iso"], script="iso15919", max_candidates=5, allow_escalation=True)
        if llm.exhausted:
            print(f"live-call cap of {args.max_live} reached at {s['id']}; nothing written", file=sys.stderr)
            return 2
        resp["trace_id"] = f"recorded-{s['id']}"
        out["samples"][s["id"]] = {"group": s["group"], "text_iso": s["text_iso"],
                                   "wall_s": round(time.perf_counter() - t0, 1), "response": resp}
        g = [(x["decision"], x["candidates"][0]["text"] if x["candidates"] else None,
              x["candidates"][0]["confidence"] if x["candidates"] else None) for x in resp["gaps"]]
        print(s["id"], g, flush=True)
    out["meta"]["bedrock"] = inner.ledger.to_dict()
    b.RECORDED.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {b.RECORDED.relative_to(REPO)}; Bedrock: {inner.ledger.to_dict()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
