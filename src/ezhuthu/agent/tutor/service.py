"""Tutor service behind /api/lesson, /api/answer, /api/assessment and /api/progress."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import statistics
import threading
import time
import uuid
import zlib
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

from ..data import inscription_meta, inscription_text, load_inscriptions
from ..decider import Decider
from ..restorer import Restorer
from ..text import GAP_RE, LEVELS, iso_to_tamil, looks_tamil, normalize_iso, tamil_to_iso
from . import policy
from .feedback import feedback
from .graph import build_lesson_graph, explain_with_team, run_lesson_graph, tutor_task_text
from .lesson import Item, assessment_items, build_items, grade

log = logging.getLogger(__name__)
EXPLAIN_MODES = ("async", "sync")
CACHE_SIZE = 256


def explain_mode() -> str:
    """``EZHUTHU_LESSON_EXPLAIN``: ``async`` (default) answers /api/lesson with the template explanation and runs
    the Tutor + Assessor Swarm in the background; ``sync`` runs the Swarm inside the lesson Graph (pre-#22)."""
    m = (os.environ.get("EZHUTHU_LESSON_EXPLAIN") or "async").strip().lower()
    return m if m in EXPLAIN_MODES else "async"


def facts_key(facts: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(facts, ensure_ascii=False, sort_keys=True, default=str).encode()).hexdigest()[:24]


class _LRU:
    def __init__(self, size: int = CACHE_SIZE):
        self.size, self._d, self._lock = size, OrderedDict(), threading.Lock()

    def get(self, k: str) -> Any:
        with self._lock:
            if k in self._d:
                self._d.move_to_end(k)
                return self._d[k]
        return None

    def put(self, k: str, v: Any) -> None:
        with self._lock:
            self._d[k] = v
            self._d.move_to_end(k)
            while len(self._d) > self.size:
                self._d.popitem(last=False)


class NotFound(LookupError):
    pass


class BadRequest(ValueError):
    pass


def _clean_text(text: str) -> str:
    lines = [normalize_iso(ln) for ln in text.split("\n")]
    return "\n".join(ln for ln in lines if ln)


class TutorService:
    def __init__(self, store: Any, restorer: Restorer, decider: Decider, *,
                 model_factory: Callable[[], Any] | None = None, clock: Callable[[], float] = time.time):
        self.store = store
        self.restorer = restorer
        self.decider = decider
        self.model_factory = model_factory
        self.clock = clock
        # Per-process caches (an AgentCore session keeps one learner on one microVM, so they stay warm):
        self.restorations = _LRU()  # restored text of an inscription (restoration is deterministic per text)
        self.explanations = _LRU()  # facts_key -> {"explain_ta", "explain_en"} from the Swarm
        self._pending: dict[str, threading.Thread] = {}
        self._pending_lock = threading.Lock()
        # (start(name) -> token, done(token)): the AgentCore app marks the runtime HealthyBusy while
        # a background explanation runs (BedrockAgentCoreApp.add_async_task / complete_async_task).
        self.task_hooks: tuple[Callable[[str], Any], Callable[[Any], Any]] | None = None

    # ---- sessions ----------------------------------------------------------------
    def _new_session(self, session_id: str | None = None) -> dict[str, Any]:
        now = self.clock()
        return {"session_id": session_id or uuid.uuid4().hex, "created_at": now, "last_event_at": now,
                "items": {}, "phases": {}, "lessons": [], "answers": []}

    def _load(self, session_id: str) -> dict[str, Any]:
        s = self.store.get("session", session_id)
        if s is None:
            raise NotFound(f"session {session_id} not found")
        return s

    def _add_items(self, s: dict[str, Any], items: list[Item]) -> None:
        now = self.clock()
        for it in items:
            s["items"][it.item_id] = {**it.to_dict(), "issued_at": now, "attempts": 0, "hint_given": False,
                                      "first_correct": None, "first_seconds": None, "done": False}
        s["last_event_at"] = now

    # ---- lesson ------------------------------------------------------------------
    def _resolve_text(self, inscription_id: str | None, text: str | None) -> tuple[str, dict[str, Any]]:
        if text is not None:
            iso = _clean_text(tamil_to_iso(text) if looks_tamil(text) else text)
            if not iso:
                raise BadRequest("text is empty")
            return iso, inscription_meta({"id": "user-text"})
        metas = load_inscriptions()
        if inscription_id is None:
            for iid in metas:
                t = inscription_text(iid)
                if t:
                    return _clean_text(t), inscription_meta(metas[iid])
            raise NotFound("no inscriptions available")
        t = inscription_text(inscription_id)
        if not t:
            raise NotFound(f"inscription {inscription_id} not found")
        return _clean_text(t), inscription_meta(metas.get(inscription_id, {"id": inscription_id}))

    def lesson(self, *, inscription_id: str | None = None, text: str | None = None, level: str = "L1",
               lang: str = "ta", session_id: str | None = None) -> dict[str, Any]:
        if level not in LEVELS:
            raise BadRequest(f"level must be one of {LEVELS}")
        if lang not in ("ta", "en"):
            raise BadRequest("lang must be 'ta' or 'en'")
        iso, meta = self._resolve_text(inscription_id, text)
        ctx: dict[str, Any] = {"text": iso, "level": level, "lang": lang, "meta": meta}

        def restore_fn(c: dict[str, Any]) -> str:
            if GAP_RE.search(c["text"]):
                key = hashlib.sha256(c["text"].encode()).hexdigest()
                res = self.restorations.get(key)
                if res is None:
                    res = self.restorer.restore(c["text"], max_candidates=5)
                    self.restorations.put(key, res)
                    c["restore_cached"] = False
                else:
                    res = {**res, "trace_id": uuid.uuid4().hex, "latency_ms": 0.0, "cached": True}
                    c["restore_cached"] = True
                c["restore_result"] = res
                c["restored"] = res["restored_text"]
            else:
                c["restore_result"], c["restored"] = None, c["text"]
            return c["restored"]

        def build_fn(c: dict[str, Any]) -> str:
            c["items"] = build_items(c["restored"], c["level"])
            ents = self.restorer.ontology.find_entities(c["restored"])
            c["entities"] = ents
            gaps = (c["restore_result"] or {}).get("gaps", [])
            c["facts"] = {
                "title": meta.get("title"), "dynasty": meta.get("dynasty"), "approx_date": meta.get("approx_date"),
                "ruler": meta.get("ruler"), "regnal_year": meta.get("regnal_year"),
                "level": c["level"], "text_iso": c["restored"],
                "entities": [{"kind": h.kind, "label": h.label, "label_ta": h.label_ta} for h in ents],
                "restored_gaps": sum(1 for g in gaps if g["decision"] == "fill"),
                "abstained_gaps": sum(1 for g in gaps if g["decision"] == "abstain"),
            }
            return tutor_task_text(c)

        mode = explain_mode()
        model = self.model_factory() if self.model_factory else None
        # async: the Graph ends at explain_template (fast); the Swarm runs after the response (below).
        graph = build_lesson_graph(restore_fn=restore_fn, build_fn=build_fn,
                                   model=model if mode == "sync" else None)
        run_lesson_graph(graph, ctx)
        fkey = facts_key(ctx["facts"])
        explanation_status = "done" if ctx["explained_by"] in ("tutor_team",) else "template"
        if ctx["explained_by"] == "tutor_team":
            self.explanations.put(fkey, ctx["context_text"])
        cached = self.explanations.get(fkey)
        if cached is not None and ctx["explained_by"] != "tutor_team":
            ctx["context_text"], ctx["explained_by"], explanation_status = cached, "tutor_team-cached", "done"
        elif mode == "async" and model is not None:
            explanation_status = "pending"
            self._explain_later(fkey, model, ctx["facts"])

        # An unknown session_id starts a session with that id (the cloud proxy mints ids as "s-<uuid>").
        s = (self.store.get("session", session_id) or self._new_session(session_id)) if session_id else self._new_session()
        self._add_items(s, ctx["items"])
        s["lessons"].append({"inscription_id": meta.get("id"), "level": level, "lang": lang,
                             "item_ids": [i.item_id for i in ctx["items"]], "explained_by": ctx["explained_by"],
                             "explain_key": fkey, "explanation_status": explanation_status})
        self.store.put("session", s["session_id"], s)

        def first(kinds: tuple[str, ...]) -> str | None:
            return next((h.label for h in ctx["entities"] if h.kind in kinds), None)

        context = {**ctx["context_text"], "explained_by": ctx["explained_by"],
                   "explanation_status": explanation_status}
        if meta.get("ruler"):  # the edition's own metadata beats an ontology match in the text
            context["ruler"] = meta["ruler"]
        for key, kinds in (("ruler", ("ruler", "title")), ("temple", ("temple",)), ("grant", ("grant_type",))):
            v = first(kinds)
            if v and key not in context:
                context[key] = v
        restored = ctx["restored"]
        return {
            "session_id": s["session_id"],
            "inscription": {"id": meta.get("id"), "title": meta.get("title"), "dynasty": meta.get("dynasty"),
                            "approx_date": meta.get("approx_date"), "source_url": meta.get("source_url"),
                            "ruler": meta.get("ruler"), "regnal_year": meta.get("regnal_year"),
                            "dharmalekha_url": meta.get("dharmalekha_url"), "licence": meta.get("licence"),
                            "restored_text": restored, "restored_text_tamil": iso_to_tamil(restored)},
            "items": [i.to_api() for i in ctx["items"]],
            "context": context,
            "restoration": ctx["restore_result"],
            "graph": {"nodes": ctx.get("graph_nodes", []), "status": ctx.get("graph_status"),
                      "explain": mode, "restoration_cached": bool(ctx.get("restore_cached"))},
        }

    # ---- background explanation ----------------------------------------------------
    def _explain_later(self, fkey: str, model: Any, facts: dict[str, Any]) -> None:
        """Run the Tutor + Assessor Swarm after the lesson response; the result lands in ``self.explanations`` and
        reaches the learner on the next /api/answer (``context_update``) or the next lesson on the same facts."""
        with self._pending_lock:
            if fkey in self._pending and self._pending[fkey].is_alive():
                return

            def work() -> None:
                token = None
                try:
                    if self.task_hooks:
                        token = self.task_hooks[0]("lesson_explanation")
                    exp = explain_with_team(model, facts)
                    if exp:
                        self.explanations.put(fkey, exp)
                    else:
                        log.warning("tutor_team produced no JSON explanation; the template stays")
                except Exception as exc:  # noqa: BLE001 - background work must never crash the runtime
                    log.warning("background explanation failed: %s", type(exc).__name__)
                finally:
                    if self.task_hooks and token is not None:
                        self.task_hooks[1](token)
                    with self._pending_lock:
                        self._pending.pop(fkey, None)

            th = threading.Thread(target=work, name=f"ezhuthu-explain-{fkey[:8]}", daemon=True)
            self._pending[fkey] = th
        th.start()

    def wait_explanations(self, timeout: float = 120.0) -> None:
        """Block until background explanations finish (tests, offline profiling)."""
        with self._pending_lock:
            threads = list(self._pending.values())
        for th in threads:
            th.join(timeout)

    def _context_update(self, s: dict[str, Any]) -> dict[str, Any] | None:
        """The finished Swarm explanation for the session's latest lesson, once (marks it delivered)."""
        if not s.get("lessons"):
            return None
        les = s["lessons"][-1]
        if les.get("explanation_status") != "pending":
            return None
        exp = self.explanations.get(les.get("explain_key", ""))
        if exp is None:
            return None
        les["explanation_status"], les["explained_by"] = "done", "tutor_team"
        return {**exp, "explained_by": "tutor_team", "explanation_status": "done"}

    # ---- answers -----------------------------------------------------------------
    def answer(self, session_id: str, item_id: str, answer: str) -> dict[str, Any]:
        s = self._load(session_id)
        rec = s["items"].get(item_id)
        if rec is None:
            raise NotFound(f"item {item_id} not in session {session_id}")
        now = self.clock()
        seconds = round(max(0.0, now - max(rec["issued_at"], s["last_event_at"])), 3)
        item = Item(**{k: rec[k] for k in Item.__dataclass_fields__})
        correct, err = grade(item, answer)
        rec["attempts"] += 1
        if rec["first_correct"] is None:
            rec["first_correct"], rec["first_seconds"] = correct, seconds
        s["answers"].append({"item_id": item_id, "answer": answer, "correct": correct, "cer": err,
                             "seconds": seconds, "at": now})
        s["last_event_at"] = now

        if rec["phase"] in ("pre", "post"):
            # Tests measure, they do not teach: no hints, no reveal, always move on.
            rec["done"] = True
            self.store.put("session", session_id, s)
            return {"correct": correct, "feedback_ta": "உங்கள் பதில் பதிவு செய்யப்பட்டது.",
                    "feedback_en": "Your answer has been recorded.", "next_action": "advance",
                    "decider_confidence": None, "decider_source": "assessment", "cer": err}

        answered = [a for a in s["answers"] if s["items"].get(a["item_id"], {}).get("phase") == "lesson"]
        recent = answered[-5:]
        state = {
            "item_type": rec["type"], "script_level": rec["script_level"], "correct": correct,
            "character_error_rate": err, "attempts_on_item": rec["attempts"],
            "hint_already_given": rec["hint_given"], "seconds_on_item": seconds,
            "recent_accuracy": round(sum(a["correct"] for a in recent) / len(recent), 2) if recent else None,
            "items_remaining": sum(1 for r in s["items"].values() if r["phase"] == "lesson" and not r["done"]),
        }
        d = policy.decide(self.decider, state)
        if d.action == "hint":
            rec["hint_given"] = True
        if d.action == "advance":
            rec["done"] = True
        fb = feedback(correct, d.action, rec["type"], rec["answer"])
        update = self._context_update(s)
        self.store.put("session", session_id, s)
        out = {"correct": correct, **fb, "next_action": d.action, "decider_confidence": d.confidence,
               "decider_source": d.source, "decider_backend": d.backend, "policy_overridden": d.overridden, "cer": err}
        if update:
            out["context_update"] = update  # additive: the Swarm explanation finished after /api/lesson returned
        return out

    # ---- assessment and progress -------------------------------------------------
    def assessment(self, session_id: str | None, phase: str) -> dict[str, Any]:
        if phase not in ("pre", "post"):
            raise BadRequest("phase must be 'pre' or 'post'")
        s = self.store.get("session", session_id) if session_id else None
        s = s or self._new_session(session_id)
        if phase in s["phases"]:
            ids = s["phases"][phase]
            return {"session_id": s["session_id"], "phase": phase,
                    "items": [Item(**{k: s["items"][i][k] for k in Item.__dataclass_fields__}).to_api()
                              for i in ids]}
        seed = zlib.crc32(s["session_id"].encode())  # stable across processes, unlike hash()
        items = assessment_items(phase, seed)
        self._add_items(s, items)
        s["phases"][phase] = [i.item_id for i in items]
        self.store.put("session", s["session_id"], s)
        return {"session_id": s["session_id"], "phase": phase, "items": [i.to_api() for i in items]}

    def progress(self, session_id: str) -> dict[str, Any]:
        s = self._load(session_id)

        def score(phase: str) -> float | None:
            ids = s["phases"].get(phase)
            if not ids:
                return None
            return round(sum(1 for i in ids if s["items"][i]["first_correct"]) / len(ids), 4)

        pre, post = score("pre"), score("post")
        by_level = {lv: 0 for lv in LEVELS}
        secs = []
        for r in s["items"].values():
            if r["type"] != "letter" or r["first_correct"] is None:
                continue
            secs.append(r["first_seconds"])
            if r["first_correct"]:
                by_level[r["script_level"]] += 1
        answered = {p: sum(1 for i in s["phases"].get(p, []) if s["items"][i]["first_correct"] is not None)
                    for p in ("pre", "post")}
        return {"pre_score": pre, "post_score": post,
                "gain": round(post - pre, 4) if pre is not None and post is not None else None,
                "letters_correct_by_level": by_level,
                "median_seconds_per_letter": round(statistics.median(secs), 2) if secs else None,
                "answered": answered, "score_basis": "first-attempt correct / 10 test items"}

