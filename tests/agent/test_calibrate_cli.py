"""ezhuthu.eval.calibrate: VAL only, variant parsing, per-variant summary (offline, fake decider)."""

from __future__ import annotations

from ezhuthu.agent.calibration import fit
from ezhuthu.eval import calibrate


def test_refuses_any_split_but_val(capsys):
    assert calibrate.main(["--split", "test"]) == 2
    assert "VAL split only" in capsys.readouterr().err
    assert calibrate.main(["--split", "train"]) == 2


def test_parse_variants():
    assert calibrate.parse_variants("choice-all, choice-topk:3,noul-topk:5,prerank,fallback") == [
        ("choice-all", "choice-all", 5), ("choice-topk:3", "choice-topk", 3), ("noul-topk:5", "noul-topk", 5),
        ("prerank", "prerank", 5), ("fallback", "fallback", 5)]


def test_summary_and_paired_copy():
    rows = [{"id": str(i), "raw": c, "correct": ok, "oracle": True, "latency_ms": 10.0}
            for i, (c, ok) in enumerate([(0.9, True), (0.8, True), (0.3, False), (0.2, False)] * 5)]
    s = calibrate.summarize_variant(rows, "k", fit([r["raw"] for r in rows], [r["correct"] for r in rows]))
    assert s["n"] == 20 and s["top1"] == 0.5 and s["at_fitted_in_sample"]["accuracy"] == 1.0
    assert s["at_raw_0.5"]["coverage"] == 0.5 and s["latency_ms_p50"] == 10.0
    pv = calibrate.paired_vs_copy(rows[:4], {"0": True, "2": True})
    assert pv == {"both": 1, "only_variant": 1, "only_copy": 1}
