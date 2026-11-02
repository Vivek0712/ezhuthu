"""ft_decider_eval: the pre-registered selection rule, fallback handling, variant settings and the TEST guards."""

from __future__ import annotations

import pytest

from ezhuthu.agent.config import load_models_config
from ezhuthu.eval import ft_decider_eval as m


def _s(matches: int, calls: int, p50: float) -> dict:
    return {"top1_matching": matches, "decider_calls": calls, "latency": {"p50_ms": p50}}


def test_choose_most_matches_then_fewer_calls_then_latency():
    s = {"ft2b-choice3": _s(100, 300, 3000.0), "ft2b-noul3": _s(101, 900, 4000.0),
         "sparrow-tiny-ft-choice3": _s(101, 300, 3500.0), "sparrow-nano-ft-choice3": _s(101, 300, 3400.0),
         "base2b-choice3": _s(150, 1, 1.0)}  # not a candidate: never chosen
    winner, ranking = m.choose(s)
    assert winner == "sparrow-nano-ft-choice3"
    assert ranking == ["sparrow-nano-ft-choice3", "sparrow-tiny-ft-choice3", "ft2b-noul3", "ft2b-choice3"]


def test_choose_needs_a_candidate():
    with pytest.raises(ValueError):
        m.choose({"base2b-choice3": _s(1, 1, 1.0)})


def test_decider_fallback_rows_count_as_misses():
    rows = [{"id": "a", "top1_correct": True, "decider_model": "fallback:llm-self-report"},
            {"id": "b", "top1_correct": True, "decider_model": "ezhuthu-strands-2b-ft"}]
    assert m.fallback_rows(rows, "ft2b-choice3") == 1
    assert [r["top1_correct"] for r in m.scored(rows, "ft2b-choice3")] == [False, True]
    # decider-free references keep their self-report rows
    assert m.fallback_rows(rows, "selfreport") == 0
    assert [r["top1_correct"] for r in m.scored(rows, "selfreport")] == [True, True]


def test_variant_settings():
    base = load_models_config().restorer
    s = m.variant_settings(base, "ft2b-choice3")
    assert (s.strategy_llm, s.top_k, s.ngram_prerank, s.ngram_slot, s.ngram_gate) == ("choice-topk", 3, True, False,
                                                                                       None)
    assert s.strategy == base.strategy  # retrieval-only gaps: as deployed
    assert m.variant_settings(base, "ft2b-choice3-slot").ngram_slot is True
    assert m.variant_settings(base, "ft2b-choice3-plain").ngram_prerank is False
    assert m.variant_settings(base, "ft2b-noul3").strategy_llm == "noul-topk"
    # the deployed reference here is the shipped configuration itself
    assert m.variant_settings(base, "hybrid-prerank") == base.with_(strategy_llm="prerank") == base


def test_every_candidate_has_a_decider_and_rule_is_fixed():
    assert all(m.VARIANTS[n]["decider"] for n in m.CANDIDATES)
    assert set(m.CANDIDATES) <= set(m.VAL_RUN)
    assert "base2b-choice3" not in m.CANDIDATES
    assert "strictly more VAL matches" in m.RULE


def test_parse_deciders():
    assert m.parse_deciders(["ft2b=http://127.0.0.1:8791"]) == {"ft2b": "http://127.0.0.1:8791"}
    with pytest.raises(SystemExit):
        m.parse_deciders(["ft2b"])


def test_test_refuses_dirty_code_and_needs_live(monkeypatch, tmp_path):
    monkeypatch.setattr(m, "code_provenance", lambda: {"code_commit": "x", "code_dirty": True})
    assert m.main(["test", "--out", str(tmp_path), "--decider", "ft2b=http://127.0.0.1:1"]) == 2
    monkeypatch.setattr(m, "code_provenance", lambda: {"code_commit": "x", "code_dirty": False})
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    assert m.main(["test", "--out", str(tmp_path), "--decider", "ft2b=http://127.0.0.1:1"]) == 2


def test_val_needs_live(monkeypatch, tmp_path):
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    assert m.main(["val", "--out", str(tmp_path)]) == 2
