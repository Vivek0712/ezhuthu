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


@dataclass(frozen=True)
class ModelsConfig:
    aws_profile: str
    region: str
    llm: dict[str, str]
    routing: Routing
    decider: dict[str, str] = field(default_factory=dict)

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
    )


@lru_cache(maxsize=4)
def load_models_config(path: str | None = None) -> ModelsConfig:
    p = Path(path) if path else find_models_yaml()
    return parse_models_config(yaml.safe_load(p.read_text()))


def live_enabled() -> bool:
    return os.environ.get("EZHUTHU_LIVE") == "1"
