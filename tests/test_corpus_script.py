import pytest

from ezhuthu.corpus.script import (
    convert,
    count_aksharas,
    iso_to_grantha,
    iso_to_tamil,
    iso_to_tamil_brahmi,
    normalize_iso,
)


@pytest.mark.parametrize(
    ("iso", "tamil"),
    [
        ("maturai", "மதுரை"),
        ("koṇṭa", "கொண்ட"),
        ("paṉṉiraṇṭu", "பன்னிரண்டு"),  # Aksharamukha gives the wrong பந்நிரண்டு here
        ("yāṇṭu", "யாண்டு"),
        ("vaḷḷal", "வள்ளல்"),
        ("kaḻaṟ", "கழற்"),
        ("tamiḻ", "தமிழ்"),
        ("svasti śrī", "ஸ்வஸ்தி ஶ்ரீ"),
        ("kō-p-parakēcari-varmarkku", "கோப்பரகேசரிவர்மர்க்கு"),
        ("vāriyam-āka", "வாரியமாக"),  # hyphen is transparent, vowel attaches
        ("Āvatu", "ஆவது"),
        ("nāṭṭu-k-Ilaṅkai", "நாட்டுக்இலங்கை"),  # upper-case vowel stays independent
        ("Uttiramēru-c·-catur", "உத்திரமேருச்சதுர்"),  # engraved puḷḷi
        ("Āṭṭ’ oru", "ஆட்ட் ஒரு"),
        ("kaïlāsa", "கஇலாஸ"),
        ("kr̥ṣṇa", "க்ருஷ்ண"),
        ("vaiṣṇava", "வைஷ்ணவ"),
        ("nilattu", "நிலத்து"),
        ("ñāṉam", "ஞானம்"),
        ("ceṅkōl", "செங்கோல்"),
        ("ponnai", "பொந்நை"),  # dental n is kept as ந (DHARMA distinguishes n and ṉ)
    ],
)
def test_iso_to_tamil_known_words(iso, tamil):
    assert iso_to_tamil(iso) == tamil


def test_tamil_numerals_and_gap_markers():
    assert iso_to_tamil("yāṇṭu 2 10 4 [?3] Āvatu") == "யாண்டு ௨ ௰ ௪ [?3] ஆவது"
    assert iso_to_tamil("100 1000") == "௱ ௲"
    assert iso_to_tamil("[?] ka [?12]") == "[?] க [?12]"


def test_keep_hyphens():
    assert iso_to_tamil("kō-p-para", keep_hyphens=True) == "கோ-ப்-பர"


@pytest.mark.parametrize(
    ("iso", "n"),
    [("maturai", 3), ("paṉṉiraṇṭu", 6), ("kaḻaṟ", 3), ("r", 1), ("kō-p-para", 4), ("Āvatu", 3),
     ("svasti", 4), ("śrī", 2), ("[?3] ka", 1), ("a", 1), ("", 0), ("10", 0)],
)
def test_count_aksharas(iso, n):
    # equals the number of Tamil letters in the converted text
    assert count_aksharas(iso) == n


def test_count_matches_tamil_letters():
    import unicodedata

    for word in ["maturai koṇṭa", "paṉṉiraṇṭu Āvatu", "vāriyam-āka", "kaḻaṟ", "nāṭṭu-k-Ilaṅkai"]:
        tamil = iso_to_tamil(word)
        letters = [c for c in tamil if unicodedata.category(c) == "Lo"]
        assert count_aksharas(word) == len(letters), word


def test_normalize_iso_marks_independent_vowels():
    assert normalize_iso("nāṭṭu-k-Ilaṅkai") == "nāṭṭuk_ilaṅkai"
    assert normalize_iso("Āṭṭ’ oru") == "_āṭṭ oru"


def test_tamil_brahmi():
    # Brahmi block: ka U+11013, virama U+11046, ṉa U+11037 (Tamil-specific), ṟa U+11036, ḻa U+11035
    assert iso_to_tamil_brahmi("kaḻaṟ") == "\U00011013\U00011035\U00011036\U00011046"
    assert iso_to_tamil_brahmi("paṉṉiraṇṭu") == "𑀧𑀷𑁆𑀷𑀺𑀭𑀡𑁆𑀝𑀼"
    assert iso_to_tamil_brahmi("[?2] Āvatu") == "[?2] 𑀆𑀯𑀢𑀼"


def test_grantha():
    assert iso_to_grantha("svasti śrī") == "𑌸𑍍𑌵𑌸𑍍𑌤𑌿 𑌶𑍍𑌰𑍀"
    assert iso_to_grantha("vaḷḷal") == "𑌵𑌳𑍍𑌳𑌲𑍍"


def test_convert_dispatch():
    assert convert("ka", "tamil") == "க"
    assert convert("ka", "tamil-brahmi") == "\U00011013"
    assert convert("ka", "grantha") == "\U00011315"
    with pytest.raises(ValueError):
        convert("ka", "devanagari")
