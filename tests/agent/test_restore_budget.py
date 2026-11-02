"""Request budget, gap cap and warm-up for ``Restorer.restore`` (issue #41). Fake clock + fake LLM, no network."""

from __future__ import annotations

import json
import threading
from dataclasses import replace

import pytest

from ezhuthu.agent.config import RestorerSettings, load_models_config
from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.llm import BedrockLLM, FakeLLM, LLMResponse
from ezhuthu.agent.restorer import Restorer

CFG = load_models_config()
LINE = "svasti śrī kōvirājakēcari[?8] yāṇṭu mūṉṟāvatu"
SONNET_S, OPUS_S = 4.0, 6.0  # simulated call latencies


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def settings(**kw) -> RestorerSettings:
    # The shipped knobs, with the strategy the unit tests use (raw self-report confidences, no decider).
    return replace(CFG.restorer, strategy="self-report", strategy_llm="self-report", **kw)


def slow_llm(clock: Clock, conf: float = 0.3, fill: str = "paṉmaṟku") -> FakeLLM:
    def respond(role, system, prompt):
        clock.t += OPUS_S if role == "escalate" else SONNET_S
        return json.dumps({"candidates": [{"text": fill, "confidence": conf}]}, ensure_ascii=False)
    return FakeLLM(respond)


def restorer(llm, clock: Clock, **kw) -> Restorer:
    return Restorer(llm=llm, decider=NoDecider(), settings=settings(**kw), clock=clock)


def text_with_gaps(n: int) -> str:
    return " ".join([LINE] * n)


def test_many_gaps_return_within_budget_with_reasons():
    clock = Clock()
    llm = slow_llm(clock)
    r = restorer(llm, clock, request_budget_s=25, max_gaps_per_request=None)
    retrieve = r.retrieve_parallels

    def slow_retrieval(*a, **kw):  # 1.5 s of local work per attempted gap
        clock.t += 1.5
        return retrieve(*a, **kw)

    r.retrieve_parallels = slow_retrieval
    out = r.restore(text_with_gaps(12))
    assert out["latency_ms"] <= 25_000
    gaps = out["gaps"]
    assert len(gaps) == 12
    # every LLM call was bounded by what was left of the budget
    assert llm.timeouts and all(t is not None and t <= 25 for t in llm.timeouts)
    late = [g for g in gaps if g.get("abstain_reason") == "time_budget"]
    assert late and all(g["decision"] == "abstain" and g["candidates"] == [] and g["chosen"] is None for g in late)
    assert any(g.get("llm_skipped") == "time_budget" for g in gaps)
    b = out["budget"]
    assert b["limited"] and b["request_budget_s"] == 25 and b["abstained"]["time_budget"] == len(late)
    assert out["restored_text"].count("[?8]") >= len(late)  # abstained gaps keep their marker


def test_escalation_skipped_when_budget_is_low():
    clock = Clock()
    llm = slow_llm(clock, conf=0.3)
    # Unconstrained: Sonnet answers 0.3 < routing.escalate_if_confidence_below, so Opus is asked.
    free = restorer(llm, clock, request_budget_s=None).restore(LINE)
    assert [r for r, _ in llm.calls] == ["default", "escalate"] and free["gaps"][0]["escalated"]
    clock2 = Clock()
    llm2 = slow_llm(clock2, conf=0.3)
    # 10 s budget: after Sonnet's 4 s, 6 s < escalate_min_remaining_s (8) is left.
    out = restorer(llm2, clock2, request_budget_s=10).restore(LINE)
    g = out["gaps"][0]
    assert [r for r, _ in llm2.calls] == ["default"]
    assert g["escalation_skipped"] == "time_budget" and not g["escalated"]
    assert out["budget"]["escalation_skipped"] == 1 and out["budget"]["limited"]


def test_pre_escalation_falls_back_to_sonnet_when_low():
    clock = Clock()
    llm = slow_llm(clock, conf=0.9)
    # [?14] > routing.escalate_if_gap_chars_over (12): routed pre-escalates to Opus when time allows.
    long_gap = "svasti śrī kōvirājakēcari[?14] yāṇṭu"
    restorer(llm, clock, request_budget_s=None).restore(long_gap)
    assert llm.calls[0][0] == "escalate"
    clock2 = Clock()
    llm2 = slow_llm(clock2, conf=0.9)
    out = restorer(llm2, clock2, request_budget_s=7).restore(long_gap)  # 7 s: Sonnet (6) yes, Opus (8) no
    assert [r for r, _ in llm2.calls] == ["default"]
    assert out["gaps"][0]["escalation_skipped"] == "time_budget"


def test_llm_skipped_when_budget_is_low():
    clock = Clock()
    llm = slow_llm(clock)
    out = restorer(llm, clock, request_budget_s=5).restore(text_with_gaps(3))  # 5 s < llm_min_remaining_s (6)
    assert llm.calls == []
    for g in out["gaps"]:
        assert g["llm_skipped"] == "time_budget" and "abstain_reason" not in g
        assert g["candidates"] and g["candidates"][0]["model"] == "retrieval"  # retrieval + 5-gram still run
    assert out["models_used"] == [] and out["budget"]["llm_skipped"] == 3


