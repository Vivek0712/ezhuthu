"""The app's try-it samples (app/web/src/samples/*.json, built by scripts/build_samples.py).

Leakage guard: a sample shown in the app and sent to /api/restore must never come from a val or test inscription
(benchmark/DATA_CARD.md, "Leakage"), and every gap in it must be a train blank, not a held-out item.
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


def test_no_val_or_test_inscription_in_samples(samples, images, splits, held_out_ids):
    assert held_out_ids, "held-out ids must load"
    for s in samples:
        assert splits[s["inscription_id"]] == "train", s["id"]
        assert s["split"] == "train"
        assert s["inscription_id"] not in held_out_ids, s["id"]
    for im in images:
        assert splits[im["inscription_id"]] == "train", im["id"]
        assert im["inscription_id"] not in held_out_ids, im["id"]


def test_every_gap_is_a_train_blank(samples):
    blanks = {b["id"]: b for b in _read(BENCH / "blank.jsonl")}
    held_items = {r["id"] for n in ("items.val.jsonl", "items.test.jsonl") for r in _read(BENCH / n)}
    for s in samples:
        assert len(s["blank_ids"]) == s["gaps"] == len(GAP_RE.findall(s["text_iso"])), s["id"]
        for bid in s["blank_ids"]:
            b = blanks[bid]
            assert b["split"] == "train" and b["kind"] == "blank" and b["inscription_id"] == s["inscription_id"]
            assert bid not in held_items


def test_the_api_accepts_every_sample(samples):
    for s in samples:
        assert check_text(s["text_iso"], script="iso15919") == s["text_iso"]
        assert check_text(s["text_tamil"], script="tamil") == s["text_tamil"]
        assert len(GAP_RE.findall(s["text_tamil"])) == s["gaps"]


def test_gallery_shape_credit_and_spread(samples):
    assert 10 <= len(samples) <= 14
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
    ids = {s["id"] for s in samples}
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
