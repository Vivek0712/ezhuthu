"""OCR eval harness (python -m ezhuthu.eval.ocr): scoring, TEST-split selection, Wikisource cleaning. Offline."""

import json

from ezhuthu.eval import ocr


def test_cer_ignores_spacing_hyphens_and_gap_markers():
    e, n = ocr.cer_counts("kō-p-para [?3] kēcari", "kōppara kēcari")
    assert e == 0 and n == len("kōpparakēcari")
    e, n = ocr.cer_counts("svasti", "svasta")
    assert (e, n) == (1, 6)


def test_wer_counts_words():
    assert ocr.wer_counts("svasti śrī kō", "svasti śrī ko") == (1, 3)


def test_best_window_finds_the_visible_part_of_a_long_edition():
    ref = "svasti śrī matiraikoṇṭa kōpparakēcaripaṉmaṟku yāṇṭu mūṉṟāvatu"
    assert ocr.best_window(ref, "kōpparakēcari") == "kōpparakēcari"


def test_select_plates_uses_only_test_split_tamil_lines():
    plates = ocr.select_plates(8, seed=1)
    ins = {json.loads(x)["id"]: json.loads(x) for x in (ocr.ROOT / "benchmark" / "inscriptions.jsonl")
           .read_text(encoding="utf-8").splitlines()}
    assert len(plates) == 8 and len({p["inscription_id"] for p in plates}) == 8
    for p in plates:
        assert ins[p["inscription_id"]]["split"] == "test" and ins[p["inscription_id"]]["lang"] == "tam-Latn"
        assert len(p["lines"]) == 3 and all(ocr._good_line(x) for x in p["lines"])


def test_render_items_cover_levels_and_other_scripts():
    plates = ocr.select_plates(2, seed=1)
    items = ocr.render_items(plates, other_scripts=1)
    assert sorted({i["level"] for i in items if i["rendered_script"] == "tamil"}) == ["clean", "photo", "weathered"]
    assert {i["rendered_script"] for i in items} == {"tamil", "tamil-brahmi", "grantha"}
    brahmi = next(i for i in items if i["rendered_script"] == "tamil-brahmi")
    assert all(any(0x11000 <= ord(c) <= 0x1107F for c in ln) for ln in brahmi["render_lines"] if ln.strip())


def test_wikisource_text_strips_header_tables_and_templates():
    wt = ("<noinclude>{{rh||82|}}</noinclude>{| cellpadding=5\n|-\n| 1. || தமிழக மகளிர் || 5\n|}\n"
          "'''அப்படி''' {{gap}} [[link|என்றால்]]<noinclude>footer</noinclude>")
    out = ocr.wikisource_text(wt)
    assert "cellpadding" not in out and "82" not in out and "footer" not in out
    assert "தமிழக மகளிர்" in out and "அப்படி" in out and "என்றால்" in out


def test_real_manifest_records_licence_and_reference_for_every_image():
    man = json.loads(ocr.REAL_MANIFEST.read_text(encoding="utf-8"))
    assert len(man["images"]) >= 5
    for it in man["images"]:
        assert it["licence"] and it["author"] and it["page_url"], it["id"]
        assert it["reference"] and it["reference_source"], it["id"]
        assert any(x in it["licence"] for x in ("CC BY-SA", "CC0", "Public domain")), it["licence"]
