"""Strands Decider client: the System One HTTP API served by ``strands-decider serve``.

    POST {base}/v1/systemone
    {"state": ..., "questions": {"<name>": {"type": "choice", "instructions": ..., "criteria": {...}}}}

If the server is unreachable, callers fall back (LLM self-reported confidence for restoration,
rules for pedagogy) and must flag the source in their output.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:8765"
MAX_OPTIONS = 24  # num_slots of the v1-2610 checkpoints (GET /health)


class DeciderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Choice:
    choice: str
    probabilities: dict[str, float]
    confidence: float  # normalised max-probability from the server
    model: str
    latency_ms: float | None = None


class Decider(Protocol):
    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice: ...

    def available(self) -> bool: ...


class HttpDecider:
    def __init__(self, base_url: str | None = None, *, timeout: float = 30.0):
        self.base_url = (base_url or os.environ.get("EZHUTHU_DECIDER_URL") or DEFAULT_URL).rstrip("/")
        self.timeout = timeout
        self._health: dict[str, Any] | None = None
        self._health_checked = 0.0

    def _request(self, path: str, payload: dict[str, Any] | None = None, timeout: float | None = None) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data,
                                     headers={"content-type": "application/json"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:  # server is up but refused the request (e.g. 422)
            detail = exc.read().decode(errors="replace")[:300]
            log.warning("decider %s returned %s: %s", path, exc.code, detail)
            raise DeciderUnavailable(f"decider refused request ({exc.code}): {detail}") from exc
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise DeciderUnavailable(f"decider at {self.base_url} unavailable: {exc}") from exc

    def health(self) -> dict[str, Any] | None:
        # Re-probe at most every 30 s so a stopped server does not add latency to every request.
        if time.monotonic() - self._health_checked < 30 and self._health_checked:
            return self._health
        self._health_checked = time.monotonic()
        try:
            self._health = self._request("/health", timeout=2.0)
        except DeciderUnavailable:
            self._health = None
        return self._health

    def available(self) -> bool:
        return self.health() is not None

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        if len(options) < 2:
            raise ValueError("choice needs at least 2 options")
        if len(options) > MAX_OPTIONS:
            raise ValueError(f"choice allows at most {MAX_OPTIONS} options")
        payload = {"state": state, "questions": {name: {"type": "choice", "instructions": instructions,
                                                        "criteria": options}}}
        out = self._request("/v1/systemone", payload)
        ans = out["answers"][name]
        return Choice(ans["choice"], {k: float(v) for k, v in ans["probabilities"].items()},
                      float(ans["confidence"]), out.get("model", "strands-decider"), out.get("latency_ms"))


class FakeDecider:
    """Test double: ``picker(state, options) -> {option: prob}``."""

    def __init__(self, picker, model: str = "fake-decider"):
        self.picker = picker
        self.model = model
        self.calls: list[dict[str, Any]] = []

    def available(self) -> bool:
        return True

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        self.calls.append({"state": state, "instructions": instructions, "options": options})
        probs = self.picker(state, options)
        best = max(probs, key=probs.get)
        n = len(probs)
        conf = max(0.0, (n * probs[best] - 1) / (n - 1)) if n > 1 else 1.0
        return Choice(best, probs, conf, self.model)


class NoDecider:
    def available(self) -> bool:
        return False

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        raise DeciderUnavailable("no decider configured")


def default_decider() -> Decider:
    if os.environ.get("EZHUTHU_DECIDER") == "off":
        return NoDecider()
    return HttpDecider()
