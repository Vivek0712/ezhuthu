"""Issue #22: truncation, retries, copy floor, top-k / noul deciders, per-decider VAL calibration."""

from __future__ import annotations

import json
import random
from collections.abc import AsyncIterator
from typing import Any

import pytest
from strands.models.model import Model

from ezhuthu.agent.baselines import copy_best_parallel
from ezhuthu.agent.calibration import (
    Calibration,
    CalibrationTable,
    cross_validated,
    fit,
    fit_platt,
    fit_threshold,
    variant_key,
)
from ezhuthu.agent.config import load_models_config, parse_models_config
from ezhuthu.agent.decider import FakeDecider, NoDecider
from ezhuthu.agent.llm import (
    BedrockLLM,
    FakeLLM,
    RateLimiter,
    backoff_delays,
    call_with_retries,
    is_retryable,
)
from ezhuthu.agent.prompts import parse_candidates, propose_max_tokens, propose_prompt
from ezhuthu.agent.restorer import Restorer, prerank_score

CFG = load_models_config()
LEFT, RIGHT, GAP = "svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", 8


# ---------------------------------------------------------------- truncation ---------------------------------
def test_prompt_is_compact_and_budget_scales():
    p = propose_prompt("a", "b", 6, [], [], 8)
    assert '{"fills": [["<gap text>", <probability>], ...]}' in p and "no reasoning" in p
    assert "cut off" in propose_prompt("a", "b", 6, [], [], 3, strict=True)
    assert propose_max_tokens(8, 6) >= 400 and propose_max_tokens(8, 40) > propose_max_tokens(8, 6)
    assert propose_max_tokens(23, 300) == 2048


def test_partial_json_keeps_complete_fills_only():
    cut = '{"fills": [["paṉmaṟku", 0.6], ["pa\\"ṉ", 0.2], ["kōvi'
    assert parse_candidates(cut) == [("paṉmaṟku", 0.6), ('pa"ṉ', 0.2)]
    assert parse_candidates('{"candidates": [{"text": "a", "confidence": 0.3}, {"text": "b"') == [("a", 0.3)]
    assert parse_candidates("I think the gap is") == []


class MaxTokensModel(Model):
    """Strands model that streams some text and stops with stopReason max_tokens."""

    def __init__(self, text: str):
        self.text = text
        self.config: dict[str, Any] = {}

    def update_config(self, **kw: Any) -> None:
        self.config.update(kw)

    def get_config(self) -> Any:
        return self.config

    async def structured_output(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kw) -> AsyncIterator[dict]:
        yield {"messageStart": {"role": "assistant"}}
        yield {"contentBlockStart": {"start": {}}}
        yield {"contentBlockDelta": {"delta": {"text": self.text}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "max_tokens"}}
        yield {"metadata": {"usage": {"inputTokens": 7, "outputTokens": 11, "totalTokens": 18},
                            "metrics": {"latencyMs": 1}}}


def test_bedrock_llm_returns_partial_text_on_max_tokens(monkeypatch, tmp_path):
    monkeypatch.setenv("EZHUTHU_LIVE", "1")
    llm = BedrockLLM(cache_dir=tmp_path, rpm=None)
    monkeypatch.setattr(llm, "_model", lambda mid, mt: MaxTokensModel('{"fills": [["paṉmaṟku", 0.6], ["x'))
    r = llm.complete("default", "sys", "prompt", max_tokens=50)
    assert r.truncated and r.text.startswith('{"fills"') and r.output_tokens == 11
    assert parse_candidates(r.text) == [("paṉmaṟku", 0.6)]
    hit = llm.complete("default", "sys", "prompt", max_tokens=50)  # cached, still flagged
    assert hit.cached and hit.truncated


