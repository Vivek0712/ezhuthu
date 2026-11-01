"""One core shared by the FastAPI app and the AgentCore entrypoint."""

from __future__ import annotations

import os
import time
import uuid
from functools import cached_property
from typing import Any

from ..agent.config import live_enabled, load_models_config
from ..agent.data import BenchmarkItem, load_items, parse_benchmark_name
from ..agent.decider import Decider, default_decider
from ..agent.llm import LLMClient, default_llm
from ..agent.restorer import Restorer
from ..agent.tutor.service import BadRequest, NotFound, TutorService
from ..eval.run import LLM_ROUTERS, ROUTERS, evaluate_items
from .storage import Store, store_from_env

MAX_EVAL_ITEMS = int(os.environ.get("EZHUTHU_MAX_EVAL_ITEMS", "500"))
QUEUE_ACTIONS = {"approve": "approved", "edit": "edited", "reject": "rejected"}

__all__ = ["BadRequest", "EzhuthuService", "NotFound"]


def default_model_factory():
    """Strands BedrockModel for the tutor team when live calls are enabled, else None (template path)."""
    if not live_enabled():
        return None
    import boto3
    from botocore.exceptions import ProfileNotFound
    from strands.models import BedrockModel

    cfg = load_models_config()
    try:
        session = boto3.Session(profile_name=cfg.aws_profile, region_name=cfg.region)
    except ProfileNotFound:
        session = boto3.Session(region_name=cfg.region)
    return BedrockModel(model_id=cfg.model_id("default"), boto_session=session, temperature=0.3, max_tokens=2000)


class EzhuthuService:
    def __init__(self, *, store: Store | None = None, llm: LLMClient | None | str = "default",
                 decider: Decider | None = None, restorer: Restorer | None = None, model_factory: Any = "default",
                 clock=time.time):
        self.store = store or store_from_env()
        self._llm = default_llm() if llm == "default" else llm
        self.decider = decider or default_decider()
        self.restorer = restorer or Restorer(llm=self._llm, decider=self.decider)
        self.tutor = TutorService(self.store, self.restorer, self.decider,
                                  model_factory=default_model_factory if model_factory == "default" else model_factory,
                                  clock=clock)
        self.clock = clock

    @cached_property
    def config(self):
        return self.restorer.config

    # ---- restore / evaluate ------------------------------------------------------
    def restore(self, text: str, script: str = "iso15919", max_candidates: int = 5,
                allow_escalation: bool = True) -> dict[str, Any]:
        if script not in ("iso15919", "tamil"):
            raise BadRequest("script must be 'iso15919' or 'tamil'")
        if not 1 <= max_candidates <= 20:
            raise BadRequest("max_candidates must be 1..20")
        if "[?" not in text:
            raise BadRequest("text has no gap marker ([?] or [?N])")
        return self.restorer.restore(text, script=script, max_candidates=max_candidates,
                                     allow_escalation=allow_escalation)

    def evaluate(self, *, benchmark: str | None = None, limit: int | None = None, router: str = "routed",
                 records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if router not in ROUTERS:
            raise BadRequest(f"router must be one of {ROUTERS}")
        if records is not None:
            try:
                items = [BenchmarkItem.from_dict(r) for r in records]
            except TypeError as exc:
                raise BadRequest(f"records do not match contracts/benchmark-item.schema.json: {exc}") from exc
            items = [it for it in items if it.kind != "blank" and it.target][: limit or None]
        else:
            split, subset = parse_benchmark_name(benchmark or "test")
            try:
                items = load_items(split, subset=subset, limit=limit)
            except (FileNotFoundError, ValueError) as exc:
                raise BadRequest(str(exc)) from exc
        if len(items) > MAX_EVAL_ITEMS:
            raise BadRequest(f"at most {MAX_EVAL_ITEMS} items per request; use the CLI for full runs")
        effective = router
        if self._llm is None and router in (*LLM_ROUTERS, "baseline-zeroshot"):
            if router == "baseline-zeroshot":
                raise BadRequest("baseline-zeroshot needs a live LLM (EZHUTHU_LIVE=1 on the server)")
            effective = "none"  # no live LLM here: say so instead of labelling LLM-free results "routed"
        out = evaluate_items(items, router=effective, restorer=self.restorer, llm=self._llm)
        out["router_requested"], out["router_effective"] = router, effective
        return out

    # ---- corrections and review queue --------------------------------------------
    def add_correction(self, gap_ref: str, *, accepted_candidate: str | None = None,
                       corrected_text: str | None = None, user: str | None = None) -> dict[str, Any]:
        if not gap_ref:
            raise BadRequest("gap_ref is required")
        if not (accepted_candidate or corrected_text):
            raise BadRequest("give accepted_candidate or corrected_text")
        cid = uuid.uuid4().hex
        doc = {"id": cid, "gap_ref": gap_ref, "accepted_candidate": accepted_candidate,
               "corrected_text": corrected_text, "user": user, "created_at": self.clock(), "status": "pending",
               "text": corrected_text or accepted_candidate, "history": []}
        self.store.put("correction", cid, doc)
        self.store.put("queue", cid, doc)
        return {"id": cid, "status": "pending"}

    def queue(self) -> dict[str, Any]:
        items = sorted(self.store.list("queue"), key=lambda d: (d["status"] != "pending", d["created_at"]))
        return {"items": items, "pending": sum(1 for d in items if d["status"] == "pending")}

    def review(self, qid: str, action: str, text: str | None = None, reviewer: str | None = None) -> dict[str, Any]:
        doc = self.store.get("queue", qid)
        if doc is None:
            raise NotFound(f"queue item {qid} not found")
        if action not in QUEUE_ACTIONS:
            raise BadRequest(f"action must be one of {sorted(QUEUE_ACTIONS)}")
        if action == "edit" and not text:
            raise BadRequest("edit needs text")
        doc["history"].append({"action": action, "text": text, "reviewer": reviewer, "at": self.clock(),
                               "previous_status": doc["status"]})
        doc["status"] = QUEUE_ACTIONS[action]
        if action == "edit":
            doc["text"] = text
        self.store.put("queue", qid, doc)
        self.store.put("correction", qid, doc)
        return doc

    # ---- tutor -------------------------------------------------------------------
    def lesson(self, **kw: Any) -> dict[str, Any]:
        return self.tutor.lesson(**kw)

    def answer(self, session_id: str, item_id: str, answer: str) -> dict[str, Any]:
        return self.tutor.answer(session_id, item_id, answer)

    def assessment(self, session_id: str | None, phase: str) -> dict[str, Any]:
        return self.tutor.assessment(session_id, phase)

    def progress(self, session_id: str) -> dict[str, Any]:
        return self.tutor.progress(session_id)

    def health(self) -> dict[str, Any]:
        h = self.decider.health() if hasattr(self.decider, "health") else None
        return {"status": "ok", "live_llm": self._llm is not None, "decider": (h or {}).get("model"),
                "ontology": self.restorer.ontology.name, "corpus_lines": len(self.restorer.corpus),
                "models": self.config.llm}
