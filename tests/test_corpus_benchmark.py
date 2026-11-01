import json
from pathlib import Path

import jsonschema
import pytest

from ezhuthu.corpus import build_benchmark as bb
from ezhuthu.corpus.epidoc import Inscription

ROOT = Path(__file__).resolve().parents[1]
FIX = Path(__file__).parent / "fixtures" / "dharma"
SCHEMA = json.loads((ROOT / "contracts" / "benchmark-item.schema.json").read_text())
REAL = ROOT / "benchmark"
ITEM_FILES = ["items.train.jsonl", "items.val.jsonl", "items.test.jsonl", "items.test-hard.jsonl",
              "items.test-age.jsonl", "blank.jsonl"]


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("bench")
    lock = json.loads((FIX / "dharma.lock.json").read_text())
    stats = bb.build(lock, FIX / "raw", out)
    return out, stats


def test_fixture_build_counts(built):
    out, stats = built
    # template and non-TEI files are skipped: 2 pallava + 2 sii editions
    assert stats["inscriptions"] == 4
    # Tamil restorations: nanti, cantira (90001); nilam, kaḻa (90002, Sanskrit śrī excluded); viḷakku, pacu
    assert stats["items"] == 6
    assert stats["items_by_reason"] == {"lost": 5, "undefined": 1}
    # blank: [?3] in 90001 line 2, [?1] from the partly lost aksara, [?2] illegible in SII90002
    assert stats["blank_items"] == 3
    assert stats["age_set_items"] == 4  # all pallava items
    assert sum(p["items"] for p in stats["per_split"].values()) == 6
    card = (out / "DATA_CARD.md").read_text()
    assert "| 4 |" in card or "**4**" in card
    assert "CC BY-SA 4.0" in card


def test_fixture_items_validate_against_contract(built):
    out, _ = built
    n = 0
    for name in ITEM_FILES:
        for rec in _read(out / name):
            jsonschema.validate(rec, SCHEMA)
            n += 1
    assert n > 0


def test_fixture_item_fields(built):
    out, _ = built
    rows = {r["target"]: r for name in ("items.train.jsonl", "items.val.jsonl", "items.test.jsonl")
            for r in _read(out / name)}
    nanti = rows["nanti"]
    assert nanti["id"] == "DHARMA_INSPallava90001:1:0"
    assert nanti["left"].endswith("kō-vicaiya-")
    assert nanti["right"].startswith("-p-pōttaraiyarkku")
    assert nanti["gap_chars"] == 3  # na-n-ti
    assert nanti["age_set"] is True and nanti["dynasty"] == "Pallava"
    assert nanti["source_url"] == ("https://github.com/erc-dharma/tfa-pallava-epigraphy/blob/"
                                   "1111111111111111111111111111111111111111/DHARMA_INSPallava90001.xml")
    pacu = rows["pacu"]
    # short line: the previous line is prepended; the other restoration there is masked
    assert pacu["left"] == "uṭaiyār śrī-rājarājēśvaram-uṭaiyārkku nantā [?4] Oṉṟukku vaitta "
    assert pacu["age_set"] is False
    assert "śrī" not in rows  # Sanskrit textpart gives no items


def test_fixture_corpus_and_inscriptions(built):
    out, _ = built
    ins = _read(out / "inscriptions.jsonl")
    assert sorted(r["id"] for r in ins) == ["DHARMA_INSPallava90001", "DHARMA_INSPallava90002",
                                           "DHARMA_INSSII90001", "DHARMA_INSSII90002"]
    rec = next(r for r in ins if r["id"] == "DHARMA_INSPallava90001")
    assert rec["text_tamil"].startswith("ஸ்வஸ்தி ஶ்ரீ கோவிசையநந்திப்போத்தரையர்க்கு")
    assert rec["dharmalekha_url"] == "https://dharmalekha.info/texts/DHARMA_INSPallava90001"
    train_ids = {r["id"] for r in ins if r["split"] == "train"}
    for line in _read(out / "corpus_lines.jsonl"):
        assert line["inscription_id"] in train_ids