def test_truncated_reply_is_retried_once_with_strict_prompt():
    def respond(role, system, prompt):
        if "cut off" in prompt:
            return '{"fills": [["oṉṟukku", 0.7]]}'
        return '{"fills": [["paṉmaṟku", 0.5], ["kō', True
    llm = FakeLLM(respond)
    r = Restorer(llm=llm, decider=NoDecider(), use_ontology=False)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet", max_candidates=20)
    assert len(llm.calls) == 2 and "cut off" in llm.calls[1][1]
    texts = {c.text for c in g.candidates}
    assert {"oṉṟukku", "paṉmaṟku"} <= texts and g.llm_truncated == 1 and g.llm_retries == 1
    assert llm.max_tokens[0] == propose_max_tokens(CFG.restorer.llm_candidates, GAP)
    no_retry = Restorer(llm=FakeLLM(respond), decider=NoDecider(), use_ontology=False,
                        settings=CFG.restorer.with_(retry_on_truncation=False))
    g2 = no_retry.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert len(no_retry.llm.calls) == 1 and g2.llm_truncated == 1 and g2.llm_retries == 0


# ---------------------------------------------------------------- throttling ---------------------------------
class Throttled(Exception):
    pass


Throttled.__name__ = "ModelThrottledException"


def test_backoff_has_full_jitter_and_cap():
    d = backoff_delays(6, base=2, cap=10, rng=random.Random(1))
    assert len(d) == 5 and all(0 <= x <= min(10, 2 * 2 ** i) for i, x in enumerate(d))
    assert len(set(d)) == 5  # jittered, not lockstep


def test_call_with_retries_retries_throttling_only():
    slept: list[float] = []
    n = {"i": 0}

    def flaky():
        n["i"] += 1
        if n["i"] < 3:
            raise Throttled("Too many requests")
        return "ok"

    assert call_with_retries(flaky, attempts=5, sleep=slept.append, rng=random.Random(0)) == "ok"
    assert n["i"] == 3 and len(slept) == 2
    with pytest.raises(ValueError):
        call_with_retries(lambda: (_ for _ in ()).throw(ValueError("bad request")), sleep=slept.append)
    assert len(slept) == 2
    with pytest.raises(Throttled):
        call_with_retries(lambda: (_ for _ in ()).throw(Throttled("x")), attempts=2, sleep=slept.append)

    class ClientErr(Exception):
        def __init__(self):
            super().__init__("throttled")
            self.response = {"Error": {"Code": "ThrottlingException"}}

    assert is_retryable(ClientErr()) and not is_retryable(KeyError("x"))


def test_rate_limiter_spaces_calls():
    t = {"now": 0.0}
    waits: list[float] = []

    def sleep(s):
        waits.append(s)
        t["now"] += s

    rl = RateLimiter(30, clock=lambda: t["now"], sleep=sleep)  # one every 2 s
    for _ in range(3):
        rl.acquire()
    assert waits == [2.0, 2.0]
    assert RateLimiter(None).acquire() == 0.0


def test_bedrock_llm_retries_throttled_invoke(monkeypatch, tmp_path):
    monkeypatch.setenv("EZHUTHU_LIVE", "1")
    slept: list[float] = []
    llm = BedrockLLM(cache_dir=tmp_path, rpm=None, sleep=slept.append, retry_base=0.01)
    n = {"i": 0}
    from ezhuthu.agent.llm import LLMResponse

    def invoke(mid, system, prompt, mt):
        n["i"] += 1
        if n["i"] == 1:
            raise Throttled("Too many requests")
        return LLMResponse('{"fills": []}', mid)

    monkeypatch.setattr(llm, "_invoke", invoke)
    r = llm.complete("default", "s", "p")
    assert r.attempts == 2 and len(slept) == 1 and llm.ledger.calls == 1


# ---------------------------------------------------------------- copy floor ---------------------------------
def test_copy_floor_is_a_candidate_and_matches_copy_baseline():
    r = Restorer(decider=NoDecider(), use_ontology=False)
    g = r.restore_gap(LEFT, RIGHT, GAP, max_candidates=20)
    floor = [c for c in g.candidates if c.copy_floor]
    base = copy_best_parallel(r, LEFT, RIGHT, GAP)
    assert len(floor) == 1 and floor[0].text == base[0][0]
    api = g.to_api()["candidates"]
    assert any(c["features"]["copy_baseline"] for c in api)
    assert any(c["features"]["ngram_rank"] == 0 for c in api)  # n-gram top fill is a candidate too


