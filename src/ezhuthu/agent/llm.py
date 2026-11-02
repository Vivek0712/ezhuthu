"""LLM access through Strands Agents on Amazon Bedrock, with caching and a usage ledger.

Live calls need ``EZHUTHU_LIVE=1``. Responses are cached under ``.cache/llm/`` keyed by
(model id, system prompt, prompt), so re-running an eval does not re-bill.

Robustness (issue #22):

* **Truncation.** A reply cut at ``max_tokens`` no longer raises: ``complete`` returns the partial text with
  ``truncated=True`` (Strands puts the partial message in ``agent.messages``) so callers can parse what arrived
  and decide whether to retry.
* **Throttling.** Strands' own retry (fixed doubling, no jitter, so parallel workers retry in lockstep) is
  turned off; ``complete`` retries throttling/transient errors with exponential backoff and full jitter, and a
  process-wide ``RateLimiter`` paces calls (``EZHUTHU_LLM_RPM``, default unlimited; eval runs set it).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from .config import ModelsConfig, live_enabled, load_models_config, repo_root

log = logging.getLogger(__name__)

# USD per million tokens, Anthropic list prices for on-demand Bedrock in us-east-1 (checked 2026-11-02).
# Used only to *estimate* eval cost in reports; the bill is the source of truth.
PRICE_PER_MTOK = {
    "sonnet": (3.0, 15.0),
    "opus": (5.0, 25.0),
    "haiku": (1.0, 5.0),
}


class LiveCallsDisabled(RuntimeError):
    """Raised when a Bedrock call is attempted without EZHUTHU_LIVE=1."""


# Error class names / codes that mean "slow down and try again" (Strands, botocore, Bedrock runtime).
RETRYABLE_NAMES = ("ModelThrottledException", "ThrottlingException", "TooManyRequestsException",
                   "ServiceUnavailableException", "ModelNotReadyException", "InternalServerException",
                   "ReadTimeoutError", "ConnectTimeoutError", "EndpointConnectionError")


def is_retryable(exc: BaseException) -> bool:
    """Throttling or a transient service fault (never a validation/auth error or a truncation)."""
    names = {type(e).__name__ for e in (exc, exc.__cause__, exc.__context__) if e is not None}
    code = ""
    resp = getattr(exc, "response", None)
    if isinstance(resp, dict):
        code = str(resp.get("Error", {}).get("Code", ""))
    text = str(exc)
    return bool(names.intersection(RETRYABLE_NAMES)) or code in RETRYABLE_NAMES \
        or "Too many requests" in text or "ThrottlingException" in text


def backoff_delays(attempts: int, *, base: float = 2.0, cap: float = 30.0,
                   rng: random.Random | None = None) -> list[float]:
    """Full-jitter exponential backoff (AWS architecture blog): ``uniform(0, min(cap, base * 2**i))``."""
    r = rng or random
    return [r.uniform(0, min(cap, base * 2 ** i)) for i in range(max(0, attempts - 1))]


def call_with_retries(fn: Callable[[], LLMResponse], *, attempts: int = 5, base: float = 2.0, cap: float = 30.0,
                      sleep: Callable[[float], None] = time.sleep, rng: random.Random | None = None,
                      retryable: Callable[[BaseException], bool] = is_retryable, deadline: float | None = None,
                      clock: Callable[[], float] = time.monotonic, min_attempt_s: float = 0.0) -> LLMResponse:
    """Retry ``fn`` on throttling with jittered backoff. With ``deadline`` (a ``clock()`` time), a back-off that would
    end less than ``min_attempt_s`` before the deadline is not taken: the last error is raised instead, so a
    request-scoped caller (the Reader inside the proxy's 27 s) never sleeps past its budget."""
    delays = backoff_delays(attempts, base=base, cap=cap, rng=rng)
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:
            if i >= attempts - 1 or not retryable(exc):
                raise
            if deadline is not None and clock() + delays[i] + min_attempt_s > deadline:
                log.warning("LLM call %s (attempt %d/%d); no time left for a retry", type(exc).__name__, i + 1,
                            attempts)
                raise
            log.warning("LLM call %s (attempt %d/%d); retrying in %.1fs", type(exc).__name__, i + 1, attempts,
                        delays[i])
            sleep(delays[i])
    raise RuntimeError("unreachable")  # pragma: no cover


class RateLimiter:
    """Thread-safe pacing to at most ``rpm`` calls a minute (evenly spaced). ``rpm`` falsy = no limit."""

    def __init__(self, rpm: float | None, *, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.interval = 60.0 / rpm if rpm else 0.0
        self._clock, self._sleep = clock, sleep
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> float:
        if not self.interval:
            return 0.0
        with self._lock:
            now = self._clock()
            wait = max(0.0, self._next - now)
            self._next = max(now, self._next) + self.interval
        if wait:
            self._sleep(wait)
        return wait


def env_rpm() -> float | None:
    v = os.environ.get("EZHUTHU_LLM_RPM")
    try:
        return float(v) if v else None
    except ValueError:
        return None


@dataclass
class LLMResponse:
    text: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    latency_ms: float = 0.0
    truncated: bool = False  # stopped at max_tokens; ``text`` is the partial output
    attempts: int = 1


@dataclass
class UsageLedger:
    calls: int = 0
    cached_calls: int = 0
    input_tokens: dict[str, int] = field(default_factory=dict)
    output_tokens: dict[str, int] = field(default_factory=dict)
    calls_by_model: dict[str, int] = field(default_factory=dict)  # live calls per short model name
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, short: str, r: LLMResponse) -> None:
        with self._lock:
            if r.cached:
                self.cached_calls += 1
                return
            self.calls += 1
            self.calls_by_model[short] = self.calls_by_model.get(short, 0) + 1
            self.input_tokens[short] = self.input_tokens.get(short, 0) + r.input_tokens
            self.output_tokens[short] = self.output_tokens.get(short, 0) + r.output_tokens

    def estimated_cost_usd(self) -> float:
        total = 0.0
        for short, (pin, pout) in PRICE_PER_MTOK.items():
            total += self.input_tokens.get(short, 0) / 1e6 * pin + self.output_tokens.get(short, 0) / 1e6 * pout
        return round(total, 4)

    def to_dict(self) -> dict:
        # Not dataclasses.asdict: it deep-copies the lock and raises "cannot pickle '_thread.lock'".
        with self._lock:
            d = {"calls": self.calls, "calls_by_model": dict(self.calls_by_model), "cached_calls": self.cached_calls,
                 "input_tokens": dict(self.input_tokens), "output_tokens": dict(self.output_tokens)}
        d["estimated_cost_usd"] = self.estimated_cost_usd()
        d["price_basis"] = "USD/MTok list prices in ezhuthu.agent.llm.PRICE_PER_MTOK"
        return d


class LLMClient(Protocol):
    config: ModelsConfig
    ledger: UsageLedger

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024,
                 timeout_s: float | None = None) -> LLMResponse: ...


