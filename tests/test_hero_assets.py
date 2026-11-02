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
    glyphs = json.loads((RUNS / "glyphs.json").read_text(encoding="utf-8"))
    restore = json.loads((RUNS / "restore.json").read_text(encoding="utf-8"))
    rows = hero["glyphs"]["rows"]
    assert [[g["ta"] for g in r["glyphs"]] for r in rows] == [[g["ta"] for g in r["glyphs"]] for r in glyphs["rows"]]
    assert [len(r) for r in hero["boxes"]] == [r["n_boxes"] for r in glyphs["rows"]]
    # The Restorer ran on the letter-by-letter reading, with each letter under the cut-off as a gap.
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from hero_read import glyph_is_gap, glyph_text

    assert restore["input"] == glyph_text(glyphs)
    n_gaps = sum(glyph_is_gap(g) for r in glyphs["rows"] for g in r["glyphs"])
    assert n_gaps == len(restore["response"]["gaps"]) == len(hero["restore"]["gaps"])
    assert hero["restore"]["decisions"] == [g["decision"] for g in restore["response"]["gaps"]]
    calls = hero["live_calls"]
    assert calls["reader"] + calls["glyphs"] + calls["restorer"] <= 60


def test_view_is_a_trimmed_subset():
    hero = _hero()
    view = json.loads((WEB / "src" / "hero" / "hero-view.json").read_text(encoding="utf-8"))
    assert view["boxes"] == hero["boxes"]
    assert view["letters"] == hero["glyphs"]["letters"]
    assert [[g["c"] for g in r["glyphs"]] for r in view["rows"]] == \
        [[g["confidence"] for g in r["glyphs"]] for r in hero["glyphs"]["rows"]]
    assert len(json.dumps(view)) < 0.3 * len(json.dumps(hero))


def test_no_edition_means_no_match_rate_and_no_claims():
    hero = _hero()
    assert hero["edition"] is None and hero["match_rate"] is None
    assert "not identified" in hero["edition_note"]
    text = json.dumps(hero, ensure_ascii=False).lower()
    for banned in ("deciphered", "is correct", "are correct", "strands ai", "aws ai", "goes to expert review"):
        assert banned not in text