def test_gap_cap_is_honoured():
    clock = Clock()
    out = restorer(None, clock, request_budget_s=None, max_gaps_per_request=2).restore(text_with_gaps(4))
    reasons = [g.get("abstain_reason") for g in out["gaps"]]
    assert reasons == [None, None, "gap_cap", "gap_cap"]
    assert all(g["candidates"] == [] and g["decision"] == "abstain" for g in out["gaps"][2:])
    assert out["budget"]["abstained"] == {"time_budget": 0, "gap_cap": 2} and out["budget"]["limited"]


def test_unconstrained_budget_leaves_results_identical():
    """A small request inside the budget is restored exactly as with no budget at all (ranking, calibration and
    selection unchanged): same gaps, same candidates and confidences, same LLM prompts."""
    def run(**kw):
        llm = FakeLLM(lambda role, s, p: json.dumps({"candidates": [{"text": "paṉmaṟku", "confidence": 0.55},
                                                                    {"text": "irāṇṭu", "confidence": 0.2}]},
                                                    ensure_ascii=False))
        r = Restorer(llm=llm, decider=NoDecider(), settings=replace(CFG.restorer, **kw))
        return r.restore(text_with_gaps(2)), llm

    budgeted, l1 = run(request_budget_s=25, max_gaps_per_request=8)
    free, l2 = run(request_budget_s=None, max_gaps_per_request=None)
    assert budgeted["gaps"] == free["gaps"]
    assert budgeted["restored_text"] == free["restored_text"] and budgeted["models_used"] == free["models_used"]
    assert l1.calls == l2.calls
    assert not budgeted["budget"]["limited"]
    assert all(t is not None for t in l1.timeouts) and all(t is None for t in l2.timeouts)


def test_failed_llm_call_under_budget_keeps_other_candidates():
    clock = Clock()

    def boom(role, system, prompt):
        clock.t += 30
        raise TimeoutError("read timed out")

    out = restorer(FakeLLM(boom), clock, request_budget_s=25).restore(text_with_gaps(2))
    g0, g1 = out["gaps"]
    assert g0["llm_skipped"] == "time_budget" and g0["candidates"]  # retrieval candidates kept
    assert g1["abstain_reason"] == "time_budget"
    # Without a budget (per-gap evals) the error still propagates, as before.
    with pytest.raises(TimeoutError):
        restorer(FakeLLM(boom), Clock(), request_budget_s=None).restore(LINE)


def test_truncation_retry_skipped_when_budget_is_low():
    clock = Clock()

    def respond(role, system, prompt):
        clock.t += SONNET_S
        return ('{"candidates": [{"text": "paṉmaṟku", "confidence": 0.9}, {"text": "ir', True)

    llm = FakeLLM(respond)
    restorer(llm, clock, request_budget_s=9).restore(LINE)  # 5 s left after the first call < 6
    assert len(llm.calls) == 1


def test_bedrock_text_call_honours_timeout(monkeypatch):
    monkeypatch.setenv("EZHUTHU_LIVE", "1")
    llm = BedrockLLM(cache_dir=None, rpm=None)
    seen = {}

    def invoke(model_id, system, prompt, max_tokens, read_timeout=None):
        seen["read_timeout"] = read_timeout
        return LLMResponse("{}", model_id, 1, 1)

    monkeypatch.setattr(llm, "_invoke", invoke)
    llm.complete("default", "sys", "p", max_tokens=10, timeout_s=12.0)
    assert seen["read_timeout"] is not None and 11.0 < seen["read_timeout"] <= 12.0
    llm.complete("default", "sys", "p2", max_tokens=10)
    assert seen["read_timeout"] is None


def test_warm_builds_index_and_ngram_once():
    r = Restorer(decider=NoDecider())
    parts = r.warm()
    assert set(parts) == {"corpus", "index", "ngram"}
    assert "ngram" in r.__dict__ and "index" in r.__dict__
    ng = r.ngram
    assert r.warm()["ngram"] < 0.05 and r.ngram is ng


def test_concurrent_first_use_builds_the_ngram_once(monkeypatch):
    import ezhuthu.agent.restorer as mod

    built = []
    real = mod.CharNgram

    class Counting(real):
        def fit(self, lines):
            built.append(1)
            return super().fit(lines)

    monkeypatch.setattr(mod, "CharNgram", Counting)
    r = Restorer(decider=NoDecider())
    got = []
    ts = [threading.Thread(target=lambda: got.append(r.ngram)) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(built) == 1 and all(g is got[0] for g in got)


def test_agentcore_warmup(monkeypatch):
    from ezhuthu import agentcore_app

    class Svc:
        restorer = Restorer(decider=NoDecider())

    out = agentcore_app.warm_up(Svc())
    assert {"service", "corpus", "index", "ngram"} <= set(out)
    monkeypatch.setenv("EZHUTHU_WARMUP", "0")
    assert agentcore_app.start_warmup(Svc()) is None
    monkeypatch.setenv("EZHUTHU_WARMUP", "1")
    th = agentcore_app.start_warmup(Svc())
    th.join(timeout=30)
    assert not th.is_alive()


def test_budget_settings_are_validated():
    with pytest.raises(ValueError):
        replace(CFG.restorer, request_budget_s=-1)
    with pytest.raises(ValueError):
        replace(CFG.restorer, max_gaps_per_request=-2)
    assert CFG.restorer.request_budget_s == 25 and CFG.restorer.max_gaps_per_request == 8