Images = list[tuple[bytes, str]]  # (bytes, Bedrock image format: jpeg|png|webp|gif)


def images_digest(images: Images) -> str:
    """Cache-key part for image prompts: a hash of the bytes (never the bytes or any metadata)."""
    h = hashlib.sha256()
    for data, fmt in images:
        h.update(fmt.encode())
        h.update(hashlib.sha256(data).digest())
    return "images:" + h.hexdigest()


def short_name(model_id: str) -> str:
    for s in ("sonnet", "opus", "haiku"):
        if s in model_id:
            return s
    return model_id


class _Cache:
    def __init__(self, root: Path | None):
        self.root = root

    def key(self, model_id: str, system: str, prompt: str, max_tokens: int) -> str:
        h = hashlib.sha256(json.dumps([model_id, system, prompt, max_tokens], ensure_ascii=False).encode())
        return h.hexdigest()

    def get(self, key: str) -> LLMResponse | None:
        if not self.root:
            return None
        p = self.root / key[:2] / f"{key}.json"
        if p.is_file():
            d = json.loads(p.read_text(encoding="utf-8"))
            return LLMResponse(**{**d, "cached": True})
        return None

    def put(self, key: str, r: LLMResponse) -> None:
        if not self.root:
            return
        p = self.root / key[:2] / f"{key}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({**asdict(r), "cached": False}, ensure_ascii=False), encoding="utf-8")


def default_cache_dir() -> Path | None:
    if os.environ.get("EZHUTHU_NO_CACHE") == "1":
        return None
    env = os.environ.get("EZHUTHU_CACHE_DIR")
    if env:
        return Path(env) / "llm"
    root = repo_root()
    return (root / ".cache" / "llm") if root else None


