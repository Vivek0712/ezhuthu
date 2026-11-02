"""FastAPI app implementing contracts/restore-api.md.

    uvicorn ezhuthu.api.app:app --port 8080
"""

from __future__ import annotations

import json
import os
from typing import Annotated, Any, Literal

from fastapi import FastAPI, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..agent.data import parse_jsonl_text
from ..eval.run import ROUTERS
from . import limits
from .service import BadRequest, Conflict, EzhuthuService, Forbidden, NotFound

AdminToken = Annotated[str | None, Header(alias="X-Ezhuthu-Admin-Token")]
DEV_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:4173", "http://127.0.0.1:4173")


def cors_origins() -> list[str]:
    """``EZHUTHU_CORS_ORIGINS`` (comma-separated; infra sets the CloudFront origin), else the Vite dev origins."""
    env = os.environ.get("EZHUTHU_CORS_ORIGINS", "")
    return [o.strip() for o in env.split(",") if o.strip()] or list(DEV_ORIGINS)


class RestoreRequest(BaseModel):
    text: str = Field(max_length=limits.MAX_TEXT_CHARS)
    script: Literal["iso15919", "tamil"] = "iso15919"
    max_candidates: int = Field(5, ge=1, le=20)
    allow_escalation: bool = True


class CorrectionRequest(BaseModel):
    gap_ref: str
    accepted_candidate: str | None = None
    corrected_text: str | None = None
    user: str | None = None


class QueueAction(BaseModel):
    action: Literal["approve", "edit", "reject"]
    text: str | None = None
    reviewer: str | None = None


class LessonRequest(BaseModel):
    inscription_id: str | None = Field(None, max_length=200)
    text: str | None = Field(None, max_length=limits.MAX_TEXT_CHARS)
    level: Literal["L1", "L2", "L3", "L4", "L5"] = "L1"
    lang: Literal["ta", "en"] = "ta"
    session_id: str | None = None


class AnswerRequest(BaseModel):
    session_id: str = Field(max_length=100)
    item_id: str = Field(max_length=100)
    answer: str = Field(max_length=500)


class EvaluateRequest(BaseModel):
    """JSON body of /api/evaluate. ``records`` are checked in the service (shared with AgentCore)."""

    model_config = ConfigDict(extra="forbid")
    benchmark: str = Field("test", max_length=40)
    limit: int | None = Field(None, ge=1)
    router: Literal[ROUTERS] = "routed"  # type: ignore[valid-type]
    records: list[Any] | None = None


class AssessmentRequest(BaseModel):
    session_id: str | None = None
    phase: Literal["pre", "post"]


def create_app(service: EzhuthuService | None = None) -> FastAPI:
    app = FastAPI(title="Ezhuthu API", version="0.1.0",
                  description="Restore and tutor API for ancient Tamil inscriptions (contracts/restore-api.md).")
    app.add_middleware(CORSMiddleware, allow_origins=cors_origins(), allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type", "Authorization", "X-Ezhuthu-Admin-Token"])
    holder: dict[str, EzhuthuService] = {}

    def svc() -> EzhuthuService:
        if "s" not in holder:
            holder["s"] = service or EzhuthuService()
        return holder["s"]

    @app.exception_handler(NotFound)
    async def _nf(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=404)

    @app.exception_handler(BadRequest)
    async def _br(_: Request, exc: BadRequest) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=422)

    @app.exception_handler(Conflict)
    async def _cf(_: Request, exc: Conflict) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=409)

    @app.exception_handler(Forbidden)
    async def _fb(_: Request, exc: Forbidden) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return svc().health()

    @app.post("/api/restore")
    def restore(req: RestoreRequest) -> dict[str, Any]:
        return svc().restore(req.text, req.script, req.max_candidates, req.allow_escalation)

    @app.post("/api/evaluate")
    async def evaluate(request: Request, admin_token: AdminToken = None) -> dict[str, Any]:
        """JSON ``{benchmark, limit, router}`` or ``{records, limit, router}``, a JSONL body (application/x-ndjson,
        ``router``/``limit`` as query parameters), or a multipart upload (field ``file``, optional form fields
        ``router`` and ``limit``). Malformed input is a 422, never a 500."""
        ctype = request.headers.get("content-type", "")
        try:
            if ctype.startswith("multipart/form-data"):
                form = await request.form()
                upload = form.get("file")
                if upload is None or isinstance(upload, str):
                    raise BadRequest("multipart upload needs a 'file' field")
                params = {"router": form.get("router") or "routed", "limit": form.get("limit") or None,
                          "records": parse_jsonl_text((await upload.read()).decode("utf-8"))}
            elif "ndjson" in ctype or "jsonl" in ctype:
                q = request.query_params
                params = {"router": q.get("router", "routed"), "limit": q.get("limit"),
                          "records": parse_jsonl_text((await request.body()).decode("utf-8"))}
            else:
                params = json.loads((await request.body()).decode("utf-8") or "{}")
                if not isinstance(params, dict):
                    raise BadRequest("expected a JSON object")
            req = EvaluateRequest.model_validate(params)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(x) for x in first.get("loc", ()))
            raise BadRequest(f"bad evaluate request: {loc}: {first.get('msg')}") from exc
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise BadRequest(f"bad evaluate request: {exc}") from exc
        return svc().evaluate(benchmark=req.benchmark, limit=req.limit, router=req.router, records=req.records,
                              admin_token=admin_token)

    @app.post("/api/corrections")
    def corrections(req: CorrectionRequest) -> dict[str, Any]:
        return svc().add_correction(req.gap_ref, accepted_candidate=req.accepted_candidate,
                                    corrected_text=req.corrected_text, user=req.user)

    @app.get("/api/queue")
    def queue() -> dict[str, Any]:
        return svc().queue()

    @app.post("/api/queue/{qid}")
    def review(qid: str, req: QueueAction, admin_token: AdminToken = None) -> dict[str, Any]:
        return svc().review(qid, req.action, req.text, req.reviewer, admin_token=admin_token)

    @app.post("/api/lesson")
    def lesson(req: LessonRequest) -> dict[str, Any]:
        return svc().lesson(**req.model_dump())

    @app.post("/api/answer")
    def answer(req: AnswerRequest) -> dict[str, Any]:
        return svc().answer(req.session_id, req.item_id, req.answer)

    @app.post("/api/assessment")
    def assessment(req: AssessmentRequest) -> dict[str, Any]:
        return svc().assessment(req.session_id, req.phase)

    @app.get("/api/progress/{session_id}")
    def progress(session_id: str) -> dict[str, Any]:
        return svc().progress(session_id)

    return app


app = create_app()
