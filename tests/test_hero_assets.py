"""The home hero photo and its reading: openly licensed, credited, small, and the real model output."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "app" / "web"
HERO_JSON = WEB / "src" / "hero" / "hero-reading.json"
RUNS = WEB / "src" / "hero" / "runs"
PUBLIC = WEB / "public" / "hero"
OPEN_LICENCES = {"CC0", "Public domain", "CC BY 2.0", "CC BY 3.0", "CC BY 4.0", "CC BY-SA 2.0", "CC BY-SA 3.0",
                 "CC BY-SA 4.0"}


def _hero() -> dict:
    return json.loads(HERO_JSON.read_text(encoding="utf-8"))


def test_photo_is_openly_licensed_and_attributed():
    photo = _hero()["photo"]
    assert photo["licence"] in OPEN_LICENCES
    attribution = (PUBLIC / "ATTRIBUTION.md").read_text(encoding="utf-8")
    for needle in (photo["author"], photo["licence"], photo["licence_url"].rstrip("/"), "commons.wikimedia.org"):
        assert needle in attribution
    # The credit is also shown in the app (StoneHero.tsx renders stoneHero.credit and the licence link).
    strings = (WEB / "src" / "i18n" / "strings.ts").read_text(encoding="utf-8")
    assert f"Photo: {photo['author']}" in strings


def test_image_variants_exist_and_fit_the_budget():
    widths = _hero()["photo"]["widths"]
    for w in widths:
        for ext in ("avif", "webp", "jpg"):
            f = PUBLIC / f"thanjavur-{w}.{ext}"
            assert f.exists(), f
            if w <= 800:  # what a 1x screen downloads
                assert f.stat().st_size < 300 * 1024, f
            assert b"Exif" not in f.read_bytes()[:4096], f"{f} still carries EXIF"


def test_reading_is_the_recorded_run():
    hero = _hero()
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    restore = json.loads((RUNS / "restore.json").read_text(encoding="utf-8"))
    assert [ln["iso"] for ln in hero["reading"]["lines"]] == [ln["text"] for ln in read["lines"]]
    assert hero["reading"]["final"]["confidence"] == read["confidence"]
    assert hero["restore"]["decisions"] == [g["decision"] for g in restore["response"]["gaps"]]
    assert restore["input"] == read["text"]
    assert len(hero["boxes"]) == len(read["lines"])
    assert hero["live_calls"]["reader"] + hero["live_calls"]["restorer"] <= 20


def test_no_edition_means_no_score_and_no_claims():
    hero = _hero()
    assert hero["edition"] is None and hero["cer"] is None
    assert "unverified" in hero["edition_note"]
    text = json.dumps(hero, ensure_ascii=False).lower()
    for banned in ("deciphered", "is correct", "are correct", "strands ai", "aws ai"):
        assert banned not in text
