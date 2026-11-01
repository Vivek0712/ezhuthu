import pytest

from ezhuthu.ontology import lookup


def test_find_entities_on_uttiramerur_opening():
    text = (
        "svasti śrī maturai koṇṭa kō-p-parakēcari-varmmarkku yāṇṭu paṉṉiraṇṭu Āvatu "
        "Uttiramēru-c-caturvvedimaṅkalattu sabhaiyōm"
    )
    found = lookup.find_entities(text)
    ids = [f["id"] for f in found]
    assert ids[:4] == ["ez:formula/svasti-sri", "ez:formula/matirai-konta", "ez:title/parakesarivarman",
                       "ez:formula/regnal-year"]
    assert "ez:assembly/sabha" in ids
    sabha = next(f for f in found if f["id"] == "ez:assembly/sabha")
    assert text[sabha["start"]:sabha["end"]] == "sabhaiyōm"
    assert all({"id", "kind", "label", "label_ta"} <= f.keys() for f in found)


def test_valid_letters_by_stage_and_level():
    chola = lookup.valid_letters("chola-tamil")
    isos = [x["iso"] for x in chola]
    assert "ka" in isos and "ṉa" in isos and "ḵ" in isos
    e = next(x for x in chola if x["iso"] == "e")
    assert e["iso_values"] == ["e", "ē"]  # no length contrast before the 18th c.
    assert "ē" not in isos and "ō" not in isos
    assert any(x.get("grantha") and x["iso"] == "ja" for x in chola)

    vatt = lookup.valid_letters("vatteluttu")
    assert all(x["glyph"] is None for x in vatt)  # no Unicode; the app ships SVGs
    assert not any(x.get("grantha") for x in vatt)

    grantha = [x["iso"] for x in lookup.valid_letters("grantha")]
    assert {"kha", "dha", "śa", "r̥"} <= set(grantha)

    tb = lookup.valid_letters("L5")
    assert {x["stage"] for x in tb} == {"tamil-brahmi-1", "tamil-brahmi-2", "tamil-brahmi-3"}
    tb1 = {x["iso"]: x for x in tb if x["stage"] == "tamil-brahmi-1"}
    assert tb1["ḻa"]["glyph"] == "\U00011035" and tb1["ṟa"]["glyph"] == "\U00011036"
    assert "kha" not in tb1

    with pytest.raises(KeyError):
        lookup.valid_letters("indus")


def test_formulas_for_ruler_title_and_unknown():
    rr = [f["id"] for f in lookup.formulas_for("ez:ruler/rajaraja-i")]
    assert set(rr[:2]) == {"ez:formula/tirumakal-pola", "ez:formula/kantalur-calai"}
    assert "ez:formula/svasti-sri" in rr
    assert "ez:formula/tirumanni-valara" not in rr  # Rājendra I's, not Rājarāja I's

    pallava = [f["id"] for f in lookup.formulas_for("ez:ruler/nandivarman")]
    assert pallava[0] == "ez:formula/ko-vicaiya"
    with pytest.raises(KeyError):
        lookup.formulas_for("ez:ruler/nobody")


def test_entity_lookup():
    rec = lookup.entity("ez:ruler/rajaraja-i")
    assert rec["wikidata"] == "Q2128757" and rec["dynasty"] == "ez:dynasty/chola"
    assert rec["attested_in"]
    assert lookup.entity("ez:ruler/nobody") is None
