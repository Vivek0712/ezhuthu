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


def test_provenance_separates_code_and_data_commits(tmp_path):
    import subprocess

    from ezhuthu.eval.run import code_provenance, git_commit

    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True).stdout

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    (tmp_path / "benchmark").mkdir()
    (tmp_path / "src").mkdir()
    (tmp_path / "benchmark" / "items.val.jsonl").write_text("{}\n")
    git("add", ".")
    git("commit", "-qm", "data")
    data_c = git("rev-parse", "HEAD").strip()
    (tmp_path / "src" / "code.py").write_text("x = 1\n")
    git("add", ".")
    git("commit", "-qm", "code")
    head = git("rev-parse", "HEAD").strip()
    assert git_commit(tmp_path / "benchmark") == data_c != head  # last commit touching the data, not HEAD
    assert code_provenance(tmp_path) == {"code_commit": head, "code_dirty": False}
    (tmp_path / "src" / "code.py").write_text("x = 2\n")  # numbers produced from uncommitted code are flagged
    assert code_provenance(tmp_path) == {"code_commit": head, "code_dirty": True}
    assert git_commit(tmp_path / "nope") is None
