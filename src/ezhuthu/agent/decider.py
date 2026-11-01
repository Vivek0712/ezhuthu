"""Strands Decider clients.

Two backends speak the same question schema:

* ``local``: ``strands-decider serve`` (System One HTTP API), ``POST {base}/v1/systemone``.
* ``hosted``: the hosted Strands Decider API (decider-cloud), ``POST {url}/v1/decide`` with
  ``Authorization: Bearer <api key>``; the key comes from ``$EZHUTHU_DECIDER_API_KEY`` or AWS Secrets
  Manager (``config/models.yaml`` ``decider.cloud.secret_name``).

    {"state": ..., "questions": {"<name>": {"type": "choice", "instructions": ..., "criteria": {...}}}}
    {"state": ..., "questions": {"<name>": {"type": "noul", "instructions": ...}}}

``EZHUTHU_DECIDER_BACKEND=hosted|local|fallback`` picks one (default ``local``); ``fallback`` means no decider.
If the decider is unreachable or refuses a request, callers fall back (LLM self-reported confidence for
restoration, rules for pedagogy) and must flag the source in their output. Every answer carries the decider
``model`` and its ``source`` (``hosted`` | ``local``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

log = logging.getLogger(__name__)

DEFAULT_URL = "http://127.0.0.1:8765"
MAX_OPTIONS = 24  # num_slots of the v1-2610 checkpoints (GET /health)
BACKENDS = ("hosted", "local", "fallback")


class DeciderUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Choice:
    choice: str
    probabilities: dict[str, float]
    confidence: float  # normalised max-probability from the server
    model: str
    latency_ms: float | None = None
    source: str = "local"  # hosted | local | fake


@dataclass(frozen=True)
class Noul:
    probability: float  # P(yes)
    model: str
    latency_ms: float | None = None
    source: str = "local"


class Decider(Protocol):
    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice: ...

    def available(self) -> bool: ...


def choice_payload(state: Any, instructions: str, options: dict[str, Any], name: str) -> dict[str, Any]:
    if len(options) < 2:
        raise ValueError("choice needs at least 2 options")
    if len(options) > MAX_OPTIONS:
        raise ValueError(f"choice allows at most {MAX_OPTIONS} options")
    return {"state": state, "questions": {name: {"type": "choice", "instructions": instructions,
                                                 "criteria": options}}}


def noul_payload(state: Any, instructions: str, name: str) -> dict[str, Any]:
    return {"state": state, "questions": {name: {"type": "noul", "instructions": instructions}}}


def request_chars(payload: dict[str, Any]) -> int:
    """Size as decider-cloud's gateway counts it against ``max_input_chars`` (json.dumps, ASCII escapes)."""
    return len(json.dumps(payload.get("state", ""))) + len(json.dumps(payload["questions"]))


def fit_choice(state: Any, instructions: str, options: dict[str, Any], name: str, max_chars: int | None,
               keep: tuple[str, ...] = ("none",)) -> dict[str, Any]:
    """Drop options from the end (never those in ``keep``) until the request fits ``max_chars``.

    Callers order options best-first (the restorer puts LLM-ranked candidates first), so the tail goes.
    Dropped options get no probability (callers read them as 0). Raises ``DeciderUnavailable`` if even two
    options do not fit.
    """
    opts = dict(options)
    payload = choice_payload(state, instructions, opts, name)
    if not max_chars:
        return payload
    while request_chars(payload) > max_chars:
        droppable = [k for k in opts if k not in keep]
        if len(opts) <= 2 or not droppable:
            raise DeciderUnavailable(f"decider request is {request_chars(payload)} characters even with "
                                     f"{len(opts)} options; the limit is {max_chars}")
        opts.pop(droppable[-1])
        payload = choice_payload(state, instructions, opts, name)
    return payload


def parse_choice(out: dict[str, Any], name: str, source: str, default_model: str) -> Choice:
    ans = out["answers"][name]
    return Choice(ans["choice"], {k: float(v) for k, v in ans["probabilities"].items()},
                  float(ans["confidence"]), out.get("model", default_model), out.get("latency_ms"), source)


