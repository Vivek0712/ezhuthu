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
LEFT, RIGHT, GAP = "svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", 5  # paṉmaṟku: 5 Tamil letters


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
    # VAL-chosen (issue #26): retrieval-only gaps self-report, LLM gaps the decider's noul on the top-3; with no
    # decider reachable (NoDecider here, the cloud runtime without one) LLM gaps fall back to self-report
    assert r.settings.strategy == CFG.restorer.strategy == "self-report"
    assert r.settings.strategy_llm == "noul-topk" and r.settings.top_k == 3
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
        # no decider here: noul-topk falls back to the LLM's own probability, which has no VAL calibration
        # entry, so raw confidences and the raw abstain threshold apply
        assert g.decider_model == "fallback:llm-self-report" and g.calibration is None
        assert g.abstain_below == CFG.routing.abstain_if_confidence_below and g.best.raw_confidence == p
    assert needless == 0 and filled == len(items)


def test_a_correct_llm_fill_longer_in_iso_than_the_letter_count_still_fills(shipped):
    """[?N] counts Tamil letters; ISO spells many letters with 2+ characters ("yañ ceytā" is 5 letters, 9 chars).
    The old ISO-character length check flagged 29% of VAL targets, and under prerank that halved a correct p=0.85
    LLM fill to 0.425 (abstain). The check now counts letters (issue #26): the fill is length-ok under every
    strategy and prerank keeps its 0.85."""
    target = "yañ ceytā"
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [[target, 0.85]]}, ensure_ascii=False))
    pars = [Parallel("I1", "1", "s", None, 60.0, "kōyil")]  # a good parallel (>= 50): no pre-escalation
    r = Restorer(llm=llm, use_ontology=False)
    r.retrieve_parallels = lambda *a, **k: list(pars)  # type: ignore[method-assign]
    g = r.restore_gap(LEFT, RIGHT, 5, router="routed")
    hit = next(c for c in g.candidates if c.text == target)
    assert hit.length_ok  # 5 letters for a 5-letter gap (9 ISO characters)
    assert g.decision == "fill" and g.best.text == target and not g.escalated  # fills, with Sonnet only
    assert [role for role, _ in llm.calls] == ["default"]
    pre = Restorer(llm=FakeLLM(lambda *a: json.dumps({"fills": [[target, 0.85]]}, ensure_ascii=False)),
                   use_ontology=False, settings=CFG.restorer.with_(strategy="prerank"))
    pre.retrieve_parallels = lambda *a, **k: list(pars)  # type: ignore[method-assign]
    g2 = pre.restore_gap(LEFT, RIGHT, 5, router="sonnet")
    assert g2.strategy == "prerank" and next(c for c in g2.candidates if c.text == target).prerank == 0.85


def test_strategy_override_applies_to_llm_gaps_too():
    assert CFG.restorer.with_(strategy="choice-topk").strategy_for(True) == "choice-topk"
    assert CFG.restorer.with_(strategy="choice-topk", strategy_llm="prerank").strategy_for(True) == "prerank"
    assert CFG.restorer.strategy_for(False) == "self-report" and CFG.restorer.strategy_for(True) == "noul-topk"
    with pytest.raises(ValueError):
        CFG.restorer.with_(strategy_llm="vote")


DEC = "strands-decider-2B-qwen3.5-v1-2610"


def test_shipped_calibration_entries_are_fitted_on_enough_val_items(shipped):
    """Issue #26: the |llm-sonnet and |llm-opus entries of the shipped strategy are fitted on >= 100 VAL items (the
    n=20 entries are gone), and retrieval-only gaps use the full-VAL (n=443) entry of the shipped strategy."""
    r = Restorer()
    llm_keys = [k for k in r.calibration.entries if "|llm" in k]
    assert all(k.endswith(("|llm-sonnet", "|llm-opus")) for k in llm_keys)  # router-aware keys
    for key in (f"{DEC}|noul-topk|k3|llm-sonnet", f"{DEC}|noul-topk|k3|llm-opus"):
        c = r.calibration.get(key)
        assert c is not None and c.n >= 100 and c.positives >= 10 and c.split == "val"
    assert all(e.n >= 100 for e in r.calibration.entries.values())
    g = r.restore_gap(LEFT, RIGHT, GAP, router="none")
    assert g.calibration == "fallback:retrieval-heuristic|fallback|kall|retrieval"
    assert r.calibration.get(g.calibration).n == 443


class _NoulDecider:
    """Says yes (p=0.9) to the candidate equal to ``target``, no (0.05) to anything else."""

    model = DEC

    def __init__(self):
        self.target = ""

    def available(self) -> bool:
        return True

    def choice(self, *a, **k):  # pragma: no cover - not used by noul-topk
        raise AssertionError("noul-topk must not call choice")

    def noul(self, state, instructions, *, name="q"):
        from ezhuthu.agent.decider import Noul

        p = 0.9 if state["candidate"]["fill"] == self.target else 0.05
        return Noul(p, DEC, source="fake")


def test_shipped_decider_path_fills_a_confident_correct_llm_fill_with_sonnet_only(shipped):
    dec = _NoulDecider()
    llm = FakeLLM(lambda role, s, prompt: json.dumps({"fills": [[dec.target, 0.85]]}, ensure_ascii=False))
    pars = [Parallel("I1", "1", "s", None, 60.0, "kōyil")]  # a good parallel: no pre-escalation
    r = Restorer(llm=llm, decider=dec, use_ontology=False)
    r.retrieve_parallels = lambda *a, **k: list(pars)  # type: ignore[method-assign]
    dec.target = "paṉmaṟku"
    g = r.restore_gap(LEFT, RIGHT, GAP, router="routed")
    assert [role for role, _ in llm.calls] == ["default"] and not g.escalated  # P(yes) 0.9 >= 0.6
    assert g.calibration == f"{DEC}|noul-topk|k3|llm-sonnet" and g.decision == "fill" and g.best.text == "paṉmaṟku"
    assert g.best.confidence_source == "decider-noul"


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
