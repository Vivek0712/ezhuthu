"""training/ft-decider/heldout_metrics.py: decider_bench top-1 semantics, the score-file filter, paired stats."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "training" / "ft-decider"
sys.path.insert(0, str(SCRIPTS))
import heldout_metrics as hm


def _row(i: str, label: str, sr=(0.1, 0.5, 0.2), hard=True) -> dict:
    return {"id": i, "label": label, "option_keys": ["c0", "c1", "c2", "none"], "self_report": list(sr),
            "inscription_id": "x", "hard": hard}


def test_top1_never_picks_none_and_self_confidence_reference():
    data = {"a": _row("a", "c1"), "b": _row("b", "none")}
    scores = [{"id": "a", "shape": "choice3", "probs": {"c0": 0.1, "c1": 0.3, "c2": 0.1, "none": 0.5}},
              {"id": "b", "shape": "choice3", "probs": {"c0": 0.2, "c1": 0.1, "c2": 0.1, "none": 0.6}}]
    ok = hm.choice_ok(scores, data)
    assert ok["a"]["ok"] and not ok["a"]["acc4"]  # forced fill c1 matches; 4-way argmax is none
    assert not ok["b"]["ok"] and ok["b"]["acc4"]
    ref = hm.reference_ok(data)
    assert ref["sonnet_self_confidence"]["a"]["ok"]  # argmax self-report = c1
    assert not ref["first_candidate_c0"]["a"]["ok"]


def test_paired_counts_and_mcnemar():
    a = {str(i): {"ok": i < 6} for i in range(10)}
    b = {str(i): {"ok": i < 2} for i in range(10)}
    p = hm.paired(a, b, [str(i) for i in range(10)])
    assert (p["only_a"], p["only_b"], p["delta"]) == (4, 0, 0.4)
    assert p["p_mcnemar"] == 0.125
    assert hm.mcnemar(0, 0) == 1.0


def test_cli_keeps_only_rows_of_the_given_data_file(tmp_path):
    data = tmp_path / "test.choice3.jsonl"
    data.write_text(json.dumps(_row("a", "c0")) + "\n", encoding="utf-8")
    scores = tmp_path / "s.jsonl"
    rows = [{"id": "a", "file": "test.choice3.jsonl", "shape": "choice3",
             "probs": {"c0": 0.9, "c1": 0.05, "c2": 0.05, "none": 0.0}},
            # same id from another data file (test-bench60 shares ids): must not override
            {"id": "a", "file": "test-bench60.choice3.jsonl", "shape": "choice3",
             "probs": {"c0": 0.0, "c1": 0.9, "c2": 0.1, "none": 0.0}}]
    scores.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    out = tmp_path / "o.json"
    subprocess.run([sys.executable, str(SCRIPTS / "heldout_metrics.py"), "--choice-data", str(data),
                    "--json-out", str(out), f"m={scores}", "--primary", "m"], check=True, capture_output=True)
    res = json.loads(out.read_text())
    assert res["choice3"]["m"]["top1"] == 1.0