def parse_noul(out: dict[str, Any], name: str, source: str, default_model: str) -> Noul:
    return Noul(float(out["answers"][name]["noul"]), out.get("model", default_model), out.get("latency_ms"), source)


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
        out = self._request("/v1/systemone", choice_payload(state, instructions, options, name))
        return parse_choice(out, name, "local", "strands-decider")

    def noul(self, state: Any, instructions: str, *, name: str = "q") -> Noul:
        out = self._request("/v1/systemone", noul_payload(state, instructions, name))
        return parse_noul(out, name, "local", "strands-decider")


def _secret_api_key(secret_name: str, region: str, profile: str | None) -> str:
    """Read the API key from Secrets Manager: a JSON object with ``api_key``, or the raw key string."""
    import boto3
    from botocore.exceptions import ProfileNotFound

    try:
        session = boto3.Session(profile_name=profile, region_name=region) if profile else \
            boto3.Session(region_name=region)
    except ProfileNotFound:  # AgentCore runtime: execution role
        session = boto3.Session(region_name=region)
    raw = session.client("secretsmanager").get_secret_value(SecretId=secret_name)["SecretString"]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    return str(data["api_key"]) if isinstance(data, dict) else str(data)


class HostedDecider:
    """Hosted Strands Decider API (decider-cloud): ``POST /v1/decide`` with a bearer API key.

    Paces requests client-side to ``rpm`` (the free tier allows 10 a minute) and honours ``Retry-After``
    on 429/503 once; any other refusal (401/402/403/413/422) raises ``DeciderUnavailable`` so callers use
    their flagged fallback. The key is never logged.
    """

    def __init__(self, url: str, model: str, *, api_key: str | None = None, secret_name: str | None = None,
                 region: str = "us-east-1", profile: str | None = None, timeout: float = 30.0,
                 rpm: float | None = 10.0, max_retry_wait: float = 20.0, max_input_chars: int | None = None,
                 sleep=time.sleep):
        self.base_url = url.rstrip("/")
        self.model = model
        self.max_input_chars = max_input_chars  # tier limit (free 8000); None sends the request unchanged
        self.last_trimmed = 0
        self.timeout = timeout
        self.min_interval = 60.0 / rpm if rpm else 0.0
        self.max_retry_wait = max_retry_wait
        self._api_key = api_key
        self._secret_name, self._region, self._profile = secret_name, region, profile
        self._sleep = sleep
        self._lock = threading.Lock()
        self._next_at = 0.0
        self._health: dict[str, Any] | None = None
        self._health_checked = 0.0
        self.last_headers: dict[str, str] = {}
        self._key_failed_at = 0.0

    @property
    def api_key(self) -> str:
        if self._api_key is None:
            env = os.environ.get("EZHUTHU_DECIDER_API_KEY")
            if env:
                self._api_key = env
            elif self._secret_name:
                # A missing secret must not cost a Secrets Manager round trip on every request.
                if self._key_failed_at and time.monotonic() - self._key_failed_at < 60:
                    raise DeciderUnavailable("hosted decider key unavailable (cached failure)")
                try:
                    self._api_key = _secret_api_key(self._secret_name, self._region, self._profile)
                except Exception as exc:  # any AWS/auth error means "no hosted decider"
                    self._key_failed_at = time.monotonic()
                    raise DeciderUnavailable(f"hosted decider key unavailable ({type(exc).__name__})") from exc
            else:
                raise DeciderUnavailable("hosted decider needs EZHUTHU_DECIDER_API_KEY or decider.cloud.secret_name")
        return self._api_key

    def _pace(self) -> None:
        if not self.min_interval:
            return
        with self._lock:
            now = time.monotonic()
            wait = self._next_at - now
            self._next_at = max(now, self._next_at) + self.min_interval
        if wait > 0:
            self._sleep(wait)

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, *,
                 timeout: float | None = None, pace: bool = True) -> Any:
        data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
        headers = {"authorization": f"Bearer {self.api_key}"}
        if data is not None:
            headers["content-type"] = "application/json"
        for attempt in range(2):
            if pace:
                self._pace()
            req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=timeout or self.timeout) as resp:
                    self.last_headers = {k.lower(): v for k, v in resp.headers.items()
                                         if k.lower().startswith("x-")}
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(errors="replace")[:300]
                try:
                    code = json.loads(body).get("error", {}).get("code", "")
                except (json.JSONDecodeError, AttributeError):
                    code = ""
                retry_after = exc.headers.get("retry-after") if exc.headers else None
                if exc.code in (429, 503) and attempt == 0:
                    wait = min(self.max_retry_wait, float(retry_after or 5))
                    log.warning("hosted decider %s %s (%s); retrying in %.1fs", path, exc.code, code, wait)
                    self._sleep(wait)
                    continue
                log.warning("hosted decider %s returned %s %s", path, exc.code, code)
                raise DeciderUnavailable(f"hosted decider refused request ({exc.code} {code})") from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                raise DeciderUnavailable(f"hosted decider at {self.base_url} unavailable: {exc}") from exc
        raise DeciderUnavailable("hosted decider: retry budget exhausted")  # pragma: no cover

    def health(self) -> dict[str, Any] | None:
        """``GET /v1/models``; healthy when the configured model is listed and ready (re-probed every 60 s)."""
        if self._health_checked and time.monotonic() - self._health_checked < 60:
            return self._health
        self._health_checked = time.monotonic()
        try:
            out = self._request("GET", "/v1/models", timeout=5.0, pace=False)
            m = next((d for d in out.get("data", []) if d.get("id") == self.model), None)
            self._health = {"status": "ok", "model": self.model, "source": "hosted",
                            "url": self.base_url} if m and m.get("ready", True) else None
        except DeciderUnavailable:
            self._health = None
        return self._health

    def available(self) -> bool:
        return self.health() is not None

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        payload = fit_choice(state, instructions, options, name, self.max_input_chars)
        self.last_trimmed = len(options) - len(payload["questions"][name]["criteria"])
        if self.last_trimmed:
            log.info("hosted decider: dropped %d tail options to fit %s characters", self.last_trimmed,
                     self.max_input_chars)
        return parse_choice(self._request("POST", "/v1/decide", {**payload, "model": self.model}), name, "hosted",
                            self.model)

    def noul(self, state: Any, instructions: str, *, name: str = "q") -> Noul:
        payload = {**noul_payload(state, instructions, name), "model": self.model}
        return parse_noul(self._request("POST", "/v1/decide", payload), name, "hosted", self.model)


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
        return Choice(best, probs, conf, self.model, source="fake")


