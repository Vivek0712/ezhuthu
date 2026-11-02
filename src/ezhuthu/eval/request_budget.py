"""Multi-gap ``restore()`` latency before/after the request budget (issue #41). VAL split only.

    python -m ezhuthu.eval.request_budget                       # offline: retrieval + 5-gram, no LLM
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.request_budget --live --max-live-calls 30

Requests are real VAL lines as a learner would send them: one benchmark item's context with its own gap and every
other supplied span of the line masked (``[?N]`` / ``[?]``), so one request carries several gaps.

* ``before``: a fresh restorer with no budget and no gap cap (the pre-#41 behaviour), cold: the first request pays
  the parallel index and 5-gram build.
* ``after``: a fresh restorer warmed first (as the runtime now does on start), with the shipped budget settings.
  With ``--live`` its LLM replies are replayed from the ``before`` run's cache, each after sleeping its original
  latency (a reply slower than the call's timeout sleeps the timeout and raises ``TimeoutError``, as Bedrock's read
  timeout would); a prompt the ``before`` run never sent (a later gap's context changed) is a live call.

Writes ``<out>.json``: per request and per gap, wall time, fills, budget fields, and LLM calls.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..agent.config import load_models_config
from ..agent.decider import NoDecider
from ..agent.llm import BedrockLLM, BudgetedLLM, LLMResponse
from ..agent.restorer import Restorer
from ..agent.text import find_gaps, to_iso

DEFAULT_ITEMS = ("DHARMA_INSCirkali00013:2:2", "DHARMA_INSKotumpalur00038:2:0", "DHARMA_INStfaSIIv04p0i0163:4:3")


def request_texts(ids: tuple[str, ...], path: Path) -> list[dict[str, Any]]:
    by_id = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        it = json.loads(line)
        by_id[it["id"]] = it
    out = []
    for i in ids:
        it = by_id[i]
        if it["split"] != "val":
            raise SystemExit(f"{i} is not a VAL item")
        marker = f"[?{it['gap_chars']}]" if it.get("gap_chars") else "[?]"
        text = it["left"] + marker + it["right"]
        out.append({"item": i, "inscription_id": it["inscription_id"], "text": text,
                    "gaps": len(find_gaps(to_iso(text, "iso15919")))})
    return out


class ReplayLLM:
    """Cached replies after their original latency (bounded by ``timeout_s``); misses go to ``live``."""

    def __init__(self, inner: BedrockLLM, live: BudgetedLLM | None):
        self.inner, self.live = inner, live
        self.config, self.ledger = inner.config, inner.ledger
        self.replayed = self.missed = self.timed_out = 0

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024,
                 timeout_s: float | None = None) -> LLMResponse:
        hit = self.inner.cache.get(self.inner.cache.key(self.inner.config.model_id(role), system, prompt, max_tokens))
        if hit is not None:
            self.replayed += 1
            lat = hit.latency_ms / 1000.0
            if timeout_s is not None and lat > timeout_s:
                time.sleep(timeout_s)
                self.timed_out += 1
                raise TimeoutError(f"replayed reply took {lat:.1f}s > timeout {timeout_s:.1f}s")
            time.sleep(lat)
            return hit
        self.missed += 1
        if self.live is None:
            from ..agent.llm import LiveCallsDisabled

            raise LiveCallsDisabled("not in the replay cache and --live is off")
        return self.live.complete(role, system, prompt, max_tokens=max_tokens, timeout_s=timeout_s)


def run(restorer: Restorer, reqs: list[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    rows = []
    for r in reqs:
        t0 = time.perf_counter()
        out = restorer.restore(r["text"])
        wall = time.perf_counter() - t0
        rows.append({"run": label, "item": r["item"], "gaps": r["gaps"], "wall_s": round(wall, 2),
                     "budget": out["budget"], "models_used": out["models_used"],
                     "gap_rows": [{"index": g["index"], "decision": g["decision"],
                                   "fill": g["candidates"][g["chosen"]]["text"] if g["chosen"] is not None else None,
                                   "top1": g["candidates"][0]["text"] if g["candidates"] else None,
                                   "escalated": g["escalated"],
                                   **{k: g[k] for k in ("abstain_reason", "llm_skipped", "escalation_skipped")
                                      if k in g}} for g in out["gaps"]]})
        print(f"{label:6s} {r['item']:40s} gaps={r['gaps']} wall={wall:6.2f}s budget={out['budget']}")
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--items", nargs="*", default=list(DEFAULT_ITEMS))
    ap.add_argument("--live", action="store_true", help="Bedrock calls (needs EZHUTHU_LIVE=1)")
    ap.add_argument("--max-live-calls", type=int, default=30)
    ap.add_argument("--cache-dir", default=None, help="LLM cache for this measurement (default: a fresh temp dir)")
    ap.add_argument("--out", default="eval/reports/2026-11-02-request-budget")
    args = ap.parse_args(argv)
    os.environ.setdefault("EZHUTHU_ONTOLOGY", "direct")
    cfg = load_models_config()
    from ..agent.data import data_source

    reqs = request_texts(tuple(args.items), data_source().path / "items.val.jsonl")
    llm_before = llm_after = None
    inner = live = replay = None
    if args.live:
        import tempfile

        cache = Path(args.cache_dir or tempfile.mkdtemp(prefix="ezhuthu-budget-"))
        inner = BedrockLLM(cache_dir=cache)
        live = BudgetedLLM(inner, args.max_live_calls)
        replay = ReplayLLM(inner, live)
        llm_before, llm_after = live, replay
    unbounded = replace(cfg.restorer, request_budget_s=None, max_gaps_per_request=None)

    t0 = time.perf_counter()
    before = Restorer(llm=llm_before, decider=NoDecider(), settings=unbounded)
    rows = run(before, reqs, "before")
    before_total = time.perf_counter() - t0
    calls_before = inner.ledger.calls if inner else 0

    after = Restorer(llm=llm_after, decider=NoDecider(), settings=cfg.restorer)
    warm = after.warm()
    print("warm-up", warm)
    rows += run(after, reqs, "after")
    out = {"items": args.items, "live": args.live, "settings": {k: getattr(cfg.restorer, k) for k in (
        "request_budget_s", "escalate_min_remaining_s", "llm_min_remaining_s", "gap_min_remaining_s",
        "max_gaps_per_request")}, "warm_up_s": warm, "before_total_s": round(before_total, 2), "rows": rows,
        "live_calls": {"before": calls_before, "after": (inner.ledger.calls - calls_before) if inner else 0,
                       "exhausted": live.exhausted if live else 0},
        "replay": {"replayed": replay.replayed, "missed": replay.missed, "timed_out": replay.timed_out}
        if replay else None}
    Path(args.out + ".json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote", args.out + ".json", "live calls", out["live_calls"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
