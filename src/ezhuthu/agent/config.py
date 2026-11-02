"""Model and routing configuration. Model IDs come ONLY from config/models.yaml."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = PACKAGE_DIR / "fixtures"


def repo_root() -> Path | None:
    """The checkout root (has config/models.yaml), if running from a source tree."""
    for base in (Path.cwd(), *PACKAGE_DIR.parents):
        if (base / "config" / "models.yaml").is_file():
            return base
    return None


def find_models_yaml() -> Path:
    env = os.environ.get("EZHUTHU_CONFIG")
    if env:
        return Path(env)
    root = repo_root()
    if root is None:
        raise FileNotFoundError(
            "config/models.yaml not found; set EZHUTHU_CONFIG or run from the repo root "
            "(AgentCore bundles must ship config/models.yaml)"
        )
    return root / "config" / "models.yaml"


@dataclass(frozen=True)
class Routing:
    escalate_if_confidence_below: float = 0.6
    escalate_if_gap_chars_over: int = 12
    escalate_if_no_parallel: bool = True
    abstain_if_confidence_below: float = 0.5


DECIDER_STRATEGIES = ("choice-all", "choice-topk", "noul-topk", "prerank", "self-report")


@dataclass(frozen=True)
class RestorerSettings:
    """``config/models.yaml`` ``restorer:`` (issue #22). Every field can be overridden per eval run.

    ``strategy``: how candidates get their confidence.
      * ``choice-all``: one decider ``choice`` over up to 23 candidates + ``none`` (the pre-#22 behaviour).
      * ``choice-topk``: a cheap pre-rank (LLM probability + parallel support), then ``choice`` over the top
        ``top_k`` + ``none``; the copy-baseline fill always gets one of the ``top_k`` slots.
      * ``noul-topk``: the same top ``top_k``, one ``noul`` per candidate ("is this the restoration?").
      * ``prerank``: no decider; the pre-rank score is the confidence.
      * ``self-report``: no decider; LLM fills keep the LLM's own probability, retrieval-only candidates get the
        parallel-agreement heuristic (the decider-unavailable fallback, and main's behaviour without a decider).
    ``strategy_llm``: the strategy for gaps where an LLM answered; ``None`` = same as ``strategy``. The shipped
    config uses ``prerank`` for retrieval-only gaps and ``self-report`` once an LLM answered: on the 20 live-Sonnet
    VAL rows self-report had the better top-1 (0.15 vs 0.10), and prerank halves a correct LLM fill whose ISO
    length misses the letter-count ``[?N]`` (29% of VAL targets), which then abstained. ``with_(strategy=...)``
    (env, eval CLIs) sets both unless ``strategy_llm`` is given too.
    ``calibration``: JSON of per-decider Platt parameters and abstain thresholds fitted on the VAL split
    (``python -m ezhuthu.eval.calibrate``); relative paths are resolved against the package directory.
    ``calibration_min_n`` / ``calibration_min_positives``: an entry fitted on fewer VAL items (or fewer correct
    top-1s) is provisional and ignored; the variant then keeps raw confidences and the routing thresholds.
    """

    strategy: str = "prerank"
    strategy_llm: str | None = None
    top_k: int = 5
    llm_candidates: int = 8
    llm_max_tokens: int = 2048
    retry_on_truncation: bool = True
    parallels_k: int = 20
    prompt_parallels: int = 5
    ngram_k: int = 3
    calibration: str | None = "calibration.json"
    calibration_min_n: int = 100
    calibration_min_positives: int = 10

    def __post_init__(self) -> None:
        if self.strategy not in DECIDER_STRATEGIES:
            raise ValueError(f"restorer.strategy must be one of {DECIDER_STRATEGIES}, got {self.strategy!r}")
        if self.strategy_llm is not None and self.strategy_llm not in DECIDER_STRATEGIES:
            raise ValueError(f"restorer.strategy_llm must be one of {DECIDER_STRATEGIES}, got {self.strategy_llm!r}")
        if not 1 <= self.top_k <= 23:
            raise ValueError("restorer.top_k must be 1..23")

    def with_(self, **kw: Any) -> RestorerSettings:
        from dataclasses import replace

        kw = {k: v for k, v in kw.items() if v is not None}
        if "strategy" in kw and "strategy_llm" not in kw:  # an explicit override applies to every gap
            kw["strategy_llm"] = kw["strategy"]
        return replace(self, **kw)

    def strategy_for(self, llm_answered: bool) -> str:
        return (self.strategy_llm or self.strategy) if llm_answered else self.strategy


@dataclass(frozen=True)
class ModelsConfig:
    aws_profile: str
    region: str
    llm: dict[str, str]
    routing: Routing
    decider: dict[str, Any] = field(default_factory=dict)  # str model ids, plus the `cloud` block
    restorer: RestorerSettings = field(default_factory=RestorerSettings)

    def model_id(self, role: str) -> str:
        if role not in self.llm:
            raise KeyError(f"no llm role {role!r} in config/models.yaml (have {sorted(self.llm)})")
        return self.llm[role]

    @property
    def short_names(self) -> dict[str, str]:
        """model id -> short name used in API output (sonnet|opus|haiku)."""
        out = {}
        for mid in self.llm.values():
            for short in ("sonnet", "opus", "haiku"):
                if short in mid:
                    out[mid] = short
        return out


def parse_models_config(data: dict[str, Any]) -> ModelsConfig:
    r = data.get("routing", {}) or {}
    return ModelsConfig(
        aws_profile=data.get("aws_profile", "heisenberg"),
        region=data.get("region", "us-east-1"),
        llm=dict(data["llm"]),
        routing=Routing(**{k: r[k] for k in Routing.__dataclass_fields__ if k in r}),
        decider=dict(data.get("decider", {}) or {}),
        restorer=RestorerSettings(**{k: v for k, v in (data.get("restorer") or {}).items()
                                     if k in RestorerSettings.__dataclass_fields__}),
    )


@lru_cache(maxsize=4)
def load_models_config(path: str | None = None) -> ModelsConfig:
    p = Path(path) if path else find_models_yaml()
    return parse_models_config(yaml.safe_load(p.read_text()))


def live_enabled() -> bool:
    return os.environ.get("EZHUTHU_LIVE") == "1"
