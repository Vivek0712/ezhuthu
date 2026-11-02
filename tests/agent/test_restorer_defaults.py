"""QA on PR #25: the shipped defaults (prerank + calibration.json) must not escalate or abstain on a confident,
correct LLM fill, and the copy-floor pre-rank must survive disagreeing parallels.

Unlike the rest of tests/agent, the end-to-end tests here remove the conftest overrides
(EZHUTHU_CALIBRATION=none, EZHUTHU_RESTORER_STRATEGY=choice-all) so they run what ships.
"""

from __future__ import annotations

import json

import pytest

from ezhuthu.agent.calibration import Calibration, CalibrationTable, variant_key
from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.data import load_items
from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.llm import FakeLLM
from ezhuthu.agent.restorer import Candidate, Restorer, prerank_score
from ezhuthu.agent.retrieval import Parallel
from ezhuthu.agent.text import normalize_iso

CFG = load_models_config()
LEFT, RIGHT, GAP = "svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", 8


@pytest.fixture
def shipped(monkeypatch):
    monkeypatch.delenv("EZHUTHU_CALIBRATION", raising=False)
    monkeypatch.delenv("EZHUTHU_RESTORER_STRATEGY", raising=False)


def _pre_escalates(r: Restorer, it) -> bool:
    rt, st = r.config.routing, r.settings
    pars = r.retrieve_parallels(it.left, it.right, it.gap_chars, k=max(st.parallels_k, st.prompt_parallels),
                                exclude_inscription=it.inscription_id)[: st.prompt_parallels]
    good = any(p.fill and p.score >= 50 for p in pars)
    length = r._estimate_len(it.gap_chars, pars)
    return length > rt.escalate_if_gap_chars_over or (rt.escalate_if_no_parallel and not good)


@pytest.mark.parametrize("p", [0.85, 0.92])
def test_shipped_defaults_fill_a_confident_correct_reply_without_escalating(shipped, p):
    cur = {}
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [[cur["target"], p]]}, ensure_ascii=False))
    r = Restorer(llm=llm)  # no settings / calibration / decider passed: config/models.yaml + calibration.json
    assert r.settings.strategy == CFG.restorer.strategy == "prerank"
    assert r.settings.strategy_llm == "self-report"
    assert r.calibration.entries, "the shipped calibration.json must load"
    items = [it for it in load_items("test") if it.gap_chars][:10]
    assert len(items) >= 5
    filled = needless = 0
    for it in items:
        cur["target"] = it.target
        before = len(llm.calls)
        g = r.restore_gap(it.left, it.right, it.gap_chars, router="routed", exclude_inscription=it.inscription_id,
                          dynasty=it.dynasty)
        roles = [role for role, _ in llm.calls[before:]]
        assert len(roles) == 1, f"{it.id}: {roles} - a confident fill must not trigger a second (Opus) call"
        if roles == ["escalate"]:
            assert _pre_escalates(r, it), f"{it.id}: escalated without a pre-escalation reason"
        else:
            assert not g.escalated
        needless += g.escalated and not _pre_escalates(r, it)
        filled += g.decision == "fill" and g.best.text == normalize_iso(it.target)
        # the |llm-* entries in calibration.json are provisional (n=20): raw confidences, raw threshold
        assert g.calibration is None and g.abstain_below == CFG.routing.abstain_if_confidence_below
        assert g.strategy == "self-report" and g.best.raw_confidence == p
    assert needless == 0 and filled == len(items)


def test_a_correct_llm_fill_longer_in_iso_than_the_letter_count_still_fills(shipped):
    """[?N] counts Tamil letters; ISO spells many letters with 2+ characters ("yañ ceytā" is 5 letters, 9 chars),
    so the ISO length check flags 29% of VAL targets. Under prerank that halved a correct p=0.85 LLM fill to 0.425
    (abstain); with strategy_llm=self-report the LLM's own probability stands."""
    target = "yañ ceytā"
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [[target, 0.85]]}, ensure_ascii=False))
    pars = [Parallel("I1", "1", "s", None, 60.0, "kōyil")]  # a good parallel (>= 50): no pre-escalation
    r = Restorer(llm=llm, use_ontology=False)
    r.retrieve_parallels = lambda *a, **k: list(pars)  # type: ignore[method-assign]
    g = r.restore_gap(LEFT, RIGHT, 5, router="routed")
    hit = next(c for c in g.candidates if c.text == target)
    assert not hit.length_ok  # the (ISO-character) length check still flags it ...
    assert g.decision == "fill" and g.best.text == target and not g.escalated  # ... but it fills, with Sonnet only
    assert [role for role, _ in llm.calls] == ["default"]
    pre = Restorer(llm=FakeLLM(lambda *a: json.dumps({"fills": [[target, 0.85]]}, ensure_ascii=False)),
                   use_ontology=False, settings=CFG.restorer.with_(strategy="prerank"))
    pre.retrieve_parallels = lambda *a, **k: list(pars)  # type: ignore[method-assign]
    g2 = pre.restore_gap(LEFT, RIGHT, 5, router="sonnet")
    assert g2.strategy == "prerank" and next(c for c in g2.candidates if c.text == target).prerank == 0.425


def test_strategy_override_applies_to_llm_gaps_too():
    assert CFG.restorer.with_(strategy="choice-topk").strategy_for(True) == "choice-topk"
    assert CFG.restorer.with_(strategy="choice-topk", strategy_llm="prerank").strategy_for(True) == "prerank"
    assert CFG.restorer.strategy_for(False) == "prerank" and CFG.restorer.strategy_for(True) == "self-report"
    with pytest.raises(ValueError):
        CFG.restorer.with_(strategy_llm="vote")


