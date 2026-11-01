from ezhuthu.agent.data import (
    data_source,
    inscription_text,
    load_corpus_lines,
    load_items,
    parse_benchmark_name,
)
from ezhuthu.agent.ngram import CharNgram
from ezhuthu.agent.retrieval import ParallelIndex, align_fill
from ezhuthu.agent.text import (
    aksharas,
    fill_gaps,
    find_gaps,
    iso_to_tamil,
    non_iso_chars,
    render_level,
    tamil_to_iso,
)


def test_find_and_fill_gaps():
    t = "svasti śrī [?4] yāṇṭu [?] āvatu"
    gaps = find_gaps(t)
    assert [g.gap_chars for g in gaps] == [4, None]
    assert gaps[0].left == "svasti śrī " and gaps[1].right == " āvatu"
    assert fill_gaps(t, ["kōvi", None]) == "svasti śrī kōvi yāṇṭu [?] āvatu"


def test_tamil_roundtrip_keeps_gap_markers_and_dental_n():
    assert iso_to_tamil("nantā viḷakku [?6] ūr") == "நந்தா விளக்கு [?6] ஊர்"
    assert iso_to_tamil("perunilac") == "பெருநிலச்"  # ISO n is dental ந, not ன
    assert iso_to_tamil("mahādēvar") == "மஹாதேவர்"  # no superscript disambiguation digits
    assert tamil_to_iso("எழுத்து [?3]") == "eḻuttu [?3]"


def test_render_levels():
    assert render_level("kō", "L1")["glyph_text"] == "கோ"
    assert render_level("kōyil", "L2")["glyph_text"] == "கொயில"  # no e/o length, no pulli
    l4 = render_level("ka", "L4")
    assert l4["glyph_svg"].startswith("<svg") and l4["glyph_text"] is None and "ka" not in l4["glyph_svg"]
    assert render_level("ki", "L4") == {"glyph_text": None, "glyph_svg": None, "font": None}  # no drawing yet
    assert "\U00011300" not in render_level("ke", "L3")["glyph_text"]  # no candrabindu on short e
    assert render_level("ka", "L5")["glyph_text"] == "\U00011013"  # BRAHMI LETTER KA
    assert render_level("ka", "L3")["font"] == "Noto Sans Grantha"


def test_aksharas_and_letters():
    assert aksharas("kōvirājakēcari") == ["kō", "vi", "rā", "ja", "kē", "ca", "ri"]
    assert aksharas("ūr") == ["ū", "r"]
    assert non_iso_chars("paṉmaṟku") == set()
    assert non_iso_chars("pan@mx") == {"@", "x"}


def test_fixture_data_loads():
    assert data_source().is_fixture
    lines = load_corpus_lines()
    assert len(lines) == 13 and all(ln.text for ln in lines)
    items = load_items("test")
    assert len(items) == 8
    assert all(it.gap_chars == len(it.target) for it in items)
    assert len(load_items("test", subset="hard")) == 2
    assert len(load_items("test", subset="age")) == 2
    assert parse_benchmark_name("test-hard") == ("test", "hard")
    assert inscription_text("FIXTURE_CHOLA_101").count("\n") == 5  # reassembled from test items


def test_align_fill_between_anchors():
    line = "svasti śrī kōvirājakēcaripaṉmaṟku yāṇṭu irupattirāvatu"
    assert align_fill(line, "svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", 8) == "paṉmaṟku"
    # boundary space in the left context must survive normalisation
    assert align_fill("cantirātittavar celvatāka ivai paṉmāhēcurar rakṣai", "ivai paṉmāhēcurar ", "", 6) == "rakṣai"


def test_parallel_index_ranks_formula_and_excludes_own_inscription():
    idx = ParallelIndex(load_corpus_lines())
    ps = idx.search("mahādēvarkku nantā viḷakku ", " vaitta āṭu", gap_chars=7, k=3)
    assert ps[0].fill == "oṉṟukku" and ps[0].inscription_id == "FIXTURE_CHOLA_001"
    ps = idx.search("mahādēvarkku nantā viḷakku ", " vaitta āṭu", gap_chars=7, k=3,
                    exclude_inscription="FIXTURE_CHOLA_001")
    assert all(p.inscription_id != "FIXTURE_CHOLA_001" for p in ps)


def test_ngram_fills_seen_formula():
    lm = CharNgram().fit(ln.text for ln in load_corpus_lines())
    out = lm.fill("cantirātittavar ", " vaittēn", 9, k=5)
    assert out and out[0][0] == "celvatāka"