def test_prerank_noisy_or():
    from ezhuthu.agent.restorer import Candidate

    a = Candidate("a", llm_confidence=0.5, retrieval_score=100.0)
    a.parallels = [object()]  # type: ignore[list-item]
    assert prerank_score(a, 1) == 1.0
    b = Candidate("b", llm_confidence=0.5)
    assert prerank_score(b, 1) == 0.5
    b.length_ok = False
    assert prerank_score(b, 1) == 0.25


# ---------------------------------------------------------------- strategies ---------------------------------
def llm_with(cands):
    return FakeLLM(lambda role, s, p: json.dumps({"fills": cands}, ensure_ascii=False))


MANY = [["kōyil" + "a" * i, 0.9 - i * 0.05] for i in range(8)]


def test_choice_topk_sends_k_options_and_keeps_copy_floor():
    seen = {}

    def picker(state, options):
        seen["opts"] = options
        names = list(options)
        return {n: 1 / len(names) for n in names}

    for k in (3, 5):
        r = Restorer(llm=llm_with(MANY), decider=FakeDecider(picker), use_ontology=False,
                     settings=CFG.restorer.with_(strategy="choice-topk", top_k=k), calibration=CalibrationTable())
        g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet", max_candidates=20)
        opts = seen["opts"]
        assert len(opts) == k + 1 and "none" in opts
        assert any(v["copy_baseline"] for n, v in opts.items() if n != "none")
        assert all({"llm_probability", "best_parallel_match", "ngram_proposal"} <= set(v)
                   for n, v in opts.items() if n != "none")
        outside = [c for c in g.candidates if c.confidence_source == "not-in-top-k"]
        assert outside and all(c.confidence == 0.0 for c in outside)
        assert g.strategy == "choice-topk"


def test_choice_all_is_the_old_behaviour():
    seen = {}

    def picker(state, options):
        seen["n"] = len(options)
        return {n: 1 / len(options) for n in options}

    r = Restorer(llm=llm_with(MANY), decider=FakeDecider(picker), use_ontology=False,
                 settings=CFG.restorer.with_(strategy="choice-all"), calibration=CalibrationTable())
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet", max_candidates=30)
    assert seen["n"] == len(g.candidates) + 1


def test_noul_topk_scores_each_candidate():
    def noul(state):
        return 0.9 if state["candidate"]["fill"] == "paṉmaṟku" else 0.1

    dec = FakeDecider(lambda s, o: {}, noul_fn=noul)
    r = Restorer(llm=llm_with([["paṉmaṟku", 0.3], ["xx", 0.9]]), decider=dec, use_ontology=False,
                 settings=CFG.restorer.with_(strategy="noul-topk", top_k=3), calibration=CalibrationTable())
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert len([c for c in dec.calls if "noul" in c]) == 3
    assert g.best.text == "paṉmaṟku" and g.best.confidence == 0.9 and g.decision == "fill"
    assert g.best.confidence_source == "decider-noul"


def test_noul_without_support_falls_back():
    r = Restorer(llm=llm_with([["paṉmaṟku", 0.8]]), decider=FakeDecider(lambda s, o: {}), use_ontology=False,
                 settings=CFG.restorer.with_(strategy="noul-topk"), calibration=CalibrationTable())
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert g.decider_model == "fallback:llm-self-report"


def test_prerank_strategy_needs_no_decider():
    dec = FakeDecider(lambda s, o: pytest.fail("decider must not be called"))
    r = Restorer(llm=llm_with([["paṉmaṟku", 0.8]]), decider=dec, use_ontology=False,
                 settings=CFG.restorer.with_(strategy="prerank"), calibration=CalibrationTable())
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert g.decider_model == "prerank" and g.best.confidence == g.best.prerank


def test_settings_from_yaml_and_validation():
    c = parse_models_config({"llm": {"default": "x"}, "restorer": {"strategy": "noul-topk", "top_k": 3}})
    assert c.restorer.strategy == "noul-topk" and c.restorer.top_k == 3
    assert CFG.restorer.strategy in ("choice-all", "choice-topk", "noul-topk", "prerank")
    with pytest.raises(ValueError):
        CFG.restorer.with_(strategy="vote")


