"""The AgentCore runtime runs the restorer configuration chosen on VAL (eval/reports/2026-11-02-deployed-config.md),
with and without the hosted decider key, and fills or abstains on that configuration's VAL calibration.

The runtime builds ``EzhuthuService()`` (src/ezhuthu/agentcore_app.py): ``default_decider()`` picks the backend from
``EZHUTHU_DECIDER_BACKEND``, which infra sets to ``hosted`` when Secrets Manager ``ezhuthu/decider-api-key`` exists
and to ``fallback`` otherwise (infra/test/agent-runtime.test.ts also checks that no env var overrides the restorer
settings). These tests remove the tests/agent conftest overrides so they run what ships.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ezhuthu.agent import decider as decider_mod
from ezhuthu.agent.calibration import CalibrationTable
from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.decider import FakeDecider, NoDecider
from ezhuthu.agent.llm import FakeLLM
from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import MemoryStore
from ezhuthu.eval.deploy_config import VARIANTS, variant_settings

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "eval" / "reports" / "2026-11-02-deployed-config" / "decisions.json"
CFG = load_models_config()
TEXT = "svasti śrī kōvirājakēcari[?4] yāṇṭu mūṉṟāvatu"


@pytest.fixture
def shipped(monkeypatch):
    for var in ("EZHUTHU_CALIBRATION", "EZHUTHU_RESTORER_STRATEGY", "EZHUTHU_DECIDER"):
        monkeypatch.delenv(var, raising=False)


def _chosen() -> str:
    return json.loads(DECISIONS.read_text(encoding="utf-8"))["chosen"]


def test_shipped_config_is_the_variant_chosen_on_val():
    chosen = _chosen()
    assert chosen == "hybrid-prerank"
    assert variant_settings(CFG.restorer, chosen) == CFG.restorer
    assert CFG.restorer.strategy_llm == "prerank" and CFG.restorer.ngram_prerank
    assert not VARIANTS[chosen].get("hosted")  # restoration makes no decider call


def test_shipped_calibration_has_usable_entries_for_the_runtime_keys():
    s = CFG.restorer
    t = CalibrationTable.load(s.calibration, min_n=s.calibration_min_n, min_positives=s.calibration_min_positives)
    for llm in ("sonnet", "opus"):
        e = t.get(f"prerank-ngram|prerank|kall|llm-{llm}")
        assert e is not None and e.n >= 100 and e.split == "val", llm  # not provisional
    assert t.get("fallback:retrieval-heuristic|fallback|kall|retrieval") is not None  # an LLM call failed


class _RecordingHosted(FakeDecider):
    def __init__(self):
        super().__init__(lambda s, o: {n: 1.0 / len(o) for n in o}, model="strands-decider-2b-hobson-v19",
                         noul_fn=lambda s: 0.99)

    def health(self):
        return {"status": "ok", "model": self.model, "source": "hosted"}


@pytest.mark.parametrize("backend", ["hosted", "fallback"])
def test_runtime_resolves_to_the_chosen_config_with_and_without_the_decider_key(shipped, monkeypatch, backend):
    hosted = _RecordingHosted()
    monkeypatch.setattr(decider_mod, "hosted_decider", lambda *a, **k: hosted)
    monkeypatch.setenv("EZHUTHU_DECIDER_BACKEND", backend)
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [["paṉma", 0.7], ["rājar", 0.2]]}))
    svc = EzhuthuService(store=MemoryStore(), llm=llm, decider=None, model_factory=None, admin_token=None)
    assert isinstance(svc.decider, _RecordingHosted if backend == "hosted" else NoDecider)
    assert svc.restorer.settings == variant_settings(CFG.restorer, _chosen())
    out = svc.restore(TEXT, "iso15919", 5, True)
    g = out["gaps"][0]
    assert hosted.calls == []  # the hosted decider is never asked to rank restorations
    assert g["strategy"] == "prerank" and g["candidates"][0]["decider_model"] == "prerank-ngram"
    llm_used = "opus" if CFG.model_id("escalate") in out["models_used"] else "sonnet"
    key = f"prerank-ngram|prerank|kall|llm-{llm_used}"
    assert g["calibration"] == key  # calibrated scale, not the raw 0.5 threshold
    assert g["abstain_below"] == svc.restorer.calibration.get(key).threshold
