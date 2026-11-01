"""Decider benchmark harness (offline: fake deciders, synthetic frozen records)."""

from __future__ import annotations

import json

import pytest

import ezhuthu.eval.decider_bench as bench
from ezhuthu.agent.decider import DeciderUnavailable, FakeDecider, fit_choice, request_chars
from ezhuthu.agent.tutor import policy


def rec(i, target, fills, llm_conf):
    options = {f"c{k}": {"fill": f, "restored_line": f"x{f}y"} for k, f in enumerate(fills)}
    options["none"] = "none of these candidates fits the gap"
    return {"id": f"it{i}", "target": target, "gap_chars": 3, "hard": True, "age_set": False,
            "request": {"state": {"text_before_gap": "kō "}, "instructions": "pick", "options": options,
                        "name": "restoration"},
            "fills": fills, "llm_confidence": llm_conf, "fallback_confidence": llm_conf,
            "fallback_tag": "fallback:llm-self-report"}


RECS = [rec(0, "abc", ["abc", "abd"], [0.9, 0.1]), rec(1, "xyz", ["xya", "xyz"], [0.7, 0.2]),
        rec(2, "qqq", ["rrr"], [0.3]), {"id": "it3", "target": "t", "fills": [], "request": None,
                                       "error": "no candidates"}]


def by_fill(target_of):
    def picker(state, options):
        tgt = target_of
        keys = list(options)
        hit = next((k for k in keys if isinstance(options[k], dict) and options[k]["fill"] == tgt), "none")
        return {k: (0.8 if k == hit else 0.2 / (len(keys) - 1)) for k in keys}
    return picker


def test_fit_choice_drops_tail_keeps_none():
    opts = {f"c{i}": {"fill": "ā" * 50} for i in range(10)} | {"none": "none fits"}
    full = fit_choice({"s": 1}, "i", opts, "q", None)
    assert len(full["questions"]["q"]["criteria"]) == 11
    lim = request_chars(full) - 300
    fitted = fit_choice({"s": 1}, "i", opts, "q", lim)
    crit = fitted["questions"]["q"]["criteria"]
    assert request_chars(fitted) <= lim and "none" in crit and "c0" in crit and "c9" not in crit
    with pytest.raises(DeciderUnavailable, match="limit is 10"):
        fit_choice({"s": 1}, "i", opts, "q", 10)


def test_score_item_decider_and_fallback():
    d = FakeDecider(by_fill("abd"))
    s = bench.score_item(RECS[0], d, 0.5)
    assert (s.top1, s.correct, s.oracle, s.abstained, s.options_sent) == ("abd", False, True, False, 2)
    fb = bench.score_item(RECS[0], None, 0.5)
    assert (fb.top1, fb.correct, fb.confidence, fb.abstained) == ("abc", True, 0.9, False)
    empty = bench.score_item(RECS[3], d, 0.5)
    assert empty.abstained and not empty.correct and empty.error == "no candidates"


def test_score_item_fit_and_unavailable():
    big = rec(9, "a", ["a" * 400, "b" * 400, "c" * 400], [0.5, 0.4, 0.1])
    seen = {}

    def picker(state, options):
        seen["keys"] = list(options)
        return {k: 1 / len(options) for k in options}

    lim = request_chars(fit_choice(big["request"]["state"], "pick", big["request"]["options"], "restoration",
                                   None)) - 300
    s = bench.score_item(big, FakeDecider(picker), 0.5, fit_chars=lim)
    assert seen["keys"] == ["c0", "c1", "none"] and s.options_sent == 2

    class Down:
        def choice(self, *a, **k):
            raise DeciderUnavailable("refused (413 input_too_large)")

    s = bench.score_item(RECS[0], Down(), 0.5)
    assert s.abstained and "413" in s.error


def test_summarize_metrics():
    rows = [bench.score_item(r, None, 0.5).to_dict() for r in RECS]
    s = bench.summarize(rows)
    # it0 correct (0.9 filled), it1 wrong (0.7 filled), it2 wrong (0.3 abstain), it3 empty
    assert s["n"] == 4 and s["top1"] == 0.25 and s["abstain_rate"] == 0.5
    assert s["selective_accuracy"] == 0.5 and s["selective_n"] == 2
    assert s["oracle_in_candidates"] == 0.5 and s["top1_given_oracle"] == 0.5
    assert bench.pct([1, 2, 3, 4], 0.5) == 2.5 and bench.pct([], 0.5) is None


