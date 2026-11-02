"""restorer.ngram_gate / ngram_prerank / ngram_slot (deployed-config issue): mechanics on the fixture corpus."""

from __future__ import annotations

import dataclasses
import json

import pytest

from ezhuthu.agent.calibration import CalibrationTable
from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.decider import FakeDecider, NoDecider
from ezhuthu.agent.llm import FakeLLM
from ezhuthu.agent.restorer import Candidate, Restorer, ngram_softmax, prerank_score

CFG = load_models_config()
LEFT, RIGHT, GAP = "svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", 4


def _restorer(llm=None, decider=None, **settings) -> Restorer:
    base = dataclasses.replace(CFG.restorer, strategy="self-report", strategy_llm="prerank", top_k=3,
                               ngram_prerank=False, ngram_slot=False, ngram_gate=None)
    return Restorer(llm=llm, decider=decider or NoDecider(), settings=dataclasses.replace(base, **settings),
                    calibration=CalibrationTable())


def _llm(fill: str = "paṉma", p: float = 0.3) -> FakeLLM:
    return FakeLLM(lambda role, s, prompt: json.dumps({"fills": [[fill, p]]}, ensure_ascii=False))


def test_ngram_softmax_matches_the_baseline_confidence():
    out = ngram_softmax([("a", -1.0), ("b", -2.0)])
    assert out[0][0] == "a" and sum(p for _, p in out) == pytest.approx(1.0, abs=1e-3) and out[0][1] > out[1][1]
    assert ngram_softmax([]) == []


def test_gate_fills_the_ngram_and_asks_no_llm_when_its_share_passes():
    llm = _llm()
    r = _restorer(llm=llm, ngram_gate=0.001)  # any top fill passes
    g = r.restore_gap(LEFT, RIGHT, GAP, router="routed")
    assert llm.calls == [] and g.models_used == []
    assert g.strategy == "ngram-gate" and g.decider_model == "ngram-gate" and g.decision == "fill"
    assert "ngram" in g.best.sources and g.best.ngram_rank == 0
    assert g.abstain_below == pytest.approx(0.001) and g.calibration is None
    assert g.best.confidence == g.best.ngram_prob == g.best.raw_confidence


def test_gate_closed_falls_through_to_the_configured_llm_strategy():
    llm = _llm()
    r = _restorer(llm=llm, ngram_gate=1.0)  # a softmax share of exactly 1.0 needs a one-string beam
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    if g.strategy == "ngram-gate":  # pragma: no cover - the fixture beam has more than one string
        pytest.skip("fixture beam collapsed to one string")
    assert llm.calls and g.strategy == "prerank" and g.decider_model == "prerank"


def test_ngram_prerank_adds_the_ngram_share_as_a_noisy_or_term():
    c = Candidate("x", llm_confidence=0.5, ngram_rank=0, ngram_prob=0.5)
    assert prerank_score(c, 1, ngram=True) == pytest.approx(0.75)
    assert prerank_score(c, 1) == pytest.approx(0.51)  # the old epsilon, unchanged when the option is off
    r = _restorer(llm=_llm(), ngram_prerank=True)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert g.decider_model == "prerank-ngram" and g.strategy == "prerank"
    assert all(c.ngram_prob is not None for c in g.candidates)


def test_ngram_slot_shows_the_ngram_top_fill_to_a_topk_decider():
    dec = FakeDecider(lambda s, o: {n: 1.0 / len(o) for n in o})
    llm = FakeLLM(lambda role, s, p: json.dumps({"fills": [[f, 0.9 - i / 10] for i, f in enumerate(
        ["aaaa", "bbbb", "cccc", "dddd"])]}))
    r = _restorer(llm=llm, decider=dec, strategy_llm="choice-topk", ngram_slot=True)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet", max_candidates=30)
    ng = next(c for c in g.candidates if c.ngram_rank == 0)
    fills = [o["fill"] for n, o in dec.calls[-1]["options"].items() if n != "none"]
    assert len(fills) == 3 and ng.text in fills and "aaaa" in fills  # pre-rank top-1 is never displaced
    assert "ngram_probability" in dec.calls[-1]["options"]["c0"]


def test_options_off_leave_the_decider_request_unchanged():
    c = Candidate("x")
    assert "ngram_probability" not in c.option("a", "b")


def test_settings_validate_the_gate():
    with pytest.raises(ValueError):
        dataclasses.replace(CFG.restorer, ngram_gate=0.0)
    with pytest.raises(ValueError):
        dataclasses.replace(CFG.restorer, ngram_beam=1)


def test_platt_fit_converges_on_scores_bunched_near_one():
    """Undamped Newton diverged (a = 218) on the 5-gram pre-rank's VAL scores; step halving keeps the fit sane."""
    import json as _json
    from pathlib import Path

    from ezhuthu.agent.calibration import fit, fit_platt

    rows = Path(__file__).resolve().parents[2] / "eval/reports/2026-11-02-deployed-config/rows/val-hybrid-prerank.jsonl"
    rs = [_json.loads(x) for x in rows.read_text(encoding="utf-8").splitlines()[1:]]
    opus = [r for r in rs if CFG.model_id("escalate") in (r.get("models_used") or [])]
    x, y = [float(r["raw_confidence"] or 0.0) for r in opus], [bool(r["top1_correct"]) for r in opus]
    a, b = fit_platt(x, y)
    assert 0 < a < 5 and -5 < b < 0
    c = fit(x, y)
    assert c.threshold < 1.0 and sum(c.apply(v) >= c.threshold for v in x) < len(x)
    # a well-behaved fit is unchanged by the damping (issue #26's prerank|llm-sonnet entry, refitted from its rows)
    s = Path(__file__).resolve().parents[2] / "eval/reports/2026-11-02-val-selection/rows/val-sonnet-prerank.jsonl"
    rs = [_json.loads(v) for v in s.read_text(encoding="utf-8").splitlines()[1:]]
    assert fit_platt([float(r.get("raw_confidence") or 0.0) for r in rs], [bool(r["top1_correct"]) for r in rs]) == (
        1.021665, -2.296331)
