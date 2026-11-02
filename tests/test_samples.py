"""The app's try-it samples (app/web/src/samples/*.json, built by scripts/build_samples.py).

Leakage guard (benchmark/DATA_CARD.md, "Leakage"; eval/reports/2026-11-02-samples.md):
- no sample ever comes from a TEST inscription;
- "masked" samples hide one VAL item's target (VAL only: train would be leaky, the 5-gram and retrieval read it) and
  are exactly the items the pre-declared rule in select_masked() draws;
- "unsolved" samples are TRAIN passages whose every gap is a train blank, not a held-out item.
"""
from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

from ezhuthu.api.limits import check_text

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
SAMPLES = ROOT / "app" / "web" / "src" / "samples"
PUBLIC = ROOT / "app" / "web" / "public"
GAP_RE = re.compile(r"\[\?(\d{1,3})?\]")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="module")
def samples() -> list[dict]:
    return json.loads((SAMPLES / "samples.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def images() -> list[dict]:
    return json.loads((SAMPLES / "sample-images.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def splits() -> dict[str, str]:
    return {r["id"]: r["split"] for r in _read(BENCH / "inscriptions.jsonl")}


@pytest.fixture(scope="module")
def held_out_ids(splits) -> set[str]:
    ids = {i for i, s in splits.items() if s in ("val", "test")}
    for name in ("items.val.jsonl", "items.test.jsonl", "items.test-hard.jsonl", "items.test-age.jsonl"):
        ids |= {r["inscription_id"] for r in _read(BENCH / name)}
    return ids


def _build_module():
    spec = importlib.util.spec_from_file_location("build_samples", ROOT / "scripts" / "build_samples.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_no_test_inscription_in_samples_masked_are_val_unsolved_are_train(samples, images, splits, held_out_ids):
    assert held_out_ids, "held-out ids must load"
    test_ids = {r["inscription_id"] for n in ("items.test.jsonl", "items.test-hard.jsonl", "items.test-age.jsonl")
                for r in _read(BENCH / n)}
    val_items = {r["id"]: r for r in _read(BENCH / "items.val.jsonl")}
    assert {s["group"] for s in samples} == {"masked", "unsolved"}
    for s in samples:
        assert splits[s["inscription_id"]] != "test" and s["inscription_id"] not in test_ids, s["id"]
        if s["group"] == "masked":
            assert s["split"] == "val" and splits[s["inscription_id"]] == "val", s["id"]
            item = val_items[s["item_id"]]
            assert item["split"] == "val" and item["inscription_id"] == s["inscription_id"]
            assert s["edition_reading"]["text_iso"] == item["target"]
        else:
            assert s["group"] == "unsolved"
            assert splits[s["inscription_id"]] == "train" and s["split"] == "train", s["id"]
            assert s["inscription_id"] not in held_out_ids, s["id"]
            assert s["edition_reading"] is None and s["item_id"] is None
    for im in images:
        assert splits[im["inscription_id"]] == "train", im["id"]
        assert im["inscription_id"] not in held_out_ids, im["id"]


def test_every_unsolved_gap_is_a_train_blank(samples):
    blanks = {b["id"]: b for b in _read(BENCH / "blank.jsonl")}
    held_items = {r["id"] for n in ("items.val.jsonl", "items.test.jsonl") for r in _read(BENCH / n)}
    for s in samples:
        if s["group"] != "unsolved":
            assert s["blank_ids"] == []
            continue
        assert len(s["blank_ids"]) == s["gaps"] == len(GAP_RE.findall(s["text_iso"])), s["id"]
        for bid in s["blank_ids"]:
            b = blanks[bid]
            assert b["split"] == "train" and b["kind"] == "blank" and b["inscription_id"] == s["inscription_id"]
            assert bid not in held_items


def test_masked_samples_are_the_pre_declared_draw(samples):
    """Rule 1-3 of eval/reports/2026-11-02-samples.md: the gallery's masked items are exactly select_masked()'s."""
    mod = _build_module()
    drawn = mod.select_masked()
    masked = [s for s in samples if s["group"] == "masked"]
    assert [s["item_id"] for s in masked] == [it["id"] for it in drawn]
    assert 8 <= len(masked) <= 10
    assert len({s["inscription_id"] for s in masked}) == len(masked)
    for s, it in zip(masked, drawn):
        assert 1 <= it["gap_chars"] <= mod.MASKED_MAX_GAP
        assert s["gaps"] == 1 and [m.group(0) for m in GAP_RE.finditer(s["text_iso"])] == [f"[?{it['gap_chars']}]"]
        assert s["hard"] == it["hard"]
        # The hidden reading itself never appears in the text sent to the restorer.
        assert s["text_iso"] == mod.masked_text(it)


def test_every_sample_has_its_live_recording(samples):
    from ezhuthu.corpus.script import normalise_for_scoring

    rec = json.loads((SAMPLES / "recorded-restores.json").read_text(encoding="utf-8"))
    assert rec["meta"]["bedrock"]["calls"] <= 40
    assert set(rec["samples"]) == {s["id"] for s in samples}
    for s in samples:
        got = rec["samples"][s["id"]]
        assert got["text_iso"] == s["text_iso"]
        gaps = got["response"]["gaps"]
        assert len(gaps) == s["gaps"] == len(s["recorded"]["gaps"])
        if s["group"] == "masked":
            g, want = gaps[0], s["edition_reading"]["norm"]
            best = g["candidates"][g["chosen"]]["text"] if g["decision"] == "fill" else None
            outcome = "open" if best is None else "match" if normalise_for_scoring(best) == want else "differs"
            assert s["recorded"]["gaps"][0]["outcome"] == outcome


def test_the_api_accepts_every_sample(samples):
    for s in samples:
        assert check_text(s["text_iso"], script="iso15919") == s["text_iso"]
        assert check_text(s["text_tamil"], script="tamil") == s["text_tamil"]
        assert len(GAP_RE.findall(s["text_tamil"])) == s["gaps"]


def test_gallery_shape_credit_and_spread(samples):
    assert 10 <= len(samples) <= 14
    assert 2 <= sum(s["group"] == "unsolved" for s in samples) <= 3
    assert len({s["id"] for s in samples}) == len(samples)
    assert len({s["era"] for s in samples}) >= 4
    for s in samples:
        for k in ("title_ta", "title_en", "place_ta", "place_en", "why_ta", "why_en", "edition_title"):
            assert s[k].strip(), (s["id"], k)
        assert re.search(r"[஀-௿]", s["title_ta"]) and re.search(r"[஀-௿]", s["why_ta"])
        assert s["licence"] == "CC BY-SA 4.0"
        assert s["licence_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
        assert s["dharma_url"] == f"https://dharmalekha.info/texts/{s['inscription_id']}"
        assert s["source_url"].startswith("https://github.com/erc-dharma/")
        assert s["learn_level"] in {"L1", "L2", "L3", "L4", "L5"}


def test_sample_images_exist_and_are_attributed(images, samples):
    ids = {p["id"] for p in _build_module().PICKS}  # source passages; not all are in the gallery
    attribution = (PUBLIC / "samples" / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert 3 <= len(images) <= 5
    for im in images:
        assert im["sample"] in ids
        path = PUBLIC / im["file"]
        assert path.is_file() and path.stat().st_size < 400_000, im["file"]
        assert path.read_bytes()[:3] == b"\xff\xd8\xff", "JPEG"
        assert im["expected_text"] == "\n".join(im["lines"])
        assert "CC BY-SA 4.0" in im["credit"] and "Synthetic render" in im["credit"]
        assert im["file"].split("/")[-1] in attribution and im["inscription_id"] in attribution


def test_committed_json_matches_the_generator():
    assert _build_module().main(["--check"]) == 0
