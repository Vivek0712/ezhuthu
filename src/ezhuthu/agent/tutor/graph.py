"""The lesson flow as a Strands Graph, with a Tutor + Assessor Swarm inside the tutoring step.

    restore ──► lesson_builder ──► tutor_team (Swarm: tutor ⇄ assessor)   [when an LLM model is available]
                              └──► explain_template                       [offline / fallback]

``restore`` and ``lesson_builder`` are deterministic function nodes (they share a context dict through
``invocation_state``); the Swarm agents write the learner-facing explanation from the lesson facts and the
Assessor checks it against those facts.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

from strands import Agent
from strands.agent import AgentResult
from strands.multiagent import GraphBuilder, Swarm
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.telemetry.metrics import EventLoopMetrics

from ..prompts import ASSESSOR_SYSTEM, TUTOR_SYSTEM, explain_prompt, parse_json_object, sanitize_explanation
from .feedback import explain_template

log = logging.getLogger(__name__)
CTX_KEY = "ezhuthu_lesson"


class FunctionNode(MultiAgentBase):
    """A deterministic Graph node: ``fn(ctx) -> str`` over the shared lesson context."""

    def __init__(self, node_id: str, fn: Callable[[dict[str, Any]], str]):
        super().__init__()
        self.id = node_id
        self.fn = fn

    async def invoke_async(self, task: Any, invocation_state: dict[str, Any] | None = None,
                           **kwargs: Any) -> MultiAgentResult:
        t0 = time.time()
        ctx = (invocation_state or {}).get(CTX_KEY)
        if ctx is None:
            raise ValueError(f"{self.id}: invocation_state[{CTX_KEY!r}] missing")
        text = self.fn(ctx)
        result = AgentResult(stop_reason="end_turn", message={"role": "assistant", "content": [{"text": text}]},
                             metrics=EventLoopMetrics(), state={})
        ms = int((time.time() - t0) * 1000)
        return MultiAgentResult(status=Status.COMPLETED,
                                results={self.id: NodeResult(result=result, execution_time=ms, status=Status.COMPLETED)},
                                execution_count=1, execution_time=ms)

    def serialize_state(self) -> dict[str, Any]:
        return {"type": "function_node", "id": self.id}

    def deserialize_state(self, payload: dict[str, Any]) -> None:
        return None


def build_tutor_team(model: Any) -> Swarm:
    tutor = Agent(name="tutor", model=model, system_prompt=TUTOR_SYSTEM, callback_handler=None,
                  description="Writes the learner-facing explanation in Tamil and English.")
    assessor = Agent(name="assessor", model=model, system_prompt=ASSESSOR_SYSTEM, callback_handler=None,
                     description="Checks the explanation against the facts and returns final JSON.")
    return Swarm([tutor, assessor], entry_point=tutor, max_handoffs=4, max_iterations=4,
                 execution_timeout=120.0, node_timeout=60.0, id="tutor_team")


def build_lesson_graph(*, restore_fn: Callable[[dict[str, Any]], str], build_fn: Callable[[dict[str, Any]], str],
                       model: Any | None) -> Any:
    b = GraphBuilder()
    b.add_node(FunctionNode("restore", restore_fn), "restore")
    b.add_node(FunctionNode("lesson_builder", build_fn), "lesson_builder")
    b.add_edge("restore", "lesson_builder")

    def _template(ctx: dict[str, Any]) -> str:
        ctx["context_text"] = explain_template(ctx["facts"])
        ctx["explained_by"] = "template"
        return json.dumps(ctx["context_text"], ensure_ascii=False)

    b.add_node(FunctionNode("explain_template", _template), "explain_template")
    if model is not None:
        b.add_node(build_tutor_team(model), "tutor_team")
        b.add_edge("lesson_builder", "tutor_team")
    else:
        b.add_edge("lesson_builder", "explain_template")
    b.set_entry_point("restore")
    b.set_execution_timeout(180.0)
    return b.build()


def swarm_explanation(result: Any) -> dict[str, str] | None:
    """Pull ``{"explain_ta", "explain_en"}`` from the tutor_team node's last agent output."""
    node = getattr(result, "results", {}).get("tutor_team")
    if node is None or not isinstance(node.result, MultiAgentResult):
        return None
    return team_explanation(node.result)


def team_explanation(inner: Any) -> dict[str, str] | None:
    """``{"explain_ta", "explain_en"}`` from a tutor_team Swarm result (last agent output with both keys)."""
    if not isinstance(inner, MultiAgentResult):
        return None
    order = [n.node_id for n in getattr(inner, "node_history", [])] or list(inner.results)
    for node_id in reversed(order):
        nr = inner.results.get(node_id)
        if nr is None:
            continue
        d = parse_json_object(str(nr.result))
        if d and isinstance(d.get("explain_ta"), str) and isinstance(d.get("explain_en"), str):
            out = {"explain_ta": sanitize_explanation(d["explain_ta"]),
                   "explain_en": sanitize_explanation(d["explain_en"])}
            if out["explain_ta"] and out["explain_en"]:
                return out
    return None


def run_lesson_graph(graph: Any, ctx: dict[str, Any]) -> dict[str, Any]:
    task = "Build a reading lesson. Facts follow after the lesson builder runs."
    result = graph(task, invocation_state={CTX_KEY: ctx})
    ctx["graph_status"] = str(getattr(result, "status", ""))
    ctx["graph_nodes"] = [n.node_id for n in getattr(result, "execution_order", [])]
    if "tutor_team" in getattr(result, "results", {}):
        exp = swarm_explanation(result)
        if exp:
            ctx["context_text"], ctx["explained_by"] = exp, "tutor_team"
        else:
            log.warning("tutor_team produced no JSON explanation; using template")
            ctx["context_text"], ctx["explained_by"] = explain_template(ctx["facts"]), "template-fallback"
    return ctx


def explain_with_team(model: Any, facts: dict[str, Any]) -> dict[str, str] | None:
    """Run the Tutor + Assessor Swarm on its own (the async path of /api/lesson); None if no usable JSON."""
    team = build_tutor_team(model)
    return team_explanation(team(explain_prompt(facts)))


def tutor_task_text(ctx: dict[str, Any]) -> str:
    """What the lesson_builder node hands to the tutor team."""
    return explain_prompt(ctx["facts"])