class NoDecider:
    def available(self) -> bool:
        return False

    def health(self) -> None:
        return None

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        raise DeciderUnavailable("no decider configured")

    def noul(self, state: Any, instructions: str, *, name: str = "q") -> Noul:
        raise DeciderUnavailable("no decider configured")


def decider_backend() -> str:
    b = (os.environ.get("EZHUTHU_DECIDER_BACKEND") or "local").strip().lower()
    if b not in BACKENDS:
        raise ValueError(f"EZHUTHU_DECIDER_BACKEND must be one of {BACKENDS}, got {b!r}")
    return b


def hosted_decider(config: Any = None, **kw: Any) -> HostedDecider:
    """HostedDecider from ``config/models.yaml`` ``decider.cloud`` (url, model, secret_name, rpm)."""
    if config is None:
        from .config import load_models_config

        config = load_models_config()
    cloud = dict((config.decider or {}).get("cloud") or {})
    missing = [k for k in ("url", "model") if not cloud.get(k)]
    if missing:
        raise ValueError(f"config/models.yaml decider.cloud is missing {missing}")
    url = os.environ.get("EZHUTHU_DECIDER_CLOUD_URL") or cloud["url"]
    return HostedDecider(url, cloud["model"], secret_name=cloud.get("secret_name"), region=config.region,
                         profile=config.aws_profile, rpm=cloud.get("rpm", 10),
                         max_input_chars=cloud.get("max_input_chars"), **kw)


def default_decider(backend: str | None = None) -> Decider:
    if os.environ.get("EZHUTHU_DECIDER") == "off":
        return NoDecider()
    b = backend or decider_backend()
    if b == "fallback":
        return NoDecider()
    if b == "hosted":
        return hosted_decider()
    return HttpDecider()
