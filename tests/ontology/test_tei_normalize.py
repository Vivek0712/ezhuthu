from pathlib import Path

from ezhuthu.ontology.matcher import VariantIndex
from ezhuthu.ontology.normalize import fold, key, slug
from ezhuthu.ontology.tei import inscription_id, iter_corpus, read_inscription

FIX = Path(__file__).parent / "fixtures" / "dharma"
COLL = FIX / "tfa-test-epigraphy"


def test_reader_lines_gaps_and_supplied_spans():
    ins = read_inscription(COLL / "DHARMA_INSTest00001.xml")
    assert ins.id == "DHARMA_INSTest00001"
    assert ins.title.startswith("Uttiramērūr, Vaikuṇṭha-Perumāḷ")
    assert ins.script_classes == ["tamil"]
    assert [ln.n for ln in ins.lines] == ["1", "2"]
    l1, l2 = ins.lines
    # <choice> keeps <reg>; <note> is dropped; supplied text stays in the reading
    assert "maturai koṇṭa kō-p-parakēcari-varmmarkku yāṇṭu" in l1.text
    assert "editorial note" not in l1.text
    assert [l1.text[a:b] for a, b in l1.supplied] == ["kō-p-para"]
    # gap with a quantity becomes [?N]; <surplus> is dropped; translation is not read
    assert l2.text == "yiṉāl [?3] vāriyam-āka Ēri-vāriyamum"
    assert "Prosperity" not in ins.text


def test_reader_unknown_gap_tilde_id_and_template_skipped():
    ids = [i.id for i in iter_corpus(FIX)]
    assert ids == ["DHARMA_INSTest00001", "DHARMA_INSTest00002"]
    ins = read_inscription(COLL / "~DHARMA_INSTest00002.xml")
    assert inscription_id(COLL / "~DHARMA_INSTest00002.xml") == "DHARMA_INSTest00002"
    assert "[?]" in ins.lines[2].text
    assert ins.place_names == ["Paḻuvūr"]


def test_fold_rules():
    assert fold("Kō-p-Parakēcari-varmmarkku") == "kopparakecarivarmarku"  # rC gemination folded
    assert fold("śrī svasti") == "crī cvacti"  # sibilants written c in Tamil
    assert key("kān=taḷūr-c cālai") == "kāntaḷūrccālai"
    assert slug("Uttiramērūr") == "uttiramerur"
    assert slug("Paḻuvūr") == "pazhuvur"


def test_variant_index_is_boundary_anchored_and_allows_case_endings():
    idx = VariantIndex()
    idx.add("ez:assembly/sabha", "sabhai")
    idx.add("ez:admin_unit/kottam", "kōṭṭattu")
    idx.add("ez:x/short", "ab")  # below MIN_KEY: ignored
    hits = idx.scan("Uttiramēru-c-caturvvedimaṅkalattu sabhaiyōm kāliyūr-k-kōṭṭattu")
    assert [(h.entity_id, h.surface) for h in hits] == [
        ("ez:assembly/sabha", "sabhaiyōm"),
        ("ez:admin_unit/kottam", "kōṭṭattu"),
    ]
    assert idx.scan("ucabhai") == []  # not at a word/compound boundary
