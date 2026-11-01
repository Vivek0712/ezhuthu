from pathlib import Path

from ezhuthu.corpus.epidoc import infer_dynasty, is_tei, parse_file

RAW = Path(__file__).parent / "fixtures" / "dharma" / "raw"
PALLAVA = RAW / "tfa-pallava-epigraphy"
SII = RAW / "tfa-sii-epigraphy" / "texts"


def _line(ins, n):
    return next(ln for ln in ins.lines if ln.n == n)


def _spans(line, kind):
    return [line.text[s.start:s.end] for s in line.spans_of(kind)]


def test_metadata():
    ins = parse_file(PALLAVA / "DHARMA_INSPallava90001.xml", "tfa-pallava-epigraphy")
    assert ins.id == "DHARMA_INSPallava90001"
    assert ins.title.startswith("Tiruveḷḷaṟai")
    assert ins.licence == "CC BY-SA 4.0"
    assert ins.summary == "Gift of a lamp (test fixture)."
    assert (ins.dynasty, ins.dynasty_source) == ("Pallava", "collection")
    assert ins.ruler == "Nandivarman"
    assert ins.regnal_year == 10
    assert ins.approx_date == "741 CE"
    assert ins.lang == "tam-Latn"


def test_lines_supplied_unclear_gap_choice():
    ins = parse_file(PALLAVA / "DHARMA_INSPallava90001.xml", "tfa-pallava-epigraphy")
    assert [ln.n for ln in ins.lines] == ["1", "2", "3", "4"]
    l1 = _line(ins, "1")
    assert l1.text == "svasti śrī kō-vicaiya-nanti-p-pōttaraiyarkku yāṇṭu 10 Āvatu"
    assert _spans(l1, "supplied") == ["nanti"]
    l2 = _line(ins, "2")
    # <unclear> kept as text, <gap quantity=3> -> [?3], <choice><sic/><corr/> -> corr
    assert l2.text == "tiru-veḷḷaṟai [?3] perumāṉaṭikaḷukku"
    assert _spans(l2, "unclear") == ["v"]
    gap = l2.spans_of("gap")[0]
    assert (gap.reason, gap.quantity, gap.unit) == ("lost", 3, "character")


def test_break_no_note_omitted_surplus_glyphs():
    ins = parse_file(PALLAVA / "DHARMA_INSPallava90001.xml", "tfa-pallava-epigraphy")
    l3 = _line(ins, "3")
    assert l3.joined is True  # <lb break="no"/>
    assert "editorial note" not in l3.text  # <note> dropped
    assert _spans(l3, "supplied") == ["cantira"]
    assert l3.spans_of("supplied")[0].reason == "undefined"
    assert _spans(l3, "omitted") == ["o"]  # scribal omission supplied as text, not a target
    l4 = _line(ins, "4")
    # partly lost aksara -> [?1]; unknown extent -> [?]; surplus dropped; punctuation kept; symbol dropped
    assert l4.text == "[?1]ri [?] vaittāṉ."


def test_masked_hides_restorations():
    ins = parse_file(PALLAVA / "DHARMA_INSPallava90001.xml", "tfa-pallava-epigraphy")
    l1 = _line(ins, "1")
    assert l1.masked() == "svasti śrī kō-vicaiya-[?3]-p-pōttaraiyarkku yāṇṭu 10 Āvatu"


def test_textparts_languages_and_duplicate_line_numbers():
    ins = parse_file(PALLAVA / "DHARMA_INSPallava90002.xml", "tfa-pallava-epigraphy")
    assert [ln.n for ln in ins.lines] == ["A.1", "B.1", "B.1~2"]
    assert [ln.lang for ln in ins.lines] == ["san-Latn", "tam-Latn", "tam-Latn"]
    assert all("part" not in ln.text for ln in ins.lines)  # <head> dropped
    b1 = _line(ins, "B.1")
    # <choice> of two <unclear> alternatives -> first; literal "..." -> [?]
    assert b1.text == "Ivv-ūr nilam Iraṇṭu maṉ [?]"
    # two adjacent <supplied> elements form one restoration
    assert _spans(_line(ins, "B.1~2"), "supplied") == ["kaḻa"]
    assert ins.lang == "tam-Latn"  # majority of line languages when the edition has none


def test_dynasty_from_title():
    ins = parse_file(SII / "DHARMA_INSSII90001.xml", "tfa-sii-epigraphy")
    assert (ins.dynasty, ins.dynasty_source) == ("Cōḻa", "title")
    assert ins.licence is None
    assert infer_dynasty("tfa-sii-epigraphy", "X, time of Sundara Pāṇḍya, year 3") == ("Pāṇḍya", "title")
    assert infer_dynasty("tfa-sii-epigraphy", "X, time of Kulottuṅga Cōḻa") == ("Cōḻa", "title")
    assert infer_dynasty("tfa-sii-epigraphy", "X, no king") == (None, None)


def test_non_tei_is_ignored():
    assert not is_tei(SII / "DHARMA_INSSII04.xml")
    assert parse_file(SII / "DHARMA_INSSII04.xml") is None
    assert is_tei(SII / "DHARMA_INSSII90001.xml")