def test_policy_states_and_summary():
    states = bench.scripted_states()
    assert len(states) == 20 and {"correct", "attempts_on_item", "hint_already_given"} <= set(states[0])
    refs = {policy.rules(s["correct"], s["attempts_on_item"], s["hint_already_given"]) for s in states}
    assert refs == {"advance", "hint", "repeat"}  # the scripted set exercises every action
    rows = [{"decider_raw": "hint", "rules_reference": "hint", "final": "hint", "overridden": False,
             "backend": "local", "latency_ms": 5.0},
            {"decider_raw": "repeat", "rules_reference": "advance", "final": "advance", "overridden": True,
             "backend": "local", "latency_ms": 7.0}]
    s = bench.policy_summary(rows)
    assert s["raw_agree_with_rules"] == 0.5 and s["final_agree_with_rules"] == 1.0 and s["guardrail_overrides"] == 1


def test_score_and_report_end_to_end(tmp_path, monkeypatch):
    cands = tmp_path / "cands.jsonl"
    cands.write_text("".join(json.dumps(r) + "\n" for r in RECS))
    (tmp_path / "cands.jsonl.meta.json").write_text(json.dumps(
        {"split": "test", "subset": "hard", "limit": 4, "llm": "us.anthropic.claude-sonnet-4-6", "use_ontology": False}))
    monkeypatch.setattr(bench, "cache_dir", lambda: tmp_path)
    monkeypatch.setattr(bench, "make_decider",
                        lambda spec, slept: (None, "fallback:llm-self-report") if spec == "fallback"
                        else (FakeDecider(by_fill("abc")), "fake-decider"))
    assert bench.main(["score", "--cands", str(cands), "--decider", "fallback", "--label", "self"]) == 0
    assert bench.main(["score", "--cands", str(cands), "--decider", "local=x", "--label", "fake"]) == 0
    assert bench.main(["policy", "--decider", "local=x", "--label", "fake"]) == 0
    out = tmp_path / "rep"
    # Without --sync-from-cache the report reads only the committed rows dir (<out>/), which is empty here.
    assert bench.main(["report", "--cands", str(cands), "--labels", "fake,self,hosted", "--out", str(out)]) == 0
    assert json.loads(out.with_suffix(".json").read_text())["restoration"] == {}
    assert bench.main(["report", "--cands", str(cands), "--labels", "fake,self,hosted", "--out", str(out),
                       "--note", "synthetic", "--sync-from-cache"]) == 0
    assert sorted(p.name for p in out.iterdir()) == ["policy-fake.jsonl", "restoration-fake.jsonl",
                                                     "restoration-self.jsonl"]
    data = json.loads(out.with_suffix(".json").read_text())
    assert data["restoration"]["self"]["top1"] == 0.25 and data["restoration"]["fake"]["n"] == 4
    assert data["policy"]["fake"]["n"] == 20 and "hosted" not in data["restoration"]
    assert data["restoration"]["fake"]["rows_file"] == "rep/restoration-fake.jsonl"
    pair = data["pairwise"]["fake vs self"]
    assert pair["n"] == 4 and pair["only_a_correct"] + pair["only_b_correct"] + pair["both_correct"] <= 4
    sz = data["meta"]["request_chars_json_ascii"]
    assert sz["n"] == len([r for r in RECS if r.get("request")]) and sz["limit"] == 8000 and sz["over_limit"] == 0
    md = out.with_suffix(".md").read_text()
    assert "| hosted | not run |" in md and "synthetic" in md and "fallback:llm-self-report" in md
    assert "| fake vs self | 4 |" in md


def test_mcnemar_exact_and_compare():
    assert bench.mcnemar_exact(16, 5) == pytest.approx(0.0266, abs=1e-4)
    assert bench.mcnemar_exact(0, 0) == 1.0 and bench.mcnemar_exact(3, 3) == 1.0
    a = [{"id": "1", "correct": True, "top1": "x"}, {"id": "2", "correct": False, "top1": "y"},
         {"id": "3", "correct": False, "top1": None}]
    b = [{"id": "1", "correct": True, "top1": "x"}, {"id": "2", "correct": False, "top1": "z"},
         {"id": "3", "correct": False, "top1": "q"}]
    c = bench.compare(a, b)
    assert c["same_correctness_every_item"] and c["different_pick"] == 2 and c["different_pick_ids"] == ["2", "3"]
