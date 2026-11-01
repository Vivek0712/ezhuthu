"""Parser for DHARMA TEI/EpiDoc editions.

``parse_file(path)`` returns an :class:`Inscription` whose ``lines`` are the ``<lb n>`` lines of the
``<div type="edition">`` as ISO-15919 text, with character spans for the editorial phenomena we
need downstream:

* ``supplied``: ``<supplied reason="lost|undefined">``, an expert restoration (benchmark target);
* ``omitted``: ``<supplied reason="omitted">``, letters the scribe left out (kept as text);
* ``unclear``: ``<unclear>`` (kept as text);
* ``gap``: ``<gap>`` rendered as a gap marker from ``contracts/restore-api.md``: ``[?N]`` for a gap of
  N characters, ``[?]`` otherwise.

The reading is *editorial*: inside ``<choice>`` we take ``reg``, ``corr`` or ``expan`` (in that
order) over ``orig``, ``sic`` and ``abbr``; ``<surplus>`` and ``<del>`` are dropped; ``<add>`` is kept.
``<note>``, ``<head>``, ``<label>``, ``<fw>`` and ``<certainty>`` are not part of the text.
Explanatory supplements (``reason="subaudible|explanation"``) are dropped. A literal ``...`` (DHARMA's
"not yet transcribed") becomes ``[?]``.

Whitespace follows TEI: runs collapse to one space, ``<lb break="no"/>`` joins a word across lines
(``Line.joined`` is then True), and block elements (``p``, ``ab``, ``l``, ``item``) separate words.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

TEI = "http://www.tei-c.org/ns/1.0"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
NS = {"t": TEI}

TARGET_REASONS = frozenset({"lost", "undefined"})
_SKIP = frozenset({"note", "head", "label", "fw", "certainty", "del", "surplus", "sic", "orig", "am",
                   "figure", "desc", "bibl", "ptr", "listBibl", "app", "listApp"})
_BLOCK = frozenset({"p", "ab", "l", "lg", "item", "list", "div"})
_CHOICE_PREF = ("reg", "corr", "expan")
_GLYPH_TEXT_TYPES = frozenset({"punctuation", "numeral"})

# Dynasty from collection name, then from rulers named in the title ("time of ...").
COLLECTION_DYNASTY = {
    "tfa-pallava-epigraphy": "Pallava",
    "tfa-pandya-epigraphy": "Pāṇḍya",
}
# ASCII-folded, lower-case keyword -> dynasty. Checked in order; first hit wins.
RULER_KEYWORDS: list[tuple[str, str]] = [
    ("pandya", "Pāṇḍya"), ("kulasekhara", "Pāṇḍya"), ("cataiyavarman", "Pāṇḍya"),
    ("jatavarman", "Pāṇḍya"), ("maravarman", "Pāṇḍya"), ("varaguna", "Pāṇḍya"),
    ("kesari", "Cōḻa"), ("cola", "Cōḻa"), ("rajaraja", "Cōḻa"), ("rajendra", "Cōḻa"),
    ("rajadhiraja", "Cōḻa"), ("kulottunga", "Cōḻa"), ("parantaka", "Cōḻa"),
    ("nandivarman", "Pallava"), ("dantivarman", "Pallava"), ("nrpatunga", "Pallava"),
    ("aparajita", "Pallava"), ("kampavarman", "Pallava"), ("kampavikramavarman", "Pallava"),
    ("mahendravarman", "Pallava"), ("narasimhavarman", "Pallava"), ("paramesvaravarman", "Pallava"),
    ("pottaraiyar", "Pallava"),
    ("kannara deva", "Rāṣṭrakūṭa"), ("kannaradeva", "Rāṣṭrakūṭa"),
    ("kopperunciṅkan", "Kāṭava"), ("kopperuncinkan", "Kāṭava"), ("katavarayan", "Kāṭava"),
    ("maharaya", "Vijayanagara"), ("devaraya", "Vijayanagara"), ("harihara", "Vijayanagara"),
    ("viruppanna", "Vijayanagara"), ("sadasiva", "Vijayanagara"), ("venkatapati", "Vijayanagara"),
    ("acyuta", "Vijayanagara"), ("krsnadeva", "Vijayanagara"), ("sriranga deva", "Vijayanagara"),
]

_CE_RE = re.compile(r"\b(\d{3,4}(?:\s*[-/–]\s*\d{1,4})?)\s*(?:CE|C\.E\.|A\.D\.|AD)\b")
_YEAR_RE = re.compile(r"\byear\s+(\d+)\b", re.IGNORECASE)
_TIME_OF_RE = re.compile(r"time of\s+([^,]+)", re.IGNORECASE)


@dataclass
class Span:
    start: int
    end: int
    kind: str  # supplied | omitted | unclear | gap
    reason: str | None = None
    quantity: int | None = None
    unit: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Line:
    n: str
    text: str
    spans: list[Span]
    lang: str | None
    joined: bool = False  # True when this line continues a word from the previous line

    def spans_of(self, kind: str) -> list[Span]:
        return [s for s in self.spans if s.kind == kind]

    def masked(self, keep: Span | None = None) -> str:
        """Text with every ``supplied`` span replaced by its gap marker ``[?N]`` (except ``keep``)."""
        from ezhuthu.corpus.script import count_aksharas

        out: list[str] = []
        pos = 0
        for s in sorted(self.spans_of("supplied"), key=lambda s: s.start):
            if s is keep:
                continue
            out.append(self.text[pos:s.start])
            out.append(f"[?{max(1, count_aksharas(self.text[s.start:s.end]))}]")
            pos = s.end
        out.append(self.text[pos:])
        return "".join(out)


@dataclass
class Inscription:
    id: str
    title: str
    collection: str | None
    path: str
    lang: str | None
    licence: str | None
    licence_url: str | None
    summary: str | None
    dynasty: str | None
    dynasty_source: str | None
    ruler: str | None
    regnal_year: int | None
    approx_date: str | None
    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        """Whole edition text, one line per row, ``-`` marking a word continued from the line above."""
        rows = []
        for ln in self.lines:
            rows.append(("-" if ln.joined else "") + ln.text)
        return "\n".join(rows)


# --------------------------------------------------------------------------------------------------
# line builder


class _Tag:
    """One editorial element; chars carry a reference to the tag they belong to."""

    __slots__ = ("kind", "quantity", "reason", "unit")

    def __init__(self, kind: str, reason: str | None = None, quantity: int | None = None,
                 unit: str | None = None):
        self.kind = kind
        self.reason = reason
        self.quantity = quantity
        self.unit = unit


class _Builder:
    def __init__(self) -> None:
        self.lines: list[tuple[str, list[tuple[str, _Tag | None]], str | None, bool]] = []
        self._cur: list[tuple[str, _Tag | None]] = []
        self._n = "0"
        self._lang: str | None = None
        self._joined = False

    def text(self, s: str, tag: _Tag | None) -> None:
        for ch in s:
            self._cur.append((ch, tag))

    def space(self) -> None:
        self._cur.append((" ", None))

    def last_char(self) -> str:
        for ch, _ in reversed(self._cur):
            if not ch.isspace():
                return ch
        return ""

    def new_line(self, n: str, lang: str | None, joined: bool) -> None:
        self._flush()
        self._n, self._lang, self._joined = n, lang, joined

    def _flush(self) -> None:
        if any(not ch.isspace() for ch, _ in self._cur):
            self.lines.append((self._n, self._cur, self._lang, self._joined))
        self._cur = []

    def finish(self) -> list[Line]:
        self._flush()
        out: list[Line] = []
        seen: dict[str, int] = {}
        for n, chars, lang, joined in self.lines:
            text, spans = _normalise(chars)
            if not text:
                continue
            if n in seen:
                seen[n] += 1
                n = f"{n}~{seen[n]}"
            else:
                seen[n] = 1
            out.append(Line(n=n, text=text, spans=spans, lang=lang, joined=joined))
        return out


def _normalise(chars: list[tuple[str, _Tag | None]]) -> tuple[str, list[Span]]:
    # collapse whitespace runs, strip ends
    collapsed: list[tuple[str, _Tag | None]] = []
    for ch, tag in chars:
        if ch.isspace():
            if collapsed and collapsed[-1][0] == " ":
                continue
            collapsed.append((" ", tag))
        else:
            collapsed.append((unicodedata.normalize("NFC", ch), tag))
    while collapsed and collapsed[0][0] == " ":
        collapsed.pop(0)
    while collapsed and collapsed[-1][0] == " ":
        collapsed.pop()
    text = "".join(ch for ch, _ in collapsed)
    spans: list[Span] = []
    i = 0
    while i < len(collapsed):
        tag = collapsed[i][1]
        j = i
        while j < len(collapsed) and collapsed[j][1] is tag:
            j += 1
        if tag is not None:
            start, end = i, j
            # a span never starts or ends with a space
            while start < end and text[start] == " ":
                start += 1
            while end > start and text[end - 1] == " ":
                end -= 1
            if end > start:
                spans.append(Span(start, end, tag.kind, tag.reason, tag.quantity, tag.unit))
        i = j
    # merge directly adjacent supplied spans (one gap edited as several elements)
    merged: list[Span] = []
    for s in spans:
        if (merged and s.kind == "supplied" and merged[-1].kind == "supplied"
                and merged[-1].end == s.start):
            merged[-1].end = s.end
        else:
            merged.append(s)
    return text, merged


# --------------------------------------------------------------------------------------------------
# tree walk


def _local(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _gap_marker(el) -> tuple[str, int | None, str | None]:
    unit = el.get("unit")
    q = el.get("quantity")
    quantity = int(q) if q and q.isdigit() else None
    if quantity and unit in (None, "character"):
        return f"[?{quantity}]", quantity, unit or "character"
    return "[?]", quantity, unit


class _Walker:
    def __init__(self) -> None:
        self.b = _Builder()
        self.prefix: list[str] = []

    def _line_n(self, n: str | None) -> str:
        return ".".join([*self.prefix, n or "0"])

    def emit_text(self, s: str | None, tag: _Tag | None) -> None:
        if not s:
            return
        if "..." in s:
            parts = re.split(r"\.{3,}|…", s)
            for k, part in enumerate(parts):
                if k:
                    self.b.text("[?]", _Tag("gap", "ellipsis"))
                self.b.text(part, tag)
        else:
            self.b.text(s, tag)

    def walk(self, el, tag: _Tag | None, lang: str | None) -> None:
        name = _local(el)
        lang = el.get(XML_LANG) or lang
        if not name:  # comment / processing instruction
            return
        if name in _SKIP:
            return
        if name == "lb":
            joined = el.get("break") == "no"
            self.b.new_line(self._line_n(el.get("n")), lang, joined)
            return
        if name in ("pb", "milestone", "cb"):
            if el.get("break") != "no":
                self.b.space()
            return
        if name == "space":
            self.b.space()
            return
        if name == "gap":
            marker, quantity, unit = _gap_marker(el)
            gtag = _Tag("gap", el.get("reason"), quantity, unit)
            self.b.text(marker, gtag)
            return
        if name == "g":
            gtype = el.get("type")
            txt = "".join(el.itertext())
            if gtype in _GLYPH_TEXT_TYPES or (gtype is None and txt.strip()):
                if gtype == "numeral" and self.b.last_char().isdigit():
                    self.b.space()
                self.emit_text(txt, tag)
                if gtype == "numeral":
                    self.b.space()
            return
        if name == "choice":
            kids = [k for k in el if _local(k)]
            pick = None
            for pref in _CHOICE_PREF:
                pick = next((k for k in kids if _local(k) == pref), None)
                if pick is not None:
                    break
            if pick is None and kids:
                pick = kids[0]
            if pick is not None:
                self.walk(pick, tag, lang)
            return
        if name == "seg" and el.get("type") == "aksara" and el.find(".//t:gap", NS) is not None:
            self.b.text("[?1]", _Tag("gap", "lost", 1, "character"))
            return
        if name == "supplied":
            reason = el.get("reason") or "undefined"
            if reason in ("subaudible", "explanation"):
                return
            if tag is None or tag.kind in ("unclear", "omitted"):
                tag = _Tag("supplied" if reason in TARGET_REASONS else "omitted", reason)
        elif name == "unclear":
            if tag is None:
                tag = _Tag("unclear", el.get("reason"))

        pushed = False
        if name == "div" and el.get("type") == "textpart" and el.get("n"):
            self.prefix.append(el.get("n"))
            pushed = True
            self.b.new_line(self._line_n(None), lang, False)
        block = name in _BLOCK
        if block:
            self.b.space()
        self.emit_text(el.text, tag)
        for child in el:
            self.walk(child, tag, lang)
            self.emit_text(child.tail, tag)
        if block:
            self.b.space()
        if pushed:
            self.prefix.pop()


def parse_edition(edition_el) -> list[Line]:
    w = _Walker()
    lang = edition_el.get(XML_LANG)
    w.b.new_line("0", lang, False)
    w.emit_text(edition_el.text, None)
    for child in edition_el:
        w.walk(child, None, lang)
        w.emit_text(child.tail, None)
    return w.b.finish()


# --------------------------------------------------------------------------------------------------
# header metadata


def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def infer_dynasty(collection: str | None, title: str | None) -> tuple[str | None, str | None]:
    if collection in COLLECTION_DYNASTY:
        return COLLECTION_DYNASTY[collection], "collection"
    if title:
        m = _TIME_OF_RE.search(title)
        if m:
            folded = _fold(m.group(1))
            for kw, dyn in RULER_KEYWORDS:
                if _fold(kw) in folded:
                    return dyn, "title"
    return None, None


def _text_of(root, xpath: str) -> str | None:
    el = root.find(xpath, NS)
    return _clean("".join(el.itertext())) if el is not None else None


def is_tei(path: str | Path) -> bool:
    try:
        for _, el in etree.iterparse(str(path), events=("start",)):
            return el.tag == f"{{{TEI}}}TEI"
    except etree.XMLSyntaxError:
        return False
    return False


def parse_file(path: str | Path, collection: str | None = None) -> Inscription | None:
    """Parse one DHARMA EpiDoc file. Returns None for non-TEI files or files without an edition."""
    path = Path(path)
    tree = etree.parse(str(path))
    root = tree.getroot()
    if root.tag != f"{{{TEI}}}TEI":
        return None
    edition = root.find(".//t:body/t:div[@type='edition']", NS)
    if edition is None:
        edition = root.find(".//t:div[@type='edition']", NS)
    if edition is None:
        return None
    ins_id = path.stem
    title = _text_of(root, ".//t:titleStmt/t:title") or ins_id
    licence_el = root.find(".//t:availability/t:licence", NS)
    licence = _clean("".join(licence_el.itertext())) if licence_el is not None else None
    licence_url = licence_el.get("target") if licence_el is not None else None
    summary = _text_of(root, ".//t:msContents/t:summary")
    lines = parse_edition(edition)
    lang = edition.get(XML_LANG)
    if lang is None:
        langs = [ln.lang for ln in lines if ln.lang]
        # most frequent line language; ties go to the language met first (deterministic)
        lang = max(dict.fromkeys(langs), key=langs.count) if langs else None
    dynasty, dyn_src = infer_dynasty(collection, title)
    m = _TIME_OF_RE.search(title)
    ruler = _clean(m.group(1)) if m else None
    if ruler and (ruler.strip("*. ") == "" or "lost" in ruler.lower()):
        ruler = None
    y = _YEAR_RE.search(title)
    approx = None
    for xp in (".//t:origDate", ".//t:div[@type='commentary']"):
        txt = _text_of(root, xp)
        if txt:
            cm = _CE_RE.search(txt)
            if xp.endswith("origDate"):
                approx = txt
            elif cm:
                approx = cm.group(0)
            if approx:
                break
    return Inscription(
        id=ins_id, title=title, collection=collection, path=str(path), lang=lang, licence=licence,
        licence_url=licence_url, summary=summary, dynasty=dynasty, dynasty_source=dyn_src, ruler=ruler,
        regnal_year=int(y.group(1)) if y else None, approx_date=approx, lines=lines,
    )