def test_shipped_llm_entries_are_provisional_and_retrieval_entries_are_used(shipped):
    r = Restorer()
    llm_keys = [k for k in r.calibration.entries if "|llm" in k]
    assert llm_keys and all(r.calibration.get(k) is None for k in llm_keys)
    assert all(k.endswith(("|llm-sonnet", "|llm-opus")) for k in llm_keys)  # router-aware keys
    assert r.calibration.get("prerank|prerank|kall|retrieval") is not None  # n=443, 104 positives
    g = r.restore_gap(LEFT, RIGHT, GAP, router="none")
    assert g.calibration == "prerank|prerank|kall|retrieval"


def test_escalation_uses_raw_confidence_not_the_calibrated_score():
    """A usable calibration that squashes scores (fill threshold 0.1) must not make a confident 0.85 escalate."""
    key = variant_key("prerank", "prerank", 5, "sonnet")
    table = CalibrationTable({key: Calibration(a=1.0, b=-4.0, threshold=0.1, n=500, positives=200)})
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [["paṉmaṟku", 0.85]]}, ensure_ascii=False))
    r = Restorer(llm=llm, decider=NoDecider(), use_ontology=False, settings=CFG.restorer.with_(strategy="prerank"),
                 calibration=table)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="routed", allow_escalation=True)
    assert not g.escalated and [role for role, _ in llm.calls] == ["default"]  # this gap has a good parallel
    assert g.calibration == key and g.best.raw_confidence >= 0.85 and g.best.confidence < 0.6
    assert g.decision == "fill"
    # a low raw confidence still escalates after Sonnet, and the gap is then calibrated as an Opus gap
    low = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [["xyzxyzxy", 0.05]]}, ensure_ascii=False))
    pars = [Parallel("I1", "1", "s", None, 90.0, "paṉmaṟku")]
    r2 = Restorer(llm=low, decider=NoDecider(), use_ontology=False,
                  settings=CFG.restorer.with_(strategy="prerank"), calibration=CalibrationTable(min_n=0,
                                                                                                  min_positives=0))
    r2.retrieve_parallels = lambda *a, **k: pars  # type: ignore[method-assign]
    r2.calibration.entries[variant_key("prerank", "prerank", 5, "opus")] = Calibration(1.0, 0.0, 0.5)
    g2 = r2.restore_gap(LEFT, RIGHT, GAP, router="routed")
    # copy fill pre-rank 0.9 >= 0.6: no escalation; force a weak parallel to see the escalation path
    assert not g2.escalated
    pars[0] = Parallel("I1", "1", "s", None, 55.0, "paṉmaṟku")
    g3 = r2.restore_gap(LEFT, RIGHT, GAP, router="routed")
    assert g3.escalated and [role for role, _ in low.calls][-2:] == ["default", "escalate"]
    assert g3.calibration == "prerank|prerank|kall|llm-opus"


def test_router_opus_uses_the_opus_calibration_key():
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [["paṉmaṟku", 0.7]]}, ensure_ascii=False))
    table = CalibrationTable({variant_key("prerank", "prerank", 5, "opus"): Calibration(1.0, 0.0, 0.5),
                              variant_key("prerank", "prerank", 5, "sonnet"): Calibration(1.0, 0.0, 0.9)},
                             min_n=0, min_positives=0)
    r = Restorer(llm=llm, decider=NoDecider(), use_ontology=False, settings=CFG.restorer.with_(strategy="prerank"),
                 calibration=table)
    assert r.restore_gap(LEFT, RIGHT, GAP, router="opus").calibration.endswith("|llm-opus")
    assert r.restore_gap(LEFT, RIGHT, GAP, router="sonnet").calibration.endswith("|llm-sonnet")


# ---------------------------------------------------------------- copy floor ---------------------------------
def _par(iid: str, score: float, fill: str) -> Parallel:
    return Parallel(iid, "1", f"snippet {iid}", None, score, fill)


def test_prerank_copy_floor_keeps_full_match_score_when_parallels_disagree():
    floor = Candidate("kōyilaka", retrieval_score=90.0, copy_floor=True)
    floor.parallels = [_par("A", 90.0, "kōyilaka")]
    majority = Candidate("nāṭṭuvar", retrieval_score=80.0)
    majority.parallels = [_par(f"B{i}", 80.0, "nāṭṭuvar") for i in range(3)]
    assert prerank_score(floor, 4) == 0.9  # not 0.9 x 1/4
    assert prerank_score(floor, 4) > prerank_score(majority, 4) == 0.6


def test_copy_floor_is_prerank_top1_through_restore_gap_with_disagreeing_parallels():
    found = [_par("A", 90.0, "kōyilaka")] + [_par(f"B{i}", 80.0, "nāṭṭuvar") for i in range(3)]
    r = Restorer(decider=NoDecider(), use_ontology=False, settings=CFG.restorer.with_(strategy="prerank"),
                 calibration=CalibrationTable())
    r.retrieve_parallels = lambda *a, **k: list(found)  # type: ignore[method-assign]
    g = r.restore_gap(LEFT, RIGHT, GAP, router="none", max_candidates=20)
    assert g.best.text == "kōyilaka" and g.best.copy_floor and g.best.prerank == 0.9
    other = next(c for c in g.candidates if c.text == "nāṭṭuvar")
    assert other.prerank == 0.6
