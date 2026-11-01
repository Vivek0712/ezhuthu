"""Live wiring smoke: proves Bedrock (Sonnet 4.6, Opus 4.6), the decider and the tutor Swarm are wired.

    EZHUTHU_LIVE=1 EZHUTHU_FIXTURES=1 python -m ezhuthu.eval.smoke [--decider-url http://127.0.0.1:8765]

At most ``MAX_CALLS`` Bedrock model calls (Strands Swarm turns included). Inputs are the synthetic fixtures,
so this checks plumbing, not quality. Writes ``eval/reports/<date>-live-wiring-smoke.{json,md}``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path
from typing import Any

from ..agent.config import live_enabled, load_models_config, repo_root
from ..agent.decider import HttpDecider, NoDecider
from ..agent.llm import BedrockLLM, LLMResponse, short_name
from ..agent.restorer import Restorer
from ..agent.tutor.service import TutorService
from ..api.storage import MemoryStore

MAX_CALLS = 6


class CallBudget:
    def __init__(self, limit: int):
        self.limit, self.used = limit, 0
        self.log: list[dict[str, Any]] = []

    def take(self, what: str, model_id: str) -> None:
        if self.used >= self.limit:
            raise RuntimeError(f"live call budget of {self.limit} exhausted before {what}")
        self.used += 1
        self.log.append({"n": self.used, "what": what, "model_id": model_id})


class BudgetedLLM(BedrockLLM):
    def __init__(self, budget: CallBudget, **kw: Any):
        super().__init__(**kw)
        self.budget = budget
        self.responses: list[dict[str, Any]] = []

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024) -> LLMResponse:
        mid = self.config.model_id(role)
        if self.cache.get(self.cache.key(mid, system, prompt, max_tokens)) is None:
            self.budget.take(f"propose_fills[{role}]", mid)
        r = super().complete(role, system, prompt, max_tokens=max_tokens)
        self.responses.append({"model_id": r.model_id, "cached": r.cached, "input_tokens": r.input_tokens,
                               "output_tokens": r.output_tokens, "latency_ms": r.latency_ms, "text": r.text[:600]})
        return r


def counting_bedrock_model(budget: CallBudget, usage: dict[str, int]):
    import boto3
    from botocore.exceptions import ProfileNotFound
    from strands.models import BedrockModel

    cfg = load_models_config()

    class CountingModel(BedrockModel):
        async def stream(self, *args: Any, **kwargs: Any):
            budget.take("tutor_team turn", self.config["model_id"])
            async for ev in super().stream(*args, **kwargs):
                u = ev.get("metadata", {}).get("usage") if isinstance(ev, dict) else None
                if u:
                    usage["input_tokens"] += u.get("inputTokens", 0)
                    usage["output_tokens"] += u.get("outputTokens", 0)
                yield ev

    try:
        session = boto3.Session(profile_name=cfg.aws_profile, region_name=cfg.region)
    except ProfileNotFound:
        session = boto3.Session(region_name=cfg.region)
    return CountingModel(model_id=cfg.model_id("default"), boto_session=session, temperature=0.3, max_tokens=2000)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decider-url", default="http://127.0.0.1:8765")
    ap.add_argument("--out", default=None)
    ap.add_argument("--skip-swarm", action="store_true", help="do not run the tutor_team Swarm live")
    ap.add_argument("--max-calls", type=int, default=MAX_CALLS)
    ap.add_argument("--note", action="append", default=[], help="operator note to record in the report")
    args = ap.parse_args(argv)
    if not live_enabled():
        print("set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    budget = CallBudget(min(args.max_calls, MAX_CALLS))
    llm = BudgetedLLM(budget)
    decider = HttpDecider(args.decider_url)
    decider = decider if decider.available() else NoDecider()
    restorer = Restorer(llm=llm, decider=decider)
    report: dict[str, Any] = {"date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                              "models": llm.config.llm, "decider": (decider.health() or {}).get("model")
                              if isinstance(decider, HttpDecider) else None, "steps": []}

    for router, left, right, n in (
        ("sonnet", "mahādēvarkku nantā viḷakku ", " vaitta āṭu toṇṇūṟu", 7),
        ("opus", "kōvicaiya kampavarmaṟku yāṇṭu ", "", 9),
    ):
        t0 = time.perf_counter()
        g = restorer.restore_gap(left, right, n, router=router, max_candidates=5)
        report["steps"].append({
            "step": f"restore_gap router={router}", "input": {"left": left, "right": right, "gap_chars": n},
            "decision": g.decision, "decider_model": g.decider_model, "models_used": g.models_used,
            "top": [{"text": c.text, "confidence": round(c.confidence, 4), "model": c.model,
                     "sources": sorted(c.sources)} for c in g.candidates[:5]],
            "wall_ms": round((time.perf_counter() - t0) * 1000),
        })

    swarm_usage = {"input_tokens": 0, "output_tokens": 0}
    if args.skip_swarm:
        report["steps"].append({"step": "lesson graph (tutor_team swarm)", "skipped": "--skip-swarm"})
    else:
        tutor = TutorService(MemoryStore(), restorer, decider,
                             model_factory=lambda: counting_bedrock_model(budget, swarm_usage))
        t0 = time.perf_counter()
        step: dict[str, Any] = {"step": "lesson graph (tutor_team swarm on default model)"}
        try:
            lesson = tutor.lesson(inscription_id="FIXTURE_CHOLA_002", level="L2")
            step.update({"graph": lesson["graph"], "explained_by": lesson["context"]["explained_by"],
                         "explain_ta": lesson["context"]["explain_ta"], "explain_en": lesson["context"]["explain_en"]})
        except Exception as exc:  # noqa: BLE001 - record what happened (e.g. budget stop) instead of crashing
            step["error"] = f"{type(exc).__name__}: {exc}"
        step.update({"swarm_usage": swarm_usage, "wall_ms": round((time.perf_counter() - t0) * 1000)})
        report["steps"].append(step)
    report["bedrock_calls"] = budget.log
    report["llm_responses"] = llm.responses
    report["usage"] = llm.ledger.to_dict()
    report["swarm_usage"] = swarm_usage
    report["notes"] = args.note

    root = repo_root() or Path.cwd()
    out = Path(args.out) if args.out else root / "eval" / "reports"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{dt.date.today().isoformat()}-live-wiring-smoke"
    (out / f"{stem}.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    md = [f"# Live wiring smoke ({report['date']})", "",
          ("> Synthetic fixture inputs. This proves the wiring (Bedrock via Strands, Strands Decider, Graph + Swarm); "
          "it is **not** a quality measurement and must not be cited as one."), "",
          f"- Bedrock model calls: {budget.used} (cap {MAX_CALLS})",
          f"- Decider: {report['decider'] or 'not reachable (fallback)'}", ""]
    md += [f"- Note: {n}" for n in args.note] + ([""] if args.note else [])
    for s in report["steps"]:
        md += [f"## {s['step']}", "", "```json", json.dumps(s, ensure_ascii=False, indent=1), "```", ""]
    u = report["usage"]
    md.append(f"Restore-path tokens: input {u['input_tokens']}, output {u['output_tokens']}; swarm tokens: "
              f"{swarm_usage}. Estimated restore-path cost ${u['estimated_cost_usd']} (list prices).")
    md.append("")
    md.append("Models: " + ", ".join(sorted({short_name(c['model_id']) + '=' + c['model_id']
                                             for c in budget.log})))
    (out / f"{stem}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps({"calls": budget.used, "report": str(out / f"{stem}.md")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
