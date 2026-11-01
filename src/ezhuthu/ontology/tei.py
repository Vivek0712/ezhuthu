"""Minimal reader for DHARMA TEI/EpiDoc inscription files.

This is the ontology team's own reader: it pulls what the ontology build needs (header title,
script class of each edition div, and the edition text line by line, in ISO-15919) without
depending on the corpus package. Gaps become ``[?]`` / ``[?N]`` markers as in
``contracts/restore-api.md``; ``<supplied>`` text is kept (it is the expert restoration) and
its character spans are recorded so tests and evaluations can hide it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"

# Elements whose text is never part of the reading text.
_SKIP = {"note", "surplus", "space", "pb", "milestone", "fw", "certainty", "link", "app", "listApp"}
# In a <choice>, keep the regularised/corrected/expanded reading.
_CHOICE_PREF = ("reg", "corr", "expan", "unclear", "seg")


@dataclass
class Line:
    n: str
    text: str
    supplied: list[tuple[int, int]] = field(default_factory=list)  # [start, end) spans in text


@dataclass
class Inscription:
    id: str
    collection: str
    path: Path
    title: str
    script_classes: list[str]
    langs: list[str]
    lines: list[Line]
    pers_names: list[str]
    place_names: list[str]

    @property
    def text(self) -> str:
        return " ".join(line.text for line in self.lines if line.text)


def inscription_id(path: Path) -> str:
    """``~DHARMA_INSPandya00011.xml`` -> ``DHARMA_INSPandya00011``."""
    return path.name.lstrip("~").removesuffix(".xml")


def _local(tag: object) -> str:
    return tag.split("}", 1)[1] if isinstance(tag, str) and "}" in tag else str(tag)


class _LineBuilder:
    def __init__(self) -> None:
        self.lines: list[Line] = []
        self._n = "0"
        self._buf: list[str] = []
        self._spans: list[tuple[int, int]] = []

    def _len(self) -> int:
        return sum(len(s) for s in self._buf)

    def text(self, s: str, supplied: bool) -> None:
        if not s:
            return
        s = re.sub(r"\s+", " ", s)
        if s.startswith(" ") and (not self._buf or self._buf[-1].endswith(" ")):
            s = s.lstrip()
            if not s:
                return
        start = self._len()
        self._buf.append(s)
        if supplied and s.strip():
            self._spans.append((start, start + len(s)))

    def lb(self, n: str | None, joined: bool) -> None:
        if joined and self._buf:
            # break="no": the word continues on the next line; trim the trailing space here.
            self._buf[-1] = self._buf[-1].rstrip()
        self.flush()
        self._n = n or self._n

    def flush(self) -> None:
        raw = "".join(self._buf)
        lead = len(raw) - len(raw.lstrip())
        text = raw.strip()
        if text:
            spans = []
            for a, b in self._spans:
                a2, b2 = max(a - lead, 0), min(b - lead, len(text))
                if b2 > a2:
                    spans.append((a2, b2))
            self.lines.append(Line(self._n, text, spans))
        self._buf, self._spans = [], []


def _walk(el: etree._Element, out: _LineBuilder, supplied: bool) -> None:
    tag = _local(el.tag)
    if not isinstance(el.tag, str):  # comments, processing instructions
        if el.tail:
            out.text(el.tail, supplied)
        return
    if tag in _SKIP:
        pass
    elif tag == "lb":
        out.lb(el.get("n"), el.get("break") == "no")
    elif tag == "gap":
        qty = el.get("quantity")
        out.text(f" [?{qty}] " if qty and qty.isdigit() else " [?] ", False)
    elif tag == "choice":
        kids = [k for k in el if isinstance(k.tag, str)]
        chosen = None
        for pref in _CHOICE_PREF:
            chosen = next((k for k in kids if _local(k.tag) == pref), None)
            if chosen is not None:
                break
        if chosen is None and kids:
            chosen = kids[0]
        if chosen is not None:
            _walk_children(chosen, out, supplied)
    else:
        sup = supplied or (tag == "supplied" and el.get("reason") in (None, "lost", "undefined"))
        if el.text:
            out.text(el.text, sup)
        for child in el:
            _walk(child, out, sup)
    if el.tail:
        out.text(el.tail, supplied)


def _walk_children(el: etree._Element, out: _LineBuilder, supplied: bool) -> None:
    sup = supplied
    if el.text:
        out.text(el.text, sup)
    for child in el:
        _walk(child, out, sup)


def read_inscription(path: Path, collection: str | None = None) -> Inscription:
    parser = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True)
    root = etree.parse(str(path), parser).getroot()
    title_el = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}titleStmt/{TEI}title")
    title = " ".join((title_el.xpath("string()") if title_el is not None else "").split())
    editions = root.findall(f".//{TEI}div[@type='edition']")
    builder = _LineBuilder()
    classes: list[str] = []
    langs: list[str] = []
    pers: list[str] = []
    places: list[str] = []
    for ed in editions:
        rend = ed.get("rendition") or ""
        m = re.search(r"class:(\S+)", rend)
        if m:
            classes.append(m.group(1))
        if ed.get(XML_LANG):
            langs.append(ed.get(XML_LANG))
        for child in ed:
            _walk(child, builder, False)
        builder.flush()
        for p in ed.iter(f"{TEI}persName"):
            s = " ".join(p.xpath("string()").split())
            if s:
                pers.append(s)
        for p in ed.iter(f"{TEI}placeName"):
            s = " ".join(p.xpath("string()").split())
            if s:
                places.append(s)
    return Inscription(
        id=inscription_id(path),
        collection=collection or path.parent.name,
        path=path,
        title=title,
        script_classes=classes,
        langs=langs,
        lines=builder.lines,
        pers_names=pers,
        place_names=places,
    )


def iter_corpus(root: Path):
    """Yield every DHARMA inscription under ``root/<collection>/*.xml`` (templates skipped)."""
    for coll in sorted(p for p in root.iterdir() if p.is_dir()):
        for path in sorted(coll.glob("*.xml")):
            if "_template" in path.name:
                continue
            yield read_inscription(path, coll.name)
