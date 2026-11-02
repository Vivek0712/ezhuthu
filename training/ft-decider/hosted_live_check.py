"""Live check of the shipped restorer with the HOSTED fine-tuned decider, on VAL only (never TEST).

    EZHUTHU_LIVE=1 EZHUTHU_DECIDER_BACKEND=hosted python training/ft-decider/hosted_live_check.py --limit 20

Each VAL gap is restored as a one-gap ``POST /api/restore`` would be: the shipped ``config/models.yaml`` restorer
settings (routed Sonnet -> Opus, then ``choice-topk`` over the pre-rank's top 3 + none), the request budget's
deadline, and ``restorer_decider()`` (decider-cloud, model ``decider.cloud.restorer_model``). Bedrock replies are not
cached (``--cache-dir`` to reuse a cache), so the latencies are live. The API key is read by the client from Secrets
Manager and never printed.

It reports where each gap's ranking came from (the hosted fine-tune, or the pre-rank fallback and why), the time per
gap and per decider call, and, for information only (a handful of VAL gaps), how many top fills match the editors'
restoration. Writes ``<out>.jsonl`` (per gap) and ``<out>.json`` (summary).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path
from typing import Any

from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.data import load_items
from ezhuthu.agent.decider import decider_backend, restorer_decider
from ezhuthu.agent.llm import BedrockLLM, BudgetedLLM
from ezhuthu.agent.restorer import Restorer
from ezhuthu.eval.metrics import canon

MAX_GAPS = 20


class TimedDecider:
    """Records the wall time of each decider call (client side, including the network and the server queue)."""

    def __init__(self, inner: Any):
        self.inner = inner
        self.calls: list[dict[str, Any]] = []

    def __getattr__(self, name: str) -> Any:
        return getattr(self.inner, name)

    def _timed(self, kind: str, fn: Any, *a: Any, **k: Any) -> Any:
        t = time.perf_counter()
        rec: dict[str, Any] = {"kind": kind, "timeout_s": k.get("timeout")}
        try:
            out = fn(*a, **k)
            rec.update(ok=True, model=out.model, server_ms=out.latency_ms)
            return out
        except Exception as e:
            rec.update(ok=False, error=type(e).__name__, message=str(e)[:160])
            raise
        finally:
            rec["wall_ms"] = round((time.perf_counter() - t) * 1000, 1)
            self.calls.append(rec)

    def choice(self, *a: Any, **k: Any) -> Any:
        return self._timed("choice", self.inner.choice, *a, **k)

    def noul(self, *a: Any, **k: Any) -> Any:
        return self._timed("noul", self.inner.noul, *a, **k)


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * (len(xs) - 1) + 0.5))], 1)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=20, help=f"VAL gaps (at most {MAX_GAPS})")
    ap.add_argument("--max-live-calls", type=int, default=60, help="Bedrock call cap for the whole run")
    ap.add_argument("--cache-dir", default=None, help="Bedrock reply cache (default: none, live latencies)")
    ap.add_argument("--out", default="eval/reports/2026-11-03-hosted-ft-live/val-live-check")
    args = ap.parse_args(argv)
    if not 0 < args.limit <= MAX_GAPS:
        raise SystemExit(f"--limit must be 1..{MAX_GAPS}")
    if decider_backend() != "hosted":
        raise SystemExit("set EZHUTHU_DECIDER_BACKEND=hosted")
    cfg = load_models_config()
    dec = TimedDecider(restorer_decider("hosted"))
    if not dec.available():
        raise SystemExit(f"hosted decider {dec.inner.model} is not listed as ready")
    llm = BudgetedLLM(BedrockLLM(cfg, cache_dir=args.cache_dir), args.max_live_calls)
    r = Restorer(llm=llm, decider=dec, config=cfg)
    st = r.settings
    r.warm()
    items = [it for it in load_items("val") if it.gap_chars][: args.limit]  # VAL only, the split's first gaps

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    with out.with_suffix(".jsonl").open("w", encoding="utf-8") as fh:
        for it in items:
            before = len(dec.calls)
            t0 = r.clock()
            g = r.restore_gap(it.left, it.right, it.gap_chars, router="routed", exclude_inscription=it.inscription_id,
                              dynasty=it.dynasty, deadline=t0 + st.request_budget_s if st.request_budget_s else None)
            wall = (r.clock() - t0) * 1000
            best = g.best
            row = {"id": it.id, "gap_chars": it.gap_chars, "wall_ms": round(wall, 1), "decision": g.decision,
                   "strategy": g.strategy, "decider_model": g.decider_model, "decider_fallback": g.decider_fallback,
                   "calibration": g.calibration, "escalated": g.escalated, "llm_calls": len(g.llm_calls),
                   "llm_wall_ms": g.llm_wall_ms, "llm_skipped": g.llm_skipped,
                   "escalation_skipped": g.escalation_skipped, "decider_calls": dec.calls[before:],
                   "top1_matches_editors": bool(best and canon(best.text) == canon(it.target)),
                   "top1_confidence": round(best.confidence, 4) if best else None}
            rows.append(row)
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            print(f"{it.id}: {row['wall_ms'] / 1000:.1f}s {g.decider_model} {g.strategy}"
                  f"{' fallback=' + g.decider_fallback if g.decider_fallback else ''} {g.decision}", flush=True)

    calls = [c for row in rows for c in row["decider_calls"]]
    ok = [c for c in calls if c["ok"]]
    walls = [row["wall_ms"] for row in rows]
    summary = {
        "split": "val", "gaps": len(rows), "decider_model": dec.inner.model, "url": dec.inner.base_url,
        "settings": {k: getattr(st, k) for k in ("strategy", "strategy_llm", "top_k", "ngram_prerank",
                                                 "decider_fallback", "decider_timeout_s", "decider_min_remaining_s",
                                                 "request_budget_s")},
        "ranked_by_hosted_fine_tune": sum(row["decider_model"] == dec.inner.model for row in rows),
        "fallbacks": {k: sum(row["decider_fallback"] == k for row in rows) for k in ("unavailable", "time_budget")},
        "other_rankings": sorted({row["decider_model"] for row in rows} - {dec.inner.model}),
        "gap_wall_ms": {"p50": pct(walls, 0.5), "p90": pct(walls, 0.9), "max": max(walls) if walls else None},
        "over_budget": sum(w > (st.request_budget_s or 1e9) * 1000 for w in walls),
        "decider_calls": len(calls), "decider_failures": len(calls) - len(ok),
        "decider_call_wall_ms": {"p50": pct([c["wall_ms"] for c in ok], 0.5),
                                 "p90": pct([c["wall_ms"] for c in ok], 0.9),
                                 "max": max((c["wall_ms"] for c in ok), default=None)},
        "decider_server_ms_p50": statistics.median([c["server_ms"] for c in ok if c.get("server_ms")] or [0]),
        "escalated": sum(row["escalated"] for row in rows),
        "fills": sum(row["decision"] == "fill" for row in rows),
        "top1_matches_editors": sum(row["top1_matches_editors"] for row in rows),
        "bedrock_live_calls": llm.inner.ledger.calls,
    }
    out.with_suffix(".json").write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
