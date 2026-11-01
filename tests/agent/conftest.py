"""Offline doubles: scripted Strands model, fake LLM, fake decider. No network in unit tests."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from typing import Any

import pytest
from strands.models.model import Model

os.environ.setdefault("EZHUTHU_FIXTURES", "1")
os.environ.setdefault("EZHUTHU_DECIDER", "off")
# Tests that script the Swarm turn by turn run it inside the Graph; async-explanation tests set "async".
os.environ.setdefault("EZHUTHU_LESSON_EXPLAIN", "sync")
os.environ.setdefault("EZHUTHU_NO_CACHE", "0" if os.environ.get("EZHUTHU_LIVE") == "1" else "1")


class ScriptedModel(Model):
    """A Strands model that replays scripted turns: ``str`` (text) or ``{"tool": name, "input": {...}}``."""

    def __init__(self, turns: list[Any]):
        self.turns = list(turns)
        self.seen: list[Any] = []
        self.config: dict[str, Any] = {}

    def update_config(self, **model_config: Any) -> None:
        self.config.update(model_config)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs) -> AsyncIterator[dict]:
        self.seen.append({"messages": messages, "system": system_prompt,
                          "tools": [t["name"] for t in tool_specs or []]})
        turn = self.turns.pop(0) if self.turns else "{}"
        yield {"messageStart": {"role": "assistant"}}
        if isinstance(turn, dict) and "tool" in turn:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": f"t{len(self.seen)}",
                                                               "name": turn["tool"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(turn["input"])}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": str(turn)}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15},
                            "metrics": {"latencyMs": 1}}}


@pytest.fixture
def scripted_model():
    return ScriptedModel


def prefer_target_picker(target_getter):
    """Fake decider that puts 0.8 on the option whose fill equals target_getter(), rest uniform."""

    def pick(state, options):
        tgt = target_getter()
        names = list(options)
        hit = [n for n in names if isinstance(options[n], dict) and options[n].get("fill") == tgt]
        if not hit:
            return {n: (0.9 if n == "none" else 0.1 / (len(names) - 1)) for n in names}
        rest = 0.2 / (len(names) - 1)
        return {n: (0.8 if n == hit[0] else rest) for n in names}

    return pick