class BedrockLLM:
    """One fresh Strands ``Agent`` per call (no history), on ``BedrockModel``."""

    def __init__(self, config: ModelsConfig | None = None, *, cache_dir: Path | None | str = "default",
                 temperature: float = 0.2, rpm: float | None | str = "env", retry_attempts: int = 5,
                 retry_base: float = 2.0, retry_cap: float = 30.0, sleep: Callable[[float], None] = time.sleep):
        self.config = config or load_models_config()
        self.ledger = UsageLedger()
        self.cache = _Cache(default_cache_dir() if cache_dir == "default" else (Path(cache_dir) if cache_dir else None))
        self.temperature = temperature
        self.limiter = RateLimiter(env_rpm() if rpm == "env" else rpm, sleep=sleep)  # type: ignore[arg-type]
        self.retry_attempts, self.retry_base, self.retry_cap = retry_attempts, retry_base, retry_cap
        self._sleep = sleep
        self._session = None

    def _boto_session(self):
        import boto3
        from botocore.exceptions import ProfileNotFound

        if self._session is None:
            try:
                self._session = boto3.Session(profile_name=self.config.aws_profile, region_name=self.config.region)
            except ProfileNotFound:  # AgentCore runtime / CI: use the execution role
                self._session = boto3.Session(region_name=self.config.region)
        return self._session

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024,
                 timeout_s: float | None = None) -> LLMResponse:
        """Text call. ``timeout_s`` bounds the whole call like :meth:`complete_image` (the restorer's request budget,
        issue #41); without it the call is unbounded, as before."""
        model_id = self.config.model_id(role)
        deadline = time.monotonic() + timeout_s if timeout_s is not None else None
        key = self.cache.key(model_id, system, prompt, max_tokens)
        hit = self.cache.get(key)
        if hit:
            self.ledger.add(short_name(model_id), hit)
            return hit
        if not live_enabled():
            raise LiveCallsDisabled(f"Bedrock call to {model_id} needs EZHUTHU_LIVE=1")
        attempts = {"n": 0}

        def once() -> LLMResponse:
            attempts["n"] += 1
            self.limiter.acquire()
            if deadline is None:
                return self._invoke(model_id, system, prompt, max_tokens)
            return self._invoke(model_id, system, prompt, max_tokens,
                                read_timeout=max(1.0, deadline - time.monotonic()))

        r = call_with_retries(once, attempts=self.retry_attempts, base=self.retry_base, cap=self.retry_cap,
                              sleep=self._sleep, deadline=deadline, min_attempt_s=3.0 if deadline else 0.0)
        r.attempts = attempts["n"]
        self.cache.put(key, r)
        self.ledger.add(short_name(model_id), r)
        return r

    def complete_image(self, role: str, system: str, prompt: str, images: Images, *,
                       max_tokens: int = 1024, timeout_s: float | None = None) -> LLMResponse:
        """Vision call (Bedrock Converse image blocks). Cached by model, prompt and a hash of the image bytes.

        ``timeout_s`` bounds the whole call (retries and back-off included): retries stop when they would not fit,
        and the HTTP read timeout is cut to what is left, so a request-scoped caller gets an error in time instead
        of a reply nobody is waiting for."""
        model_id = self.config.model_id(role)
        deadline = time.monotonic() + timeout_s if timeout_s is not None else None
        key = self.cache.key(model_id, system, prompt + "\n" + images_digest(images), max_tokens)
        hit = self.cache.get(key)
        if hit:
            self.ledger.add(short_name(model_id), hit)
            return hit
        if not live_enabled():
            raise LiveCallsDisabled(f"Bedrock call to {model_id} needs EZHUTHU_LIVE=1")
        attempts = {"n": 0}
        content = [{"text": prompt}, *({"image": {"format": fmt, "source": {"bytes": data}}} for data, fmt in images)]

        def once() -> LLMResponse:
            attempts["n"] += 1
            self.limiter.acquire()
            read_timeout = None if deadline is None else max(1.0, deadline - time.monotonic())
            return self._invoke(model_id, system, content, max_tokens,  # type: ignore[arg-type]
                                read_timeout=read_timeout)

        r = call_with_retries(once, attempts=self.retry_attempts, base=self.retry_base, cap=self.retry_cap,
                              sleep=self._sleep, deadline=deadline, min_attempt_s=3.0)
        r.attempts = attempts["n"]
        self.cache.put(key, r)
        self.ledger.add(short_name(model_id), r)
        return r

    def _model(self, model_id: str, max_tokens: int, read_timeout: float | None = None):
        from strands.models import BedrockModel

        extra = {}
        if read_timeout is not None:
            from botocore.config import Config

            # botocore's own retries off: call_with_retries owns retrying and the deadline.
            extra["boto_client_config"] = Config(read_timeout=read_timeout, connect_timeout=min(5.0, read_timeout),
                                                 retries={"max_attempts": 1, "mode": "standard"})
        return BedrockModel(model_id=model_id, boto_session=self._boto_session(),
                            temperature=self.temperature, max_tokens=max_tokens, **extra)

    def _invoke(self, model_id: str, system: str, prompt: str | list, max_tokens: int,
                read_timeout: float | None = None) -> LLMResponse:
        from strands import Agent
        from strands.types.exceptions import MaxTokensReachedException

        model = self._model(model_id, max_tokens, read_timeout) if read_timeout is not None \
            else self._model(model_id, max_tokens)
        # retry_strategy=None: our call_with_retries (jittered) replaces Strands' lockstep doubling.
        agent = Agent(model=model, system_prompt=system, callback_handler=None, retry_strategy=None)
        t0 = time.perf_counter()
        try:
            result = agent(prompt)
            text, usage, truncated = str(result).strip(), result.metrics.accumulated_usage, False
        except MaxTokensReachedException:
            # The partial assistant message is the last entry of the conversation; keep it.
            last = agent.messages[-1] if agent.messages else {}
            text = "".join(b.get("text", "") for b in last.get("content", []) if isinstance(b, dict)) \
                if last.get("role") == "assistant" else ""
            usage, truncated = agent.event_loop_metrics.accumulated_usage, True
            log.warning("LLM reply hit max_tokens=%d (%d chars kept)", max_tokens, len(text))
        return LLMResponse(
            text=text.strip(), model_id=model_id,
            input_tokens=int(usage.get("inputTokens", 0)), output_tokens=int(usage.get("outputTokens", 0)),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1), truncated=truncated,
        )


