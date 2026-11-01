"""Request limits and input checks shared by the FastAPI app and the AgentCore entrypoint.

The API is reachable without sign-in (learners), so every request is bounded in size and in the Bedrock
calls it can trigger:

- text: at most ``MAX_TEXT_CHARS`` characters, ISO-15919 (or Tamil script) letters and inscription punctuation
  only, so prose such as URLs or code cannot be smuggled into the tutor prompt;
- gaps: at most ``MAX_GAPS`` per request, each ``[?N]`` with 1 <= N <= ``MAX_GAP_CHARS`` (each gap costs up
  to two LLM calls, and the n-gram beam costs about 1 ms per gap character);
- evaluate: LLM routers need the admin token and at most ``MAX_LIVE_EVAL_ITEMS`` items; offline routers at
  most ``MAX_EVAL_ITEMS``.

Every limit can be overridden with the matching ``EZHUTHU_*`` environment variable.
"""

from __future__ import annotations

import hmac
import os

from ..agent.text import GAP_RE, looks_tamil, non_iso_chars, tamil_to_iso
from ..agent.tutor.service import BadRequest


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


MAX_TEXT_CHARS = _env_int("EZHUTHU_MAX_TEXT_CHARS", 2000)
MAX_GAPS = _env_int("EZHUTHU_MAX_GAPS", 5)
MAX_GAP_CHARS = _env_int("EZHUTHU_MAX_GAP_CHARS", 60)
MAX_EVAL_ITEMS = _env_int("EZHUTHU_MAX_EVAL_ITEMS", 500)
MAX_LIVE_EVAL_ITEMS = _env_int("EZHUTHU_MAX_LIVE_EVAL_ITEMS", 20)
MAX_CORRECTION_CHARS = 500

# Editorial marks that appear in DHARMA ISO text (sandhi '=', apostrophes, middle dots).
INSCRIPTION_PUNCT = "=’‘·[]?"


class Forbidden(PermissionError):
    """The request needs the admin/reviewer token."""


def check_text(text: str | None, *, script: str = "iso15919", field: str = "text") -> str:
    """Validate learner- or user-supplied inscription text; returns it unchanged. Raises BadRequest."""
    if text is None or not text.strip():
        raise BadRequest(f"{field} is empty")
    if len(text) > MAX_TEXT_CHARS:
        raise BadRequest(f"{field} is {len(text)} characters; the limit is {MAX_TEXT_CHARS}")
    markers = list(GAP_RE.finditer(text))
    if len(markers) > MAX_GAPS:
        raise BadRequest(f"{field} has {len(markers)} gaps; the limit is {MAX_GAPS} per request")
    for m in markers:
        if m.group(1):
            n = int(m.group(1))
            if not 1 <= n <= MAX_GAP_CHARS:
                raise BadRequest(f"gap {m.group(0)}: N must be 1..{MAX_GAP_CHARS} (use [?] for unknown length)")
    if "[?" in GAP_RE.sub("", text):
        raise BadRequest(f"{field} has a malformed gap marker; use [?] or [?N]")
    body = GAP_RE.sub(" ", text)
    iso = tamil_to_iso(body) if (script == "tamil" or looks_tamil(body)) else body
    bad = non_iso_chars(iso, extra_allowed=INSCRIPTION_PUNCT)
    if bad:
        shown = "".join(sorted(bad))[:20]
        raise BadRequest(f"{field} must be ISO-15919 or Tamil script; unsupported characters: {shown!r}")
    return text


def check_token(given: str | None, expected: str | None) -> bool:
    return bool(given) and bool(expected) and hmac.compare_digest(str(given), str(expected))
