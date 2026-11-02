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
from . import limits
from .limits import Forbidden, check_text, check_token
from .records import parse_records
from .storage import Store, _iso, store_from_env

QUEUE_ACTIONS = {"approve": "approved", "edit": "edited", "reject": "rejected"}

__all__ = ["BadRequest", "Conflict", "EzhuthuService", "Forbidden", "NotFound"]


class Conflict(Exception):
    """The request conflicts with the item's state (HTTP 409), e.g. reviewing an already reviewed queue item."""


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
                 clock=time.time, admin_token: str | None | bool = True, open_review: bool | None = None):
        """``admin_token``: the shared secret for review actions and LLM evaluation (True = read
        ``EZHUTHU_ADMIN_TOKEN``; None = no token, so those actions are refused). ``open_review`` (default
        ``EZHUTHU_OPEN_REVIEW=1``) lets anyone act on the review queue, for local development only; in a
        deployment AgentCore (IAM/JWT) or the API gateway authenticates callers in front of this service."""
        self.store = store or store_from_env()
        self.admin_token = (os.environ.get("EZHUTHU_ADMIN_TOKEN") or None) if admin_token is True else admin_token
        self.open_review = os.environ.get("EZHUTHU_OPEN_REVIEW") == "1" if open_review is None else open_review
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
        if not isinstance(max_candidates, int) or not 1 <= max_candidates <= 20:
            raise BadRequest("max_candidates must be 1..20")
        check_text(text, script=script)
        if "[?" not in text:
            raise BadRequest("text has no gap marker ([?] or [?N])")
        return self.restorer.restore(text, script=script, max_candidates=max_candidates,
                                     allow_escalation=allow_escalation)

    def evaluate(self, *, benchmark: str | None = None, limit: int | None = None, router: str = "routed",
                 records: Any = None, admin_token: str | None = None) -> dict[str, Any]:
        if router not in ROUTERS:
            raise BadRequest(f"router must be one of {ROUTERS}")
        if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 1):
            raise BadRequest("limit must be a positive integer")
        live = self._llm is not None and router in (*LLM_ROUTERS, "baseline-zeroshot")
        if live and not check_token(admin_token, self.admin_token):
            raise Forbidden("evaluating with an LLM router calls Bedrock and needs the admin token")
        cap = limits.MAX_LIVE_EVAL_ITEMS if live else limits.MAX_EVAL_ITEMS
        if records is not None:
            items = [BenchmarkItem.from_dict(r) for r in parse_records(records)]
            items = [it for it in items if it.kind != "blank" and it.target][: limit or None]
        else:
            split, subset = parse_benchmark_name(benchmark or "test")
            try:
                items = load_items(split, subset=subset, limit=limit)
            except (FileNotFoundError, ValueError) as exc:
                raise BadRequest(str(exc)) from exc
        if len(items) > cap:
            raise BadRequest(f"at most {cap} items per request{' with an LLM router' if live else ''}; "
                             "use the CLI (python -m ezhuthu.eval.run) for full runs")
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
        for name, v in (("gap_ref", gap_ref), ("accepted_candidate", accepted_candidate),
                        ("corrected_text", corrected_text), ("user", user)):
            if v is not None and len(v) > limits.MAX_CORRECTION_CHARS:
                raise BadRequest(f"{name} is longer than {limits.MAX_CORRECTION_CHARS} characters")
        if corrected_text is not None:
            check_text(corrected_text, field="corrected_text")
        cid = f"q-{uuid.uuid4()}"  # the cloud proxy's queue id shape (infra/lambda/proxy/queue.ts review())
        doc = {"id": cid, "gap_ref": gap_ref, "accepted_candidate": accepted_candidate,
               "corrected_text": corrected_text, "user": user, "created_at": self.clock(), "status": "pending",
               "text": corrected_text or accepted_candidate, "history": []}
        self.store.put("correction", cid, doc)
        self.store.put("queue", cid, doc)
        return {"id": cid, "status": "pending"}

    def queue(self) -> dict[str, Any]:
        # created_at is epoch seconds here and ISO-8601 in items the cloud proxy wrote; compare as ISO.
        items = sorted(self.store.list("queue"), key=lambda d: (d.get("status") != "pending", _iso(d.get("created_at"))))
        return {"items": items, "pending": sum(1 for d in items if d["status"] == "pending")}

    def check_reviewer(self, admin_token: str | None) -> None:
        if self.open_review or check_token(admin_token, self.admin_token):
            return
        raise Forbidden("review actions need the reviewer token (X-Ezhuthu-Admin-Token)")

    def review(self, qid: str, action: str, text: str | None = None, reviewer: str | None = None, *,
               admin_token: str | None = None) -> dict[str, Any]:
        self.check_reviewer(admin_token)
        doc = self.store.get("queue", qid)
        if doc is None:
            raise NotFound(f"queue item {qid} not found")
        if action not in QUEUE_ACTIONS:
            raise BadRequest(f"action must be one of {sorted(QUEUE_ACTIONS)}")
        if action == "edit" and not text:
            raise BadRequest("edit needs text")
        if text is not None:
            check_text(text, field="text")
        if doc.get("status") != "pending":
            raise Conflict(f"queue item {qid} was already reviewed ({doc.get('status')})")
        now = self.clock()
        doc.setdefault("history", []).append({"action": action, "text": text, "reviewer": reviewer, "at": now,
                               "previous_status": doc["status"]})
        doc["status"] = QUEUE_ACTIONS[action]
        doc["reviewed_by"] = reviewer
        doc["reviewed_at"] = _iso(now)
        if action == "edit":
            doc["text"] = text
        if action == "approve":
            # As in the proxy: approve keeps the proposer's reading; an abstention has none, so it needs "edit".
            proposal = doc.get("corrected_text") or doc.get("accepted_candidate") or doc.get("text")
            if not proposal:
                raise BadRequest("nothing to approve; use edit with a reading")
            doc["text"] = proposal
        if action in ("approve", "edit"):
            doc["final_text"] = doc["text"]
        # Conditional on status=pending (as the proxy's review): two reviewers racing cannot both win.
        if not self.store.put_if_status("queue", qid, doc, "pending"):
            raise Conflict(f"queue item {qid} does not exist or was already reviewed")
        self.store.put("correction", qid, doc)
        return doc

    # ---- tutor -------------------------------------------------------------------
    def lesson(self, **kw: Any) -> dict[str, Any]:
        if kw.get("text") is not None:
            check_text(kw["text"])
        return self.tutor.lesson(**kw)

    def answer(self, session_id: str, item_id: str, answer: str) -> dict[str, Any]:
        if not isinstance(answer, str) or len(answer) > 500:
            raise BadRequest("answer must be a string of at most 500 characters")
        return self.tutor.answer(session_id, item_id, answer)

    def assessment(self, session_id: str | None, phase: str) -> dict[str, Any]:
        return self.tutor.assessment(session_id, phase)

    def progress(self, session_id: str) -> dict[str, Any]:
        return self.tutor.progress(session_id)

    def health(self) -> dict[str, Any]:
        h = self.decider.health() if hasattr(self.decider, "health") else None
        return {"status": "ok", "live_llm": self._llm is not None, "decider": (h or {}).get("model"),
                "decider_source": (h or {}).get("source", "local") if h else "fallback",
                "ontology": self.restorer.ontology.name, "corpus_lines": len(self.restorer.corpus),
                "models": self.config.llm}