class FakeLLM:
    """Deterministic LLM for tests: ``responder(role, system, prompt) -> text``."""

    def __init__(self, responder: Callable[[str, str, str], str], config: ModelsConfig | None = None):
        self.responder = responder
        self.config = config or load_models_config()
        self.ledger = UsageLedger()
        self.calls: list[tuple[str, str]] = []
        self.max_tokens: list[int] = []
        self.images: list[Images] = []
        self.timeouts: list[float | None] = []

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024,
                 timeout_s: float | None = None) -> LLMResponse:
        self.calls.append((role, prompt))
        self.max_tokens.append(max_tokens)
        self.timeouts.append(timeout_s)
        model_id = self.config.model_id(role)
        out = self.responder(role, system, prompt)
        # A responder may return (text, truncated) to simulate a reply cut at max_tokens.
        text, truncated = out if isinstance(out, tuple) else (out, False)
        r = LLMResponse(text, model_id, len(prompt) // 4, 50, truncated=truncated)
        self.ledger.add(short_name(model_id), r)
        return r

    def complete_image(self, role: str, system: str, prompt: str, images: Images, *,
                       max_tokens: int = 1024, timeout_s: float | None = None) -> LLMResponse:
        """Same responder; the images are recorded in ``self.images`` (tests check metadata never arrives) and the
        time budget in ``self.timeouts``."""
        self.images.append(list(images))
        return self.complete(role, system, prompt, max_tokens=max_tokens, timeout_s=timeout_s)


class BudgetedLLM:
    """Wraps an LLM client; after ``max_live`` uncached calls it raises ``LiveCallsDisabled`` (the restorer then
    uses retrieval candidates only). Cached replies never count against the budget."""

    def __init__(self, inner: BedrockLLM, max_live: int):
        self.inner, self.max_live = inner, max_live
        self.config, self.ledger = inner.config, inner.ledger
        self.exhausted = 0

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024,
                 timeout_s: float | None = None) -> LLMResponse:
        key = self.inner.cache.key(self.inner.config.model_id(role), system, prompt, max_tokens)
        if self.inner.cache.get(key) is None and self.inner.ledger.calls >= self.max_live:
            self.exhausted += 1
            raise LiveCallsDisabled(f"live-call budget of {self.max_live} reached")
        return self.inner.complete(role, system, prompt, max_tokens=max_tokens, timeout_s=timeout_s)

    def complete_image(self, role: str, system: str, prompt: str, images: Images, *,
                       max_tokens: int = 1024, timeout_s: float | None = None) -> LLMResponse:
        mid = self.inner.config.model_id(role)
        key = self.inner.cache.key(mid, system, prompt + "\n" + images_digest(images), max_tokens)
        if self.inner.cache.get(key) is None and self.inner.ledger.calls >= self.max_live:
            self.exhausted += 1
            raise LiveCallsDisabled(f"live-call budget of {self.max_live} reached")
        return self.inner.complete_image(role, system, prompt, images, max_tokens=max_tokens, timeout_s=timeout_s)


def default_llm() -> LLMClient | None:
    """Bedrock when live calls are enabled, else None (retrieval/n-gram/ontology candidates only)."""
    return BedrockLLM() if live_enabled() else None
