"""LLM access through Strands Agents on Amazon Bedrock, with caching and a usage ledger.

Live calls need ``EZHUTHU_LIVE=1``. Responses are cached under ``.cache/llm/`` keyed by
(model id, system prompt, prompt), so re-running an eval does not re-bill.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
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


@dataclass
class LLMResponse:
    text: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    cached: bool = False
    latency_ms: float = 0.0


@dataclass
class UsageLedger:
    calls: int = 0
    cached_calls: int = 0
    input_tokens: dict[str, int] = field(default_factory=dict)
    output_tokens: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def add(self, short: str, r: LLMResponse) -> None:
        with self._lock:
            if r.cached:
                self.cached_calls += 1
                return
            self.calls += 1
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
            d = {"calls": self.calls, "cached_calls": self.cached_calls,
                 "input_tokens": dict(self.input_tokens), "output_tokens": dict(self.output_tokens)}
        d["estimated_cost_usd"] = self.estimated_cost_usd()
        d["price_basis"] = "USD/MTok list prices in ezhuthu.agent.llm.PRICE_PER_MTOK"
        return d


class LLMClient(Protocol):
    config: ModelsConfig
    ledger: UsageLedger

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024) -> LLMResponse: ...


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
                 temperature: float = 0.2):
        self.config = config or load_models_config()
        self.ledger = UsageLedger()
        self.cache = _Cache(default_cache_dir() if cache_dir == "default" else (Path(cache_dir) if cache_dir else None))
        self.temperature = temperature
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

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024) -> LLMResponse:
        model_id = self.config.model_id(role)
        key = self.cache.key(model_id, system, prompt, max_tokens)
        hit = self.cache.get(key)
        if hit:
            self.ledger.add(short_name(model_id), hit)
            return hit
        if not live_enabled():
            raise LiveCallsDisabled(f"Bedrock call to {model_id} needs EZHUTHU_LIVE=1")
        from strands import Agent
        from strands.models import BedrockModel

        model = BedrockModel(model_id=model_id, boto_session=self._boto_session(),
                             temperature=self.temperature, max_tokens=max_tokens)
        agent = Agent(model=model, system_prompt=system, callback_handler=None)
        t0 = time.perf_counter()
        result = agent(prompt)
        usage = result.metrics.accumulated_usage
        r = LLMResponse(
            text=str(result).strip(), model_id=model_id,
            input_tokens=int(usage.get("inputTokens", 0)), output_tokens=int(usage.get("outputTokens", 0)),
            latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        )
        self.cache.put(key, r)
        self.ledger.add(short_name(model_id), r)
        return r


class FakeLLM:
    """Deterministic LLM for tests: ``responder(role, system, prompt) -> text``."""

    def __init__(self, responder: Callable[[str, str, str], str], config: ModelsConfig | None = None):
        self.responder = responder
        self.config = config or load_models_config()
        self.ledger = UsageLedger()
        self.calls: list[tuple[str, str]] = []

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024) -> LLMResponse:
        self.calls.append((role, prompt))
        model_id = self.config.model_id(role)
        r = LLMResponse(self.responder(role, system, prompt), model_id, len(prompt) // 4, 50)
        self.ledger.add(short_name(model_id), r)
        return r


def default_llm() -> LLMClient | None:
    """Bedrock when live calls are enabled, else None (retrieval/n-gram/ontology candidates only)."""
    return BedrockLLM() if live_enabled() else None
