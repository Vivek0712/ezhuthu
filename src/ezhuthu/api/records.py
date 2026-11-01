"""Validation of uploaded benchmark-item records (contracts/benchmark-item.schema.json) for /api/evaluate."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from ..agent.tutor.service import BadRequest
from . import limits


class BenchmarkRecord(BaseModel):
    """The fields the evaluator reads, typed and bounded; other schema fields pass through."""

    model_config = ConfigDict(extra="allow", strict=False)

    id: str = Field(min_length=1, max_length=200)
    inscription_id: str = Field(min_length=1, max_length=200)
    collection: str = Field("", max_length=200)
    split: str = Field("test", max_length=20)
    line_n: str = Field("", max_length=50)
    left: str = Field(max_length=limits.MAX_TEXT_CHARS)
    right: str = Field(max_length=limits.MAX_TEXT_CHARS)
    target: str = Field(max_length=limits.MAX_TEXT_CHARS)
    gap_chars: int = Field(ge=1, le=limits.MAX_GAP_CHARS)
    hard: bool = False
    age_set: bool = False
    source_url: str = Field("", max_length=500)
    dynasty: str | None = Field(None, max_length=100)
    kind: str = Field("supplied", max_length=20)


_RECORDS = TypeAdapter(list[BenchmarkRecord])


def _short(exc: ValidationError) -> str:
    errs = exc.errors()
    first = errs[0]
    where = ".".join(str(x) for x in first.get("loc", ()))
    return f"{len(errs)} error(s); first at {where or 'records'}: {first.get('msg')}"


def parse_records(records: Any) -> list[dict[str, Any]]:
    """Validated records as plain dicts (``line_n`` coerced to str), or BadRequest."""
    if not isinstance(records, list):
        raise BadRequest("records must be a list of benchmark-item objects")
    if len(records) > limits.MAX_EVAL_ITEMS:
        raise BadRequest(f"at most {limits.MAX_EVAL_ITEMS} records per request")
    norm = [{**r, "line_n": str(r["line_n"])} if isinstance(r, dict) and isinstance(r.get("line_n"), int) else r
            for r in records]
    try:
        return [r.model_dump() for r in _RECORDS.validate_python(norm)]
    except ValidationError as exc:
        raise BadRequest(f"records do not match contracts/benchmark-item.schema.json: {_short(exc)}") from exc
