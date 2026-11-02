"""Issue #26: statistics and bookkeeping of the full VAL-selection / TEST evaluation (no network)."""

from __future__ import annotations

import math

from ezhuthu.eval import full_eval as fe
from ezhuthu.eval.stats import bootstrap_ci, mcnemar_exact, paired


def test_mcnemar_exact_matches_the_binomial():
    assert mcnemar_exact(0, 0) == 1.0
    assert mcnemar_exact(5, 5) == 1.0
    # 10 vs 0 discordant pairs: 2 * 0.5**10
    assert math.isclose(mcnemar_exact(10, 0), 2 * 0.5 ** 10, abs_tol=1e-6)  # rounded to 6 places
    assert mcnemar_exact(3, 1) == mcnemar_exact(1, 3) == 0.625


def test_paired_counts():
    p = paired([True, True, False, False], [True, False, True, False])
    assert (p["only_a"], p["only_b"], p["both"]) == (1, 1, 1)


def test_bootstrap_ci_brackets_the_mean_and_is_seeded():
    xs = [1.0] * 30 + [0.0] * 70
    lo, hi = bootstrap_ci(xs)
    assert lo < 0.3 < hi and 0.15 < lo and hi < 0.45
    assert bootstrap_ci(xs) == (lo, hi)
    assert bootstrap_ci([]) is None


def _row(i, ok, *, raw=None, calls=(), conf=0.5, abstained=False, hard=True, age=False, lat=100.0, wall=0.0):
    return {"id": f"i{i}", "top1_correct": ok, "in_top20": ok, "cer": 0.0 if ok else 1.5, "confidence": conf,
            "abstained": abstained, "hard": hard, "age_set": age, "raw_confidence": raw, "top1": "x" if ok else "y",
            "llm_calls": list(calls), "latency_ms": lat, "llm_wall_ms": wall}


SON = {"model": "sonnet", "input_tokens": 1000, "output_tokens": 100, "latency_ms": 2000.0, "cached": False}
OPU = {"model": "opus", "input_tokens": 1000, "output_tokens": 100, "latency_ms": 4000.0, "cached": True}


def test_simulate_routed_uses_sonnet_above_threshold_and_opus_below_or_on_pre_escalation():
    sonnet = [_row(0, True, raw=0.9, calls=[SON]), _row(1, False, raw=0.3, calls=[SON]), _row(2, False, raw=0.9,
                                                                                               calls=[SON])]
    always = [_row(0, False, calls=[SON, OPU]), _row(1, True, calls=[SON, OPU]), _row(2, True, calls=[OPU])]
    sim = fe.simulate_routed(sonnet, always, 0.6)
    assert [r["top1_correct"] for r in sim] == [True, True, True]  # 0: Sonnet kept, 1: escalated, 2: pre-escalated
    assert fe.cost(sim)["opus_items"] == 2
    assert [r["top1_correct"] for r in fe.simulate_routed(sonnet, always, 0.0)] == [True, False, True]


def test_cost_counts_cached_calls_at_their_original_tokens_and_latency_adds_llm_time():
    rows = [_row(0, True, calls=[SON, OPU], lat=500.0, wall=10.0)]
    c = fe.cost(rows)
    assert c["calls"] == 2 and c["live_calls_this_run"] == 1
    assert c["usd"] == round(1000 / 1e6 * 3 + 100 / 1e6 * 15 + 1000 / 1e6 * 5 + 100 / 1e6 * 25, 4)
    assert fe.latency(rows)["p50_ms"] == 490.0 + 6000.0


def test_summarize_coverage_uses_pipeline_decision_or_baseline_threshold():
    rows = [_row(0, True, conf=0.9), _row(1, False, conf=0.2), _row(2, False, conf=0.7, abstained=True)]
    s = fe.summarize(rows, n_boot=50)
    assert s["coverage"] == round(2 / 3, 4) and s["selective_accuracy"] == 0.5
    s2 = fe.summarize(rows, threshold=0.5, n_boot=50)
    assert s2["filled"] == 1 and s2["selective_accuracy"] == 1.0
    assert s["cer_clipped"] == round(2 / 3, 4)


def test_vs_pairs_by_item_id():
    a = [_row(0, True), _row(1, False, age=True)]
    b = [_row(1, True, age=True), _row(0, True)]
    v = fe.vs(a, b)
    assert v["full"]["only_a"] == 0 and v["full"]["only_b"] == 1 and v["age"]["n"] == 1


def test_seeded_sample_is_stable_and_keeps_order():
    from ezhuthu.agent.data import load_items

    items = load_items("test")  # fixtures (8 items) under the unit-test env
    s1, s2 = fe.seeded_sample(items, 5), fe.seeded_sample(items, 5)
    assert [i.id for i in s1] == [i.id for i in s2] and len(s1) == 5
    assert [i.id for i in s1] == [i.id for i in items if i.id in {x.id for x in s1}]
    assert fe.seeded_sample(items, 100) == items


def test_pre_escalates_matches_restore_gap():
    from ezhuthu.agent.data import load_items
    from ezhuthu.agent.decider import NoDecider
    from ezhuthu.agent.llm import FakeLLM
    from ezhuthu.agent.restorer import Restorer

    llm = FakeLLM(lambda role, s, p: '{"fills": [["xyz", 0.9]]}')
    r = Restorer(llm=llm, decider=NoDecider())
    for it in load_items("test"):
        llm.calls.clear()
        r.restore_gap(it.left, it.right, it.gap_chars, router="routed", exclude_inscription=it.inscription_id)
        assert (llm.calls[0][0] == "escalate") == fe.pre_escalates(r, it), it.id