# ---------------------------------------------------------------- calibration --------------------------------
def test_platt_recovers_a_spread_and_threshold_maximises_margin():
    rng = random.Random(3)
    conf, ok = [], []
    for _ in range(400):  # true P(correct) = 2.5 x raw, a decider that is under-confident
        c = rng.uniform(0.05, 0.4)
        conf.append(c)
        ok.append(rng.random() < min(1.0, 2.5 * c))
    a, b = fit_platt(conf, ok)
    cal = Calibration(a, b)
    assert cal.apply(0.35) > 0.6 and cal.apply(0.06) < 0.3
    t = fit_threshold([cal.apply(c) for c in conf], ok)
    assert 0.3 < t < 0.7
    assert fit_threshold([0.9, 0.8], [False, False]) == 1.0  # never more right than wrong: always abstain


def test_fit_and_cross_validation_and_table_round_trip(tmp_path):
    conf = [0.1, 0.2, 0.3, 0.4] * 10
    ok = [False, False, True, True] * 10
    c = fit(conf, ok, split="val", fitted_at="t")
    assert c.n == 40 and c.positives == 20 and c.apply(0.4) > c.apply(0.1)
    cal, filled = cross_validated(conf, ok, folds=5)
    assert len(cal) == 40 and any(filled)
    key = variant_key("m", "choice-topk", 3, True)
    assert key == "m|choice-topk|k3|llm" and variant_key("m", "choice-all", 3, False) == "m|choice-all|kall|retrieval"
    p = tmp_path / "cal.json"
    p.write_text(CalibrationTable({key: c}).to_json())
    t = CalibrationTable.load(p)
    assert t.get(key) == c and CalibrationTable.load(tmp_path / "missing.json").entries == {}


def test_restorer_applies_per_decider_calibration_and_threshold():
    def picker(state, options):
        names = [n for n in options if n != "none"]
        return {**{n: 0.05 for n in names}, names[0]: 0.3, "none": 0.0}

    dec = FakeDecider(picker)
    key = variant_key("fake-decider", "choice-topk", 3, True)
    table = CalibrationTable({key: Calibration(a=1.0, b=1.5, threshold=0.4)})
    r = Restorer(llm=llm_with([["paṉmaṟku", 0.8]]), decider=dec, use_ontology=False,
                 settings=CFG.restorer.with_(strategy="choice-topk", top_k=3), calibration=table)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert g.calibration == key and g.abstain_below == 0.4
    assert g.best.raw_confidence == 0.3 and g.best.confidence == Calibration(1.0, 1.5).apply(0.3)
    assert g.decision == "fill"  # raw 0.3 would abstain at the uncalibrated 0.5
    uncal = Restorer(llm=llm_with([["paṉmaṟku", 0.8]]), decider=dec, use_ontology=False,
                     settings=CFG.restorer.with_(strategy="choice-topk", top_k=3), calibration=CalibrationTable())
    g2 = uncal.restore_gap(LEFT, RIGHT, GAP, router="sonnet")
    assert g2.calibration is None and g2.abstain_below == CFG.routing.abstain_if_confidence_below
    assert g2.decision == "abstain"


def test_budgeted_llm_caps_live_calls_but_not_cache_hits(monkeypatch, tmp_path):
    from ezhuthu.agent.llm import BudgetedLLM, LiveCallsDisabled, LLMResponse

    monkeypatch.setenv("EZHUTHU_LIVE", "1")
    inner = BedrockLLM(cache_dir=tmp_path, rpm=None)
    monkeypatch.setattr(inner, "_invoke", lambda mid, s, p, mt: LLMResponse('{"fills": []}', mid, 1, 1))
    llm = BudgetedLLM(inner, 1)
    llm.complete("default", "s", "p1")
    llm.complete("default", "s", "p1")  # cached: allowed
    with pytest.raises(LiveCallsDisabled):
        llm.complete("default", "s", "p2")
    assert inner.ledger.calls == 1 and llm.exhausted == 1
    r = Restorer(llm=llm, decider=NoDecider(), use_ontology=False)
    g = r.restore_gap(LEFT, RIGHT, GAP, router="sonnet")  # budget gone: retrieval candidates only, no crash
    assert g.models_used == [] and g.candidates
