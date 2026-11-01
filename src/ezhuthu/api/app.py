"""FastAPI app implementing contracts/restore-api.md.

    uvicorn ezhuthu.api.app:app --port 8080
"""

from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..agent.data import parse_jsonl_text
from .service import BadRequest, EzhuthuService, NotFound


class RestoreRequest(BaseModel):
    text: str
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
    inscription_id: str | None = None
    text: str | None = None
    level: Literal["L1", "L2", "L3", "L4", "L5"] = "L1"
    lang: Literal["ta", "en"] = "ta"
    session_id: str | None = None


class AnswerRequest(BaseModel):
    session_id: str
    item_id: str
    answer: str


class AssessmentRequest(BaseModel):
    session_id: str | None = None
    phase: Literal["pre", "post"]


def create_app(service: EzhuthuService | None = None) -> FastAPI:
    app = FastAPI(title="Ezhuthu API", version="0.1.0",
                  description="Restore and tutor API for ancient Tamil inscriptions (contracts/restore-api.md).")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
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

    @app.get("/health")
    def health() -> dict[str, Any]:
        return svc().health()

    @app.post("/api/restore")
    def restore(req: RestoreRequest) -> dict[str, Any]:
        return svc().restore(req.text, req.script, req.max_candidates, req.allow_escalation)

    @app.post("/api/evaluate")
    async def evaluate(request: Request) -> dict[str, Any]:
        """JSON ``{benchmark, limit, router}``, a JSONL body (application/x-ndjson), or a multipart upload
        (field ``file``, optional form fields ``router`` and ``limit``)."""
        ctype = request.headers.get("content-type", "")
        try:
            if ctype.startswith("multipart/form-data"):
                form = await request.form()
                upload = form.get("file")
                if upload is None or isinstance(upload, str):
                    raise BadRequest("multipart upload needs a 'file' field")
                records = parse_jsonl_text((await upload.read()).decode("utf-8"))
                limit = int(form["limit"]) if form.get("limit") else None
                return svc().evaluate(records=records, limit=limit, router=str(form.get("router") or "routed"))
            body = (await request.body()).decode("utf-8")
            if "ndjson" in ctype or "jsonl" in ctype:
                params = request.query_params
                return svc().evaluate(records=parse_jsonl_text(body), router=params.get("router", "routed"),
                                      limit=int(params["limit"]) if params.get("limit") else None)
            data = json.loads(body or "{}")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            if isinstance(exc, BadRequest):
                raise
            raise HTTPException(422, f"bad evaluate request: {exc}") from exc
        if not isinstance(data, dict):
            raise HTTPException(422, "expected a JSON object")
        if "records" in data:
            return svc().evaluate(records=data["records"], limit=data.get("limit"),
                                  router=data.get("router", "routed"))
        return svc().evaluate(benchmark=data.get("benchmark", "test"), limit=data.get("limit"),
                              router=data.get("router", "routed"))

    @app.post("/api/corrections")
    def corrections(req: CorrectionRequest) -> dict[str, Any]:
        return svc().add_correction(req.gap_ref, accepted_candidate=req.accepted_candidate,
                                    corrected_text=req.corrected_text, user=req.user)

    @app.get("/api/queue")
    def queue() -> dict[str, Any]:
        return svc().queue()

    @app.post("/api/queue/{qid}")
    def review(qid: str, req: QueueAction) -> dict[str, Any]:
        return svc().review(qid, req.action, req.text, req.reviewer)

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
