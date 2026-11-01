"""Analysis of filled sheets, on synthetic ratings with a known generating model."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from ezhuthu.corpus.script import iso_to_tamil_display
from ezhuthu.expert.__main__ import main
from ezhuthu.expert.analyze import SheetError, analyze, analyze_reading, score_answer, to_markdown
from ezhuthu.expert.packet import RATING_COLUMNS, SampleSpec, build_packet, sample_items, write_csv
from ezhuthu.expert.synth import synth_ratings, synth_reading, write_synthetic

SPEC = SampleSpec(seed=3, n_blank=8, n_masked=8, n_reading=8, spares=2, min_context_letters=10)


@pytest.fixture()
def key(bench: Path, make_proposals) -> dict:
    sample = sample_items(bench, SPEC)
    return build_packet(sample, make_proposals(sample), seed=9, provenance={"router": "fake"})


def _write_ratings(tmp: Path, sheets: dict[str, list[dict[str, str]]]) -> list[Path]:
    paths = []
    for rater, rows in sheets.items():
        p = tmp / f"rating-{rater}.csv"
        write_csv(p, RATING_COLUMNS, rows)
        paths.append(p)
    return paths


def test_identical_raters_give_kappa_one(key, tmp_path):
    sheets = synth_ratings(key, ["SYN-A", "SYN-B", "SYN-C"], rater_sd=0.0, rater_bias_sd=0.0, p_cannot_judge=0,
                           p_flagged=0)
    res = analyze(_write_ratings(tmp_path, sheets), key, n_boot=200)
    ag = res["rating"]["agreement"]
    assert ag["fleiss_kappa"] == pytest.approx(1.0)
    assert ag["cohen_mean"] == pytest.approx(1.0) and ag["cohen_quadratic_mean"] == pytest.approx(1.0)
    assert ag["units_rated_by_2plus"] == 3 * len(key["rating"])
    assert res["synthetic"] is True


def test_noisy_raters_lower_agreement_and_recover_the_quality_gap(key, tmp_path):
    sheets = synth_ratings(key, [f"SYN-{i}" for i in range(5)], seed=4, q_edition=3.7, q_ai=1.8, unit_sd=0.3,
                           rater_sd=0.7, p_cannot_judge=0.05, p_flagged=0.05)
    res = analyze(_write_ratings(tmp_path, sheets), key, n_boot=300)["rating"]
    assert 0 < res["agreement"]["fleiss_kappa"] < 0.9
    # weighted kappa credits near misses on the ordinal scale
    assert res["agreement"]["cohen_quadratic_mean"] > res["agreement"]["cohen_mean"]
    g = res["by_group"]
    assert g["edition_fill (masked)"]["mean_rating"] > g["ai (masked)"]["mean_rating"] + 1
    assert res["masked"]["mean_edition_minus_best_ai"] > 0
    lo, hi = res["masked"]["mean_edition_minus_best_ai_ci95"]
    assert lo <= res["masked"]["mean_edition_minus_best_ai"] <= hi
    c = res["counts"]
    assert c["cannot_judge"] > 0 and c["flagged_ratings"] > 0
    # independent recount: a rater's "knew this text" on any row of an item flags all their rows of that item
    flagged = {(r["rater_id"], r["item_code"]) for rows in sheets.values() for r in rows if r["knew_this_text_y"]}
    main_set = [r for rows in sheets.values() for r in rows
                if (r["rater_id"], r["item_code"]) not in flagged and r["rating_1_to_4"]]
    assert c["main_set_ratings"] == len(main_set) < c["ratings"] - c["cannot_judge"]


def test_sheet_validation_errors(key, tmp_path):
    sheets = synth_ratings(key, ["R1"], p_cannot_judge=0, p_flagged=0)
    rows = sheets["R1"]
    for bad, msg in (("5", "not 1-4"), ("2.5", "not 1-4"), ("x", "not 1-4")):
        rows[0]["rating_1_to_4"] = bad
        with pytest.raises(SheetError, match=msg):
            analyze(_write_ratings(tmp_path, {"R1": rows}), key)
    rows[0]["rating_1_to_4"] = "3"
    with pytest.raises(SheetError, match="rated twice"):
        analyze(_write_ratings(tmp_path, {"R1": [*rows, rows[0]]}), key)
    with pytest.raises(SheetError, match="not in this packet"):
        analyze(_write_ratings(tmp_path, {"R1": [{**rows[0], "item_code": "P99"}]}), key)
    # a real rater mixed with synthetic ones is refused
    mixed = {"R1": rows, "SYN-X": synth_ratings(key, ["SYN-X"])["SYN-X"]}
    with pytest.raises(SheetError, match="mixed"):
        analyze(_write_ratings(tmp_path, mixed), key)
    # blank ratings are counted, not invented
    rows[1]["rating_1_to_4"] = ""
    res = analyze(_write_ratings(tmp_path, {"R1": rows}), key)
    assert res["rating"]["counts"]["blank_unrated"] == 1
    assert res["synthetic"] is False


def test_reading_study_scoring(key, tmp_path):
    raters = [f"SYN-{i}" for i in range(4)]
    sheets = synth_reading(key, raters, p_unaided=0.0, p_assisted=1.0)
    rows = [r for rs in sheets.values() for r in rs]
    res = analyze_reading(rows, key, n_boot=200)
    assert res["unaided"]["exact_match"] == 0.0 and res["ai_assisted"]["exact_match"] == 1.0
    assert res["paired_items"]["mean_diff_assisted_minus_unaided"] == pytest.approx(1.0)
    assert res["paired_items"]["items"] == len(key["reading"])
    assert res["paired_items"]["items_better_with_ai"] == len(key["reading"])
    assert all(v == pytest.approx(1.0) for v in res["per_rater_diff_assisted_minus_unaided"].values())
    # Tamil-script answers and editorial hyphens score like ISO
    t = key["reading"][0]["target"]
    assert score_answer(iso_to_tamil_display(t), t) == (True, 0.0)
    assert score_answer(t.replace("-", ""), t)[0]
    assert score_answer("", t) == (False, 1.0)
    ok, cer = score_answer("zz", t)
    assert not ok and 0 < cer <= 1
    # flagged answers are excluded and counted
    rows[0]["knew_this_text_y"] = "y"
    assert analyze_reading(rows, key, n_boot=50)["counts"]["flagged_excluded"] == 1
    with pytest.raises(SheetError, match="condition"):
        analyze_reading([{**rows[1], "condition": "maybe"}], key)


def test_markdown_carries_synthetic_banner(key, tmp_path):
    paths = write_synthetic(key, 3, tmp_path / "syn", seed=1)
    res = analyze([tmp_path / "syn"], key, n_boot=100)
    md = to_markdown(res)
    assert "SYNTHETIC RATINGS" in md and "Fleiss' kappa" in md and "Reading study" in md
    assert len(paths) == 6


def test_cli_end_to_end_offline(bench, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("EZHUTHU_BENCHMARK_DIR", str(bench))
    monkeypatch.delenv("EZHUTHU_FIXTURES", raising=False)
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    # the restorer needs a train-only retrieval corpus next to the items
    (bench / "corpus_lines.jsonl").write_text(
        "".join(f'{{"inscription_id": "DHARMA_INSTrain{i:03d}", "line_n": "1", "split": "train", '
                f'"text": "svasti śrī kō rāja kēcari panmarkku yāṇṭu {i} tiru nāḷ oṉṟukku"}}\n' for i in range(30)),
        encoding="utf-8")
    k = tmp_path / "kit"
    assert main(["sample", "--out", str(k / "sample.jsonl"), "--seed", "1", "--n-blank", "3", "--n-masked", "3",
                 "--n-reading", "2", "--spares", "1"]) == 0
    assert main(["propose", "--sample", str(k / "sample.jsonl"), "--out", str(k / "proposals.jsonl")]) == 0
    assert main(["propose", "--sample", str(k / "sample.jsonl"), "--out", str(k / "x.jsonl"),
                 "--router", "sonnet"]) == 2  # no EZHUTHU_LIVE: refused, no Bedrock call
    assert main(["generate", "--sample", str(k / "sample.jsonl"), "--proposals", str(k / "proposals.jsonl"),
                 "--raters", "R1,R2", "--out", str(k / "packet"), "--options", "2"]) == 0
    keyp = k / "packet/coordinator/key.json"
    assert keyp.exists() and (k / "packet/raters/R2/rating-R2.html").exists()
    assert main(["synth", "--key", str(keyp), "--out", str(k / "syn"), "--raters", "3"]) == 0
    assert main(["analyze", "--key", str(keyp), "--out", str(k / "res"), "--n-boot", "50", str(k / "syn")]) == 0
    assert "SYNTHETIC RATINGS" in (k / "res/expert-validation.md").read_text()
    # a sheet with a bad value gives exit code 2 and a message, not a traceback
    bad = k / "bad.csv"
    rows = list(csv.DictReader((k / "syn/rating-SYN-R1.csv").read_text(encoding="utf-8-sig").splitlines()))
    rows[0]["rating_1_to_4"] = "9"
    write_csv(bad, RATING_COLUMNS, rows)
    assert main(["analyze", "--key", str(keyp), "--out", str(k / "res2"), str(bad)]) == 2
    assert "sheet error" in capsys.readouterr().err