def test_splits_are_by_inscription_and_deterministic():
    def fake(i, col):
        return Inscription(id=f"I{i:04d}", title="", collection=col, path="", lang="tam-Latn",
                           licence=None, licence_url=None, summary=None, dynasty=None,
                           dynasty_source=None, ruler=None, regnal_year=None, approx_date=None)

    ins = [fake(i, "a" if i % 3 else "b") for i in range(300)]
    s1 = bb.assign_splits(ins)
    assert s1 == bb.assign_splits(list(reversed(ins)))  # order independent
    assert s1 != bb.assign_splits(ins, seed=14)
    counts = {k: list(s1.values()).count(k) for k in ("train", "val", "test")}
    assert counts == {"train": 240, "val": 30, "test": 30}


def test_mark_hard():
    train = [("T1", bb.norm_for_match("uṭaiyārkku nantā viḷakku Oṉṟukku vaitta")),
             ("T2", bb.norm_for_match("kāci ārāyiram"))]
    items = [
        {"inscription_id": "X", "left": "uṭaiyārkku nantā ", "target": "viḷakku", "right": " Oṉṟukku"},
        {"inscription_id": "X", "left": "maṟṟum ", "target": "viḷakku", "right": " pala Eḻuttu"},
        {"inscription_id": "T1", "left": "nantā ", "target": "viḷakku", "right": " Oṉṟukku"},
        {"inscription_id": "X", "left": "kāci ", "target": "ā", "right": "rāyiram"},
        {"inscription_id": "X", "left": "uṭaiyārkku nantā ", "target": "viḷakku", "right": " oṉṟukku"},
        {"inscription_id": "X", "left": "", "target": "", "right": ""},
    ]
    bb.mark_hard(items, train)
    # 1: parallel in another train inscription; 2: target present but context differs;
    # 3: the only parallel is its own inscription; 4: one-letter target with matching context;
    # 5: one-letter spelling difference in the context still matches; 6: no target -> never hard
    assert [it["hard"] for it in items] == [False, True, True, False, False, False]


# ---------------------------------------------------------------------------------------------------
# the committed artefacts (skipped until the benchmark has been built)

needs_real = pytest.mark.skipif(not (REAL / "items.test.jsonl").exists(), reason="benchmark not built")


@needs_real
def test_real_items_validate_and_splits_disjoint():
    seen: dict[str, str] = {}
    ids: set[str] = set()
    for name in ("items.train.jsonl", "items.val.jsonl", "items.test.jsonl", "blank.jsonl"):
        for rec in _read(REAL / name):
            jsonschema.validate(rec, SCHEMA)
            assert rec["id"] not in ids
            ids.add(rec["id"])
            if name != "blank.jsonl":
                assert rec["split"] == name.split(".")[1]
                assert rec["target"] and rec["kind"] == "supplied"
            else:
                assert rec["kind"] == "blank" and rec["target"] == ""
            assert seen.setdefault(rec["inscription_id"], rec["split"]) == rec["split"]
    meta = {r["id"]: r["split"] for r in _read(REAL / "inscriptions.jsonl")}
    assert all(meta[i] == s for i, s in seen.items())


@needs_real
def test_real_subsets_and_stats_agree():
    stats = json.loads((REAL / "stats.json").read_text())
    test = _read(REAL / "items.test.jsonl")
    hard = _read(REAL / "items.test-hard.jsonl")
    age = _read(REAL / "items.test-age.jsonl")
    assert len(hard) == stats["per_split"]["test"]["hard"] == sum(r["hard"] for r in test)
    assert len(age) == stats["per_split"]["test"]["age_set"]
    assert all(r["collection"] in bb.AGE_SET_COLLECTIONS for r in age)
    assert sum(p["items"] for p in stats["per_split"].values()) == stats["items"]
    train_ids = {r["id"] for r in _read(REAL / "inscriptions.jsonl") if r["split"] == "train"}
    assert {r["inscription_id"] for r in _read(REAL / "corpus_lines.jsonl")} <= train_ids
    assert str(stats["items"]) in (REAL / "DATA_CARD.md").read_text()
