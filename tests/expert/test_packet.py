"""Sampling, blinding and sheet generation of the expert-validation kit."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

import pytest

from ezhuthu.expert.packet import (
    RATING_COLUMNS,
    READING_COLUMNS,
    SampleSpec,
    build_packet,
    display_iso,
    propose,
    reading_forms,
    sample_items,
    write_packet,
)

SPEC = SampleSpec(seed=11, n_blank=6, n_masked=6, n_reading=6, spares=2, max_per_inscription=2,
                  min_context_letters=10)


def test_sample_is_seeded_disjoint_and_split_safe(bench: Path):
    a = sample_items(bench, SPEC)
    b = sample_items(bench, SPEC)
    c = sample_items(bench, SampleSpec(**{**SPEC.__dict__, "seed": 12}))
    assert a == b
    assert [r["id"] for r in a] != [r["id"] for r in c]
    roles = Counter((r["role"], r["spare"]) for r in a)
    assert roles[("rating-blank", False)] == 6 and roles[("rating-masked", False)] == 6
    assert roles[("reading", False)] == 6 and roles[("reading", True)] == 0
    assert len({r["id"] for r in a}) == len(a)  # reading items never reused as rating items
    assert max(Counter(r["inscription_id"] for r in a).values()) <= 2
    assert all(r["split"] in ("test", "val") for r in a if r["role"] == "rating-blank")
    assert all(r["split"] == "test" and r["target"] for r in a if r["role"] != "rating-blank")
    with pytest.raises(ValueError, match="not enough eligible"):
        sample_items(bench, SampleSpec(n_blank=500))


def _packet(bench: Path, make_proposals, **kw):
    sample = sample_items(bench, SPEC)
    return sample, build_packet(sample, make_proposals(sample), seed=5, **kw)


def test_every_item_has_the_same_number_of_options_and_one_edition_fill_when_masked(bench: Path, make_proposals):
    _sample, key = _packet(bench, make_proposals, options_per_item=3)
    assert key["meta"]["n_rating_masked"] == 6 and key["meta"]["n_rating_blank"] == 6
    assert key["meta"]["n_reading"] == 6 and not key["meta"]["short"]
    for it in key["rating"]:
        assert len(it["options"]) == 3
        assert [o["label"] for o in it["options"]] == ["A", "B", "C"]
        shown = [o["text"] for o in it["options"]]
        assert len(set(shown)) == 3
        origins = Counter(o["origin"] for o in it["options"])
        if it["kind"] == "masked":
            assert origins["expert"] == 1
            exp = next(o for o in it["options"] if o["origin"] == "expert")
            assert exp["text"] == display_iso(it["target"])
        else:
            assert origins == {"ai": 3}
    # the edition fill that retrieval also proposed is shown once and flagged
    flagged = [o for it in key["rating"] for o in it["options"] if o.get("also_proposed_by_ai")]
    assert 1 <= len(flagged) <= 2
    # the edition fill is not always under the same label
    labels = Counter(o["label"] for it in key["rating"] for o in it["options"] if o["origin"] == "expert")
    assert len(labels) >= 2


def test_spares_replace_items_with_too_few_proposals(bench: Path, make_proposals):
    sample = sample_items(bench, SPEC)
    props = make_proposals(sample)
    first_blank = next(r["id"] for r in sample if r["role"] == "rating-blank")
    for p in props:
        if p["id"] == first_blank:
            p["proposals"] = p["proposals"][:1]
    key = build_packet(sample, props, seed=5)
    assert key["meta"]["n_rating_blank"] == 6
    assert key["dropped"][0]["id"] == first_blank
    assert first_blank not in {it["id"] for it in key["rating"]}


def test_display_iso_hides_edition_typography():
    assert display_iso("Iraṇṭu-k-kaḻañcu=") == "iraṇṭukkaḻañcu"
    assert display_iso("  t'  ") == "t'"
    assert display_iso("nan=ti-p ‡pōttaraiyar") == "nantip pōttaraiyar"


def _read_csv(p: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(p.read_text(encoding="utf-8-sig").splitlines()))


def test_sheets_are_blind_bilingual_and_complete(bench: Path, tmp_path: Path, make_proposals):
    _, key = _packet(bench, make_proposals)
    out = tmp_path / "packet"
    written = write_packet(key, ["R1", "R2", "R3"], out)
    assert (out / "coordinator" / "key.json").exists()
    assert json.loads((out / "coordinator" / "assignments.json").read_text())[1]["reading_form"] == "B"
    secrets = {"sonnet", "opus", "ngram", "parallel", "retrieval", "masked", "blank", "expert", "edition fill",
               "also_proposed", "confidence"}
    for it in key["rating"]:
        secrets.add(it["id"])
        secrets.add(it["inscription_id"] + ":")
    for p in written["rating"]:
        raw = p.read_bytes()
        text = raw.decode("utf-8-sig").lower()
        for s in secrets:
            assert s.lower() not in text, f"{p.name} leaks {s!r}"
        if p.suffix == ".csv":
            assert raw.startswith(b"\xef\xbb\xbf")  # BOM for Excel
            rows = _read_csv(p)
            assert list(rows[0]) == RATING_COLUMNS
            assert len(rows) == 3 * len(key["rating"])
            assert Counter(r["item_code"] for r in rows) == {it["code"]: 3 for it in key["rating"]}
            assert all(any("஀" <= ch <= "௿" for ch in r["proposal_tamil"]) for r in rows)
            assert all(r["source_url"].startswith("https://") for r in rows)
            assert all(r["rating_1_to_4"] == "" for r in rows)
        else:
            assert '<html lang="ta">' in text and "instructions" in text and "வழிமுறை" in raw.decode("utf-8")
    # raters see the items in different orders, with the same codes
    r1 = [r["item_code"] for r in _read_csv(out / "raters/R1/rating-R1.csv")][::3]
    r2 = [r["item_code"] for r in _read_csv(out / "raters/R2/rating-R2.csv")][::3]
    assert sorted(r1) == sorted(r2) and r1 != r2
    with pytest.raises(ValueError, match="rater id"):
        write_packet(key, ["Dr Some Name"], tmp_path / "bad")


def test_reading_forms_are_counterbalanced(bench: Path, tmp_path: Path, make_proposals):
    _, key = _packet(bench, make_proposals)
    forms = reading_forms(key)
    for f in ("A", "B"):
        assert sorted(it["code"] for _, _, it in forms[f]) == sorted(it["code"] for it in key["reading"])
        conds = [c for _, c, _ in forms[f]]
        assert conds == sorted(conds, key=lambda c: c != "unaided")  # unaided block first
    cond_a = {it["code"]: c for _, c, it in forms["A"]}
    cond_b = {it["code"]: c for _, c, it in forms["B"]}
    assert all(cond_a[k] != cond_b[k] for k in cond_a)
    write_packet(key, ["R1", "R2"], tmp_path / "p")
    rows = _read_csv(tmp_path / "p/raters/R1/reading-R1.csv")
    assert list(rows[0]) == READING_COLUMNS
    for r in rows:
        assert (r["ai_suggestions_iso"] == "") == (r["condition"] == "unaided")
    text = (tmp_path / "p/raters/R1/reading-R1.csv").read_text(encoding="utf-8-sig")
    for it in key["reading"]:
        assert it["id"] not in text


def test_propose_offline_and_live_guards(bench: Path, monkeypatch):
    sample = sample_items(bench, SPEC)[:2]
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    with pytest.raises(RuntimeError, match="EZHUTHU_LIVE=1"):
        propose(sample, router="sonnet")
    monkeypatch.setenv("EZHUTHU_LIVE", "1")
    with pytest.raises(RuntimeError, match="cap is 1"):
        propose(sample, router="sonnet", max_llm_calls=1)


PILOT = Path(__file__).resolve().parents[2] / "docs" / "expert-validation" / "pilot"


@pytest.mark.skipif(not (PILOT / "sample.jsonl").exists(), reason="pilot packet not present")
def test_committed_pilot_packet_is_reproducible_and_blind(tmp_path: Path):
    from ezhuthu.expert.packet import read_jsonl

    key = json.loads((PILOT / "packet/coordinator/key.json").read_text(encoding="utf-8"))
    rebuilt = build_packet(read_jsonl(PILOT / "sample.jsonl"), read_jsonl(PILOT / "proposals.jsonl"),
                           seed=key["meta"]["seed"])
    assert rebuilt["rating"] == key["rating"] and rebuilt["reading"] == key["reading"]
    write_packet(rebuilt, ["R1"], tmp_path)
    for name in ("rating-R1.csv", "reading-R1.csv", "rating-R1.html", "reading-R1.html"):
        assert (tmp_path / "raters/R1" / name).read_bytes() == (PILOT / "packet/raters/R1" / name).read_bytes()
    sheet = (PILOT / "packet/raters/R1/rating-R1.csv").read_text(encoding="utf-8-sig").lower()
    for word in ("sonnet", "ngram", "parallel", "expert", "masked", "blank"):
        assert word not in sheet
    assert all(len(it["options"]) == 3 for it in key["rating"])
    # every passage is from a val/test inscription, none of which is in the train-only retrieval corpus
    assert all(it["split"] in ("test", "val") for it in key["rating"] + key["reading"])
