"""The AgentCore runtime runs the restorer configuration chosen on VAL, with and without the hosted decider key, and
fills or abstains on that configuration's VAL calibration.

Shipped (2026-11-03): once an LLM answered, the fine-tuned restoration decider (``ezhuthu-strands-2b-ft``, served by
decider-cloud; decider.cloud.restorer_model) ranks the pre-rank's top 3 + none: the variant the pre-registered rule
chose on VAL (eval/reports/2026-11-02-finetuned-decider.md, ``ft2b-choice3``). Without the key, or when the decider
is unavailable or out of time, the gap falls back to the deployed-config pre-rank (``hybrid-prerank``,
eval/reports/2026-11-02-deployed-config.md) and says ``decider_fallback``. The tutor keeps decider.cloud.model (v19).

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
from ezhuthu.agent.decider import DeciderUnavailable, FakeDecider, NoDecider
from ezhuthu.agent.llm import FakeLLM
from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import MemoryStore
from ezhuthu.eval import ft_decider_eval as ft
from ezhuthu.eval.deploy_config import VARIANTS

ROOT = Path(__file__).resolve().parents[2]
DECISIONS = ROOT / "eval" / "reports" / "2026-11-02-deployed-config" / "decisions.json"
FT_DECISIONS = ROOT / "eval" / "reports" / "2026-11-02-finetuned-decider" / "decisions.json"
FT_MODEL = "ezhuthu-strands-2b-ft"
CFG = load_models_config()
# the hosted runtime's decider bounds and fallback (not part of a VAL variant; the evals pin their own)
RUNTIME = {k: getattr(CFG.restorer, k) for k in ("decider_fallback", "decider_timeout_s", "decider_min_remaining_s")}
TEXT = "svasti śrī kōvirājakēcari[?4] yāṇṭu mūṉṟāvatu"


@pytest.fixture
def shipped(monkeypatch):
    for var in ("EZHUTHU_CALIBRATION", "EZHUTHU_RESTORER_STRATEGY", "EZHUTHU_DECIDER", "EZHUTHU_DECIDER_FALLBACK"):
        monkeypatch.delenv(var, raising=False)


def _chosen() -> str:
    return json.loads(DECISIONS.read_text(encoding="utf-8"))["chosen"]


def _ft_chosen() -> str:
    return json.loads(FT_DECISIONS.read_text(encoding="utf-8"))["chosen"]


def test_shipped_config_is_the_variant_chosen_on_val():
    chosen = _ft_chosen()
    assert chosen == "ft2b-choice3" and ft.VARIANTS[chosen]["decider"] == "ft2b"
    assert ft.variant_settings(CFG.restorer, chosen).with_(**RUNTIME) == CFG.restorer
    assert CFG.restorer.strategy_llm == "choice-topk" and CFG.restorer.top_k == 3 and CFG.restorer.ngram_prerank
    # the fallback is the earlier deployed choice, the decider-free pre-rank
    assert _chosen() == "hybrid-prerank" and not VARIANTS["hybrid-prerank"].get("hosted")
    assert CFG.restorer.decider_fallback == "prerank"
    assert CFG.restorer.decider_timeout_s and CFG.restorer.decider_timeout_s < CFG.restorer.request_budget_s
    cloud = CFG.decider["cloud"]
    assert cloud["restorer_model"] == FT_MODEL and cloud["model"] == "strands-decider-2b-hobson-v19"


def test_shipped_calibration_has_usable_entries_for_the_runtime_keys():
    s = CFG.restorer
    t = CalibrationTable.load(s.calibration, min_n=s.calibration_min_n, min_positives=s.calibration_min_positives)
    for llm in ("sonnet", "opus"):
        e = t.get(f"prerank-ngram|prerank|kall|llm-{llm}")
        assert e is not None and e.n >= 100 and e.split == "val", llm  # not provisional
        e = t.get(f"{FT_MODEL}|choice-topk|k3|llm-{llm}")  # the hosted fine-tuned decider's
        assert e is not None and e.n >= 100 and e.split == "val", llm
    assert t.get("fallback:retrieval-heuristic|fallback|kall|retrieval") is not None  # an LLM call failed


class _RecordingHosted(FakeDecider):
    def __init__(self, model: str, fail: bool = False):
        super().__init__(self._pick, model=model, noul_fn=lambda s: 0.99)
        self.fail = fail

    @staticmethod
    def _pick(state, options):
        keys = list(options)
        return {k: (0.7 if i == 0 else 0.3 / (len(keys) - 1)) for i, k in enumerate(keys)}

    def choice(self, *a, **k):
        if self.fail:
            self.calls.append({"failed": True, **k})
            raise DeciderUnavailable("hosted decider timed out")
        return super().choice(*a, **k)

    def health(self):
        return {"status": "ok", "model": self.model, "source": "hosted"}


def _service(monkeypatch, backend, *, fail=False):
    made: dict[str, _RecordingHosted] = {}

    def fake_hosted(*a, role="default", **k):
        model = FT_MODEL if role == "restorer" else "strands-decider-2b-hobson-v19"
        return made.setdefault(role, _RecordingHosted(model, fail=fail and role == "restorer"))

    monkeypatch.setattr(decider_mod, "hosted_decider", fake_hosted)
    monkeypatch.setenv("EZHUTHU_DECIDER_BACKEND", backend)
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [["paṉma", 0.7], ["rājar", 0.2]]}))
    svc = EzhuthuService(store=MemoryStore(), llm=llm, decider=None, model_factory=None, admin_token=None)
    return svc, made


def _assert_prerank_fallback(svc, out, reason):
    g = out["gaps"][0]
    assert g["strategy"] == "prerank" and g["candidates"][0]["decider_model"] == "prerank-ngram"
    assert g["decider_fallback"] == reason
    llm_used = "opus" if CFG.model_id("escalate") in out["models_used"] else "sonnet"
    key = f"prerank-ngram|prerank|kall|llm-{llm_used}"
    assert g["calibration"] == key  # calibrated scale, not the raw 0.5 threshold
    assert g["abstain_below"] == svc.restorer.calibration.get(key).threshold
    # Additive wire fields of the deployed config are documented in the contract (QA on PR #40).
    feats = [c["features"] for c in g["candidates"]]
    assert all("ngram_probability" in f for f in feats)
    assert any(isinstance(f["ngram_probability"], float) for f in feats)


def test_runtime_with_the_key_ranks_with_the_hosted_fine_tuned_decider(shipped, monkeypatch):
    svc, made = _service(monkeypatch, "hosted")
    assert svc.restorer.settings == CFG.restorer
    assert svc.decider is made["default"] and svc.decider.model == "strands-decider-2b-hobson-v19"  # the tutor's
    assert svc.restorer.decider is made["restorer"] and svc.restorer.decider.model == FT_MODEL
    out = svc.restore(TEXT, "iso15919", 5, True)
    g = out["gaps"][0]
    rcalls = made["restorer"].calls
    assert rcalls and made["default"].calls == []  # restoration asks the fine-tuned model only
    assert all(len(c["options"]) <= 4 and "none" in c["options"] for c in rcalls)  # top 3 + none
    # each call is bounded by what is left of the request budget, at most decider_timeout_s
    assert all(0 < c["timeout"] <= CFG.restorer.decider_timeout_s for c in rcalls)
    assert g["strategy"] == "choice-topk" and "decider_fallback" not in g
    assert g["candidates"][0]["decider_model"] == FT_MODEL
    llm_used = "opus" if CFG.model_id("escalate") in out["models_used"] else "sonnet"
    key = f"{FT_MODEL}|choice-topk|k3|llm-{llm_used}"
    assert g["calibration"] == key and g["abstain_below"] == svc.restorer.calibration.get(key).threshold
    assert FT_MODEL in out["models_used"]
    assert svc.health()["restorer_decider"] == FT_MODEL and svc.health()["decider"] == "strands-decider-2b-hobson-v19"


def test_runtime_without_the_key_is_the_deployed_prerank(shipped, monkeypatch):
    svc, made = _service(monkeypatch, "fallback")
    assert isinstance(svc.decider, NoDecider) and isinstance(svc.restorer.decider, NoDecider)
    assert svc.restorer.settings == CFG.restorer
    out = svc.restore(TEXT, "iso15919", 5, True)
    assert made == {}
    _assert_prerank_fallback(svc, out, "unavailable")


def test_runtime_falls_back_to_the_prerank_when_the_hosted_decider_fails(shipped, monkeypatch):
    svc, made = _service(monkeypatch, "hosted", fail=True)
    out = svc.restore(TEXT, "iso15919", 5, True)
    assert made["restorer"].calls  # it was asked, and failed
    _assert_prerank_fallback(svc, out, "unavailable")


def test_runtime_skips_the_decider_when_the_budget_is_spent(shipped, monkeypatch):
    svc, made = _service(monkeypatch, "hosted")
    st = svc.restorer.settings
    # less than decider_min_remaining_s left once the LLM has answered: no decider call, the pre-rank ranks
    svc.restorer.settings = st.with_(request_budget_s=st.llm_min_remaining_s + 1.0,
                                     decider_min_remaining_s=st.llm_min_remaining_s + 2.0)
    out = svc.restore(TEXT, "iso15919", 5, True)
    assert made["restorer"].calls == []
    _assert_prerank_fallback(svc, out, "time_budget")


def test_contract_documents_the_deployed_configs_additive_fields():
    text = " ".join((ROOT / "contracts" / "restore-api.md").read_text(encoding="utf-8").split())
    assert "`decider_model` is `\"prerank-ngram\"`" in text
    assert "`ngram_probability`" in text


def test_about_copy_says_the_fine_tuned_decider_picks_fills():
    """The web About page (en + ta) must describe what the deployed runtime does (QA on PR #40; updated when the
    fine-tuned restoration decider went live, 2026-11-04): the pre-rank shortlists and escalates, the fine-tuned
    Strands Decider picks one of the top 3 or none, the pre-rank is the fallback, and the decider also serves the tutor."""
    src = (ROOT / "app" / "web" / "src" / "i18n" / "strings.ts").read_text(encoding="utf-8")
    how2 = [ln for ln in src.splitlines() if "'about.how2':" in ln]
    assert len(how2) == 2  # English and Tamil
    en, ta = how2
    assert "A Strands Decider fine-tuned for Tamil inscriptions then picks one of the top three fills, or none" in en
    assert "which fill to choose" in en and "If the decider is slow or unavailable, the pre-rank decides" in en
    assert "also makes the tutor" in en
    assert "Strands Decider makes the calibrated calls" not in en
    assert "கூடுதல் பயிற்சி பெற்ற Strands Decider முதல் மூன்று நிரப்புகளில் ஒன்றை" in ta
    assert "ஆசிரியர் முடிவையும் Strands Decider எடுக்கிறது" in ta
    assert "Strands Decider அளவிட்ட முடிவுகளை எடுக்கிறது" not in ta
