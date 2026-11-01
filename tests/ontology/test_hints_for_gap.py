"""hints_for_gap on fixture lines (real DHARMA lines with the expert-supplied text hidden)."""

from ezhuthu.ontology import lookup
from ezhuthu.ontology.letters import letter_count
from ezhuthu.ontology.normalize import key

# (left, hidden target, right, expected entity) -- from DHARMA_INSUttiramerur00001 line 1,
# DHARMA Rājarāja I meykkīrtti lines and a Toṇṭaimaṇṭalam address chain.
FIXTURE_LINES = [
    ("svasti śrī maturai koṇṭa kō-p-para", "kēcari-varmma", "rkku yāṇṭu paṉṉiraṇṭu", "ez:title/parakesarivarman"),
    ("svasti śrī tirumakaḷ pō", "la-p peru-nila-c celvi", "yun taṉakkē-y urimai", "ez:formula/tirumakal-pola"),
    ("jayaṅ-koṇṭa-cōḻa-maṇṭalattu kāli", "yūr-k-kō", "ṭṭattu taṉ-kūṟṟu", "ez:admin_unit/kaliyur-kottam"),
    ("Ivv-ūr ", "sabhai", "yōm", "ez:assembly/sabha"),
]


def test_fixture_gaps_are_restored_by_an_ontology_hint():
    for left, target, right, expected in FIXTURE_LINES:
        hints = lookup.hints_for_gap(left, right, gap_chars=letter_count(target))
        assert hints, left
        by_id = {h["id"]: h for h in hints}
        assert expected in by_id, (expected, [h["id"] for h in hints])
        h = by_id[expected]
        assert key(target) in [h["fill"], *h["alt_fills"]], (h["fill"], h["alt_fills"], key(target))
        assert {"id", "kind", "label"} <= by_id[expected].keys()  # restore-api ontology_hints shape


def test_royal_title_ranks_first_in_regnal_slot():
    hints = lookup.hints_for_gap("svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu", gap_chars=7)
    assert hints[0]["id"] == "ez:title/parakesarivarman"
    assert hints[0]["reason"] == "overlap"


def test_regnal_slot_without_anchor_proposes_royal_names_of_context_dynasty():
    hints = lookup.hints_for_gap("svasti śrī kō-vicaiya ", "ṟku yāṇṭu Oṉpatāvatu")
    slot = [h for h in hints if h["reason"] == "regnal_slot"]
    assert slot and all(h["fill"] is None for h in slot)
    assert all(lookup.entity(h["id"])["dynasty"] == "ez:dynasty/pallava" for h in slot)


def test_gap_length_filters_candidates():
    left, right = "svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu"
    short = lookup.hints_for_gap(left, right, gap_chars=2)
    assert all(1 <= letter_count(h["fill"]) <= 3 for h in short if h["fill"])
    assert not any("kecarivarma" in [h["fill"], *h["alt_fills"]] for h in short)
    assert any("kecarivarma" in [h["fill"], *h["alt_fills"]] for h in lookup.hints_for_gap(left, right, gap_chars=7))


def test_no_hints_without_anchor_or_slot():
    assert lookup.hints_for_gap("xyz ", " qqq") == []


def test_letter_count_matches_benchmark_unit():
    assert letter_count("kēcari-varmma") == 7  # கே ச ரி வ ர் ம் ம
    assert letter_count("kō-p-para") == 4  # கோ ப் ப ர
    assert letter_count("Āvatu") == 3
    assert letter_count("[?3]") == 0
