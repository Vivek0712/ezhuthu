"""The public results page's numbers (app/web/src/benchmark/summary.json) match the committed reports.

The JSON is built by scripts/build_benchmark_summary.py from the reports' machine-readable outputs. These tests check
it two ways, so the page cannot drift from what the reports say:
1. the committed file equals a fresh build;
2. every headline number also appears, in the same digits, in the Markdown report it is cited from.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "app" / "web" / "src" / "benchmark" / "summary.json"


def _script():
    spec = importlib.util.spec_from_file_location("build_benchmark_summary", ROOT / "scripts" / "build_benchmark_summary.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def summary() -> dict:
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def _md(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _num(x: float) -> str:
    """How the reports print a 4-decimal value in tables (trailing zeros dropped, e.g. 0.615)."""
    return repr(x)


def test_committed_json_matches_a_fresh_build():
    mod = _script()
    assert SUMMARY.read_text(encoding="utf-8") == mod.render(mod.build()), "run scripts/build_benchmark_summary.py"


def test_every_source_exists(summary):
    for rel in summary["sources"].values():
        assert (ROOT / rel).exists(), rel
    assert summary["github"] == "https://github.com/Vivek0712/ezhuthu/blob/main/"


def test_leaderboard_matches_the_reports(summary):
    dep = _md("eval/reports/2026-11-02-deployed-config.md")
    test = _md("eval/reports/2026-11-02-test-eval.md")
    full = {r["id"]: r for r in summary["leaderboard"]["full"]["rows"]}
    assert [r["id"] for r in summary["leaderboard"]["full"]["rows"]] == ["deployed", "ngram", "routed2b", "copy", "sonnet"]
    assert "**259 of 413** gaps (**0.6271**, 95% CI 0.5787-0.6731)" in dep
    assert full["deployed"]["matches"] == 259 and full["deployed"]["ci"] == [0.5787, 0.6731]
    # The TEST table of the deployed report: one line per row, with its CI.
    table = {
        "deployed": "| **Deployed: b2.",
        "copy": "| Copy baseline (PR #31 row) |",
        "ngram": "| Character 5-gram baseline (PR #31 row) |",
        "routed2b": "| Routed + local 2B decider (PR #31 measured pipeline) |",
    }
    for rid, prefix in table.items():
        line = next(ln for ln in dep.splitlines() if ln.startswith(prefix))
        r = full[rid]
        assert f"| {r['top1']:.4f} [{r['ci'][0]}, {r['ci'][1]}] |" in line, rid
    # Paired tests against the deployed system (McNemar table).
    for rid, name in (("copy", "copy baseline"), ("ngram", "character 5-gram"), ("routed2b", "PR #31 routed row")):
        v = full[rid]["vs_deployed"]
        assert f"| {name} | 413 | {v['only_deployed']} | {v['only_other']} | {v['p_text']} |" in dep, rid
    # Sonnet alone and the hard subset come from the TEST evaluation.
    s = full["sonnet"]
    assert f"| Sonnet 4.6 (VAL-chosen config, local 2B decider, ontology on) | 413 | {_num(s['top1'])} [{_num(s['ci'][0])}, {_num(s['ci'][1])}] |" in test
    assert s["vs_deployed"] is None
    hard = {r["id"]: r for r in summary["leaderboard"]["hard"]["rows"]}
    assert f"| hard | 317 | {hard['deployed']['top1']:.4f} [{hard['deployed']['ci'][0]}, {hard['deployed']['ci'][1]}] |" in dep
    hard_section = test.split("### Hard subset")[1].split("### Age subset")[0]
    for rid, prefix in (("copy", "| Copy baseline"), ("ngram", "| Character 5-gram"), ("routed2b", "| Routed Sonnet 4.6 -> Opus 4.6"),
                        ("sonnet", "| Sonnet 4.6 (VAL-chosen")):
        r = hard[rid]
        assert f"| 317 | {_num(r['top1'])} [{_num(r['ci'][0])}, {_num(r['ci'][1])}] |" in next(
            ln for ln in hard_section.splitlines() if ln.startswith(prefix)), rid


def test_abstention_matches_the_report(summary):
    dep = _md("eval/reports/2026-11-02-deployed-config.md")
    a = summary["abstention"]
    assert f"fills **{a['coverage'] * 100:.1f}%** of TEST gaps and **{a['selective_accuracy'] * 100:.1f}%** of" in dep
    assert f"({a['filled_matching']} of {a['filled']}); ECE {a['ece']:.3f}" in dep
    assert len(a["reliability"]) == 10 and sum(b["n"] for b in a["reliability"]) == a["n"] == 413


def test_gap_length_matches_the_report(summary):
    dep = _md("eval/reports/2026-11-02-deployed-config.md")
    bins = summary["gap_length"]["bins"]
    assert [b["n"] for b in bins] == [281, 81, 51]
    for rid, name in (("deployed", "Deployed"), ("copy", "Copy baseline"), ("ngram", "Character 5-gram"), ("routed2b", "PR #31 routed + local 2B")):
        assert f"| {name} | " + " | ".join(f"{b[rid]:.4f}" for b in bins) + " |" in dep, rid


def test_ocr_matches_the_report(summary):
    ocr = _md("eval/reports/2026-11-02-ocr-eval.md")
    o = summary["ocr"]
    for lvl in ("clean", "photo", "weathered"):
        assert f"| {lvl} | 24 | **{o['tamil_synthetic'][lvl]['cer']:.3f}** |" in ocr, lvl
    assert f"inscriptions **{o['brahmi_real']['cer']:.3f}** (3 images" in ocr
    assert f"printed pages **{o['printed_pages']['cer']:.3f}**" in ocr
    assert f"| **{o['brahmi_synthetic']['cer']:.3f}** |" in ocr


def test_decider_matches_the_reports(summary):
    dep = _md("eval/reports/2026-11-02-deployed-config.md")
    bench = _md("eval/reports/2026-11-02-decider-benchmark.md")
    h = summary["decider"]["hosted"]
    assert (f"it matched {h['hosted_matching']} vs {h['chosen_matching']} for the chosen\n  configuration "
            f"({h['only_hosted']} vs {h['only_chosen']} discordant, p = {h['p_text']})") in dep
    assert f"made {h['over_limit']} of {h['n']} gaps exceed the 27 s proxy limit (latency p90\n  {h['p90_s']} s" in dep
    sp = summary["decider"]["sparrow"]
    assert f"a uniform random pick among the top 3 = {sp['random_top3']:.3f}" in bench
    assert f"always pick candidate 1 = {sp['first_candidate']:.3f}" in bench
    assert f"| sparrow-nano | `sparrow-nano-general-v1.1` | {sp['nano_policy_raw']:.3f} | {sp['nano_policy_final']:.3f} |" in bench
    assert f"| sparrow-micro-top3 | `sparrow-micro-general-v1.1` | 60 | 0 | {sp['best_top1']:.3f} |" in bench


def test_split_counts_match_the_data_card(summary):
    card = _md("benchmark/DATA_CARD.md")
    sp = summary["method"]["splits"]
    assert (f"({sp['train']['inscriptions']} train, {sp['val']['inscriptions']} val, "
            f"{sp['test']['inscriptions']} test inscriptions)") in card
    assert re.search(rf"\| test \| {sp['test']['inscriptions']} \| {sp['test']['items']} \| {summary['method']['test_hard']} \|", card)
