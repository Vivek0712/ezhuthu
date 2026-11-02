"""Amazon Bedrock AgentCore Runtime entrypoint.

Payload: ``{"action": "restore|lesson|answer|assessment|progress|evaluate|corrections|queue|review|health", ...}``
with the same fields as the matching endpoint in contracts/restore-api.md (``review`` = POST /api/queue/{id}:
``{"action": "review", "id": ..., "review_action": "approve|edit|reject", "text"?}``). The response is the endpoint's JSON
body, or ``{"error": {"status": 403|404|422|500, "detail": "..."}}``. ``review`` and LLM-router ``evaluate`` need
``"admin_token"`` (the runtime's ``EZHUTHU_ADMIN_TOKEN``); request size limits are in ``ezhuthu.api.limits``.

Local run: ``python -m ezhuthu.agentcore_app`` (serves POST /invocations and GET /ping on :8080).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from .api.service import BadRequest, Conflict, EzhuthuService, Forbidden, NotFound

log = logging.getLogger(__name__)
_service: EzhuthuService | None = None


def service() -> EzhuthuService:
    global _service
    if _service is None:
        _service = EzhuthuService()
    return _service


def _require(p: dict[str, Any], *keys: str) -> None:
    missing = [k for k in keys if p.get(k) in (None, "")]
    if missing:
        raise BadRequest(f"missing field(s): {', '.join(missing)}")


def _restore(s: EzhuthuService, p: dict[str, Any]) -> Any:
    _require(p, "text")
    return s.restore(p["text"], p.get("script", "iso15919"), int(p.get("max_candidates", 5)),
                     bool(p.get("allow_escalation", True)))


def _lesson(s: EzhuthuService, p: dict[str, Any]) -> Any:
    return s.lesson(inscription_id=p.get("inscription_id"), text=p.get("text"), level=p.get("level", "L1"),
                    lang=p.get("lang", "ta"), session_id=p.get("session_id"))


def _answer(s: EzhuthuService, p: dict[str, Any]) -> Any:
    _require(p, "session_id", "item_id", "answer")
    return s.answer(p["session_id"], p["item_id"], p["answer"])


def _assessment(s: EzhuthuService, p: dict[str, Any]) -> Any:
    _require(p, "phase")
    if p["phase"] not in ("pre", "post"):
        raise BadRequest("phase must be 'pre' or 'post'")
    return s.assessment(p.get("session_id"), p["phase"])


def _progress(s: EzhuthuService, p: dict[str, Any]) -> Any:
    _require(p, "session_id")
    return s.progress(p["session_id"])


def _evaluate(s: EzhuthuService, p: dict[str, Any]) -> Any:
    return s.evaluate(benchmark=p.get("benchmark"), limit=p.get("limit"), router=p.get("router", "routed"),
                      records=p.get("records"), admin_token=p.get("admin_token"))


def _corrections(s: EzhuthuService, p: dict[str, Any]) -> Any:
    _require(p, "gap_ref")
    return s.add_correction(p["gap_ref"], accepted_candidate=p.get("accepted_candidate"),
                            corrected_text=p.get("corrected_text"), user=p.get("user"))


def _review(s: EzhuthuService, p: dict[str, Any]) -> Any:
    # "action" routes the invocation, so the queue action travels as "review_action" (approve|edit|reject).
    _require(p, "id", "review_action")
    return s.review(p["id"], p["review_action"], p.get("text"), p.get("reviewer"), admin_token=p.get("admin_token"))


ACTIONS: dict[str, Callable[[EzhuthuService, dict[str, Any]], Any]] = {
    "restore": _restore, "lesson": _lesson, "answer": _answer, "assessment": _assessment, "progress": _progress,
    "evaluate": _evaluate, "corrections": _corrections, "queue": lambda s, p: s.queue(), "review": _review,
    "health": lambda s, p: s.health(),
}


def handle(payload: dict[str, Any], svc: EzhuthuService | None = None) -> dict[str, Any]:
    """Route one AgentCore invocation. Pure function of (payload, service) so it is testable offline."""
    if not isinstance(payload, dict):
        return {"error": {"status": 422, "detail": "payload must be a JSON object"}}
    action = payload.get("action")
    fn = ACTIONS.get(action or "")
    if fn is None:
        return {"error": {"status": 422, "detail": f"action must be one of {sorted(ACTIONS)}"}}
    try:
        return fn(svc or service(), payload)
    except NotFound as exc:
        return {"error": {"status": 404, "detail": str(exc)}}
    except Forbidden as exc:
        return {"error": {"status": 403, "detail": str(exc)}}
    except Conflict as exc:
        return {"error": {"status": 409, "detail": str(exc)}}
    except (BadRequest, ValueError, TypeError) as exc:
        return {"error": {"status": 422, "detail": str(exc)}}
    except Exception as exc:
        log.exception("agentcore action %s failed", action)
        return {"error": {"status": 500, "detail": f"{type(exc).__name__}: {exc}"}}


_ROUTE_ACTIONS = {
    "/api/restore": "restore", "/api/lesson": "lesson", "/api/answer": "answer", "/api/assessment": "assessment",
    "/api/progress/{session_id}": "progress", "/api/evaluate": "evaluate", "/api/corrections": "corrections",
    "/api/queue": "queue", "/api/queue/{id}": "review", "/health": "health",
}


def handle_proxy(payload: dict[str, Any], svc: EzhuthuService | None = None) -> dict[str, Any]:
    """Adapt the infra Lambda proxy envelope (infra/README.md "Proxy to agent contract") to :func:`handle`.

    In: ``{"version": 1, "route": "/api/...", "body": {...}, "path_params": {...}, "session_id"?, "user"?}``.
    Out: ``{"status": <http status>, "body": <contract body | {"error": {"code", "message"}}>}``.
    Payloads that already carry ``action`` are passed through unchanged (AgentCore CLI / local use).
    """
    if not isinstance(payload, dict) or "action" in payload or "route" not in payload:
        return handle(payload, svc)
    action = _ROUTE_ACTIONS.get(str(payload.get("route")))
    if action is None:
        return {"status": 404, "body": {"error": {"code": "not_found", "message": f"no agent route {payload.get('route')}"}}}
    body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
    flat: dict[str, Any] = {**body, **(payload.get("path_params") or {}), "action": action}
    if payload.get("session_id"):  # the proxy mints the lesson session id; the agent must reuse it
        flat["session_id"] = payload["session_id"]
    if action == "review" and "action" in body:
        flat["review_action"] = body["action"]
    out = handle(flat, svc)
    err = out.get("error") if isinstance(out, dict) else None
    if isinstance(err, dict) and "status" in err and "detail" in err and len(out) == 1:
        status = int(err["status"])
        code = {403: "forbidden", 404: "not_found", 422: "bad_request"}.get(status, "internal")
        return {"status": status, "body": {"error": {"code": code, "message": str(err["detail"])}}}
    return {"status": 200, "body": out}


def create_agentcore_app():
    from bedrock_agentcore.runtime import BedrockAgentCoreApp

    app = BedrockAgentCoreApp()

    @app.entrypoint
    def invoke(payload: dict[str, Any]) -> dict[str, Any]:
        svc = service()
        if svc.tutor.task_hooks is None:  # /ping reports HealthyBusy while a lesson explanation runs
            svc.tutor.task_hooks = (app.add_async_task, app.complete_async_task)
        return handle_proxy(payload, svc)

    return app


try:  # module-level ``app`` is what the AgentCore starter toolkit / CLI look for
    app = create_agentcore_app()
except ImportError:  # bedrock-agentcore is the optional "agentcore" extra
    app = None

if __name__ == "__main__":
    if app is None:
        raise SystemExit("pip install -e '.[agentcore]' to run the AgentCore entrypoint")
    app.run()
