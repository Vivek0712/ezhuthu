"""Text utilities: gap markers, ISO-15919 normalisation, script rendering, aksharas.

Text is ISO-15919 internally (contracts/restore-api.md). Gap markers:
``[?]`` is a gap of unknown length and ``[?N]`` a gap of about N Tamil letters (aksharas; DHARMA's "character"
unit, see :func:`akshara_len`), not N ISO-15919 characters.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import dataclass
from functools import lru_cache

GAP_RE = re.compile(r"\[\?(\d*)\]")
GRANTHA_CANDRABINDU = "\U00011300"
DEFAULT_UNKNOWN_GAP = 6  # used only when neither the marker nor a parallel gives a length

# Script stage per tutor level (contracts/restore-api.md, "Tutor").
LEVELS = ("L1", "L2", "L3", "L4", "L5")
LEVEL_NAMES = {
    "L1": ("modern Tamil", "தற்காலத் தமிழ்"),
    "L2": ("Chola Tamil", "சோழர் காலத் தமிழ்"),
    "L3": ("Pallava Tamil (Grantha)", "பல்லவர் காலத் தமிழ் (கிரந்தம்)"),
    "L4": ("Vatteluttu", "வட்டெழுத்து"),
    "L5": ("Tamil-Brahmi", "தமிழ்-பிராமி"),
}


@dataclass(frozen=True)
class Gap:
    index: int
    start: int  # offset of the marker in the original text
    end: int
    left: str  # ISO text before the gap (other gaps left as their markers)
    right: str
    gap_chars: int | None  # None when the marker was ``[?]``


def normalize_iso(text: str) -> str:
    """NFC, collapse whitespace, lower-case. ISO-15919 is case-insensitive for Tamil."""
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", text).strip().lower()


def find_gaps(text: str) -> list[Gap]:
    gaps: list[Gap] = []
    for i, m in enumerate(GAP_RE.finditer(text)):
        n = int(m.group(1)) if m.group(1) else None
        gaps.append(Gap(i, m.start(), m.end(), text[: m.start()], text[m.end():], n))
    return gaps


def fill_gaps(text: str, fills: list[str | None]) -> str:
    """Replace gap markers left to right. ``None`` keeps the original marker (abstain)."""
    it = iter(fills)

    def _sub(m: re.Match[str]) -> str:
        fill = next(it, None)
        return m.group(0) if fill is None else fill

    return GAP_RE.sub(_sub, text)


def _translit(src: str, dst: str, text: str) -> str:
    from aksharamukha import transliterate

    kw: dict = {}
    if src == "ISO" and dst == "Tamil":
        # Faithful mapping (ISO n -> ந, ṉ -> ன) and no superscript disambiguation digits (த³).
        kw = {"nativize": False, "post_options": ["TamilRemoveNumbers"]}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return transliterate.process(src, dst, text, **kw)


def _protect_gaps(text: str, fn) -> str:
    """Transliterate everything except gap markers."""
    # re.split with one group returns [text, N, text, N, text]; odd slots are marker lengths.
    out: list[str] = []
    for i, part in enumerate(GAP_RE.split(text)):
        if i % 2:
            out.append(f"[?{part}]")
        else:
            out.append(fn(part) if part.strip() else part)
    return "".join(out)


@lru_cache(maxsize=4096)
def iso_to_tamil(text: str) -> str:
    return _protect_gaps(text, lambda s: _translit("ISO", "Tamil", s))


@lru_cache(maxsize=4096)
def tamil_to_iso(text: str) -> str:
    return _protect_gaps(text, lambda s: _translit("Tamil", "ISO", s))


def to_iso(text: str, script: str) -> str:
    return tamil_to_iso(text) if script == "tamil" else text


def looks_tamil(text: str) -> bool:
    return any("஀" <= ch <= "௿" for ch in text)


def chola_orthography(iso: str) -> str:
    """Chola-era spelling: inscriptions of the period do not mark e/ē or o/ō length."""
    return iso.replace("ē", "e").replace("ō", "o")


@lru_cache(maxsize=4096)
def render_level(iso: str, level: str) -> dict[str, str | None]:
    """Render ISO text for a tutor level. Returns ``glyph_text`` and/or ``glyph_svg``.

    L1 modern Tamil; L2 Tamil script in Chola orthography (no e/ō length contrast, no pulli);
    L3 Grantha (Noto Sans Grantha), the closest Unicode script to Pallava-Grantha. Aksharamukha marks short
    e/o with a combining candrabindu (U+11300); Pallava-Grantha did not write the short/long contrast, so the
    mark is dropped for teaching (grading at L3 ignores e/ē, o/ō length anyway);
    L4 Vatteluttu has no Unicode block: ``glyph_svg`` is SVG markup drawn server side (see ``glyphs``) and
    ``glyph_text`` is None, so the payload never carries the answer. Letters without a drawing return None
    for both;
    L5 Tamil-Brahmi (Unicode Brahmi with Tamil-Brahmi letters).
    """
    if level == "L1":
        return {"glyph_text": iso_to_tamil(iso), "glyph_svg": None, "font": "Noto Sans Tamil"}
    if level == "L2":
        ta = iso_to_tamil(chola_orthography(iso)).replace("்", "")
        return {"glyph_text": ta, "glyph_svg": None, "font": "Noto Sans Tamil"}
    if level == "L3":
        grantha = _translit("ISO", "Grantha", iso).replace(GRANTHA_CANDRABINDU, "")
        return {"glyph_text": grantha, "glyph_svg": None, "font": "Noto Sans Grantha"}
    if level == "L4":
        from .glyphs import vatteluttu_svg

        return {"glyph_text": None, "glyph_svg": vatteluttu_svg(iso), "font": None}
    if level == "L5":
        return {"glyph_text": _translit("ISO", "TamilBrahmi", iso), "glyph_svg": None, "font": "Noto Sans Brahmi"}
    raise ValueError(f"unknown level {level!r}")


# ISO-15919 aksharas for Tamil + Grantha letters. Longest first so "ai" wins over "a".
_VOWELS = ["ai", "au", "ā", "ī", "ū", "ē", "ō", "a", "i", "u", "e", "o", "r̥", "r̥̄"]
_CONS = ["kṣ", "ṅ", "ñ", "ṇ", "ṉ", "ṟ", "ḻ", "ḷ", "ś", "ṣ", "k", "c", "ṭ", "t", "p", "m", "y", "r", "l", "v",
         "n", "j", "s", "h", "g", "d", "b", "ḍ", "ḥ", "ṃ"]
_AKSHARA_RE = re.compile(
    "(?:" + "|".join(sorted(map(re.escape, _CONS), key=len, reverse=True)) + ")"
    "(?:" + "|".join(sorted(map(re.escape, _VOWELS), key=len, reverse=True)) + ")?"
    "|(?:" + "|".join(sorted(map(re.escape, _VOWELS), key=len, reverse=True)) + ")"
)


def aksharas(iso: str) -> list[str]:
    """Split an ISO word into aksharas (consonant + optional vowel, or bare vowel).

    For display and letter drills. To *count* letters against a gap length use :func:`akshara_len`, which is the
    benchmark's own counter (this split disagrees with ``gap_chars`` on 21 of 443 VAL targets, e.g. ``ḵ``)."""
    return _AKSHARA_RE.findall(unicodedata.normalize("NFC", iso.lower()))


def akshara_len(iso: str) -> int:
    """Length of ISO text in Tamil letters (uyir, mey, uyirmey): the unit of ``gap_chars`` and of ``[?N]``.

    Every gap length in the restorer (length check, copy floor, copy baseline, n-gram fill length, alignment
    window, LLM prompt) is compared in this unit. It is :func:`ezhuthu.corpus.script.count_aksharas`, the
    function that computed ``gap_chars`` when the benchmark was built, so an expert target always has
    ``akshara_len(target) == gap_chars`` (443/443 VAL, 413/413 test, also after :func:`normalize_iso`).
    ISO-15919 characters are not letters: ``yañ ceytā`` is 9 characters but 5 letters (ya ñ ce y tā)."""
    from ezhuthu.corpus.script import count_aksharas

    return count_aksharas(iso or "")


def akshara_span_end(text: str, start: int, n: int) -> int:
    """End offset of the longest ``text[start:end]`` holding at most ``n`` letters (``n`` >= 1)."""
    end = start
    for e in range(start + 1, len(text) + 1):
        if akshara_len(text[start:e]) > n:
            break
        end = e
    return end


def akshara_span_start(text: str, end: int, n: int) -> int:
    """Start offset of the longest ``text[start:end]`` holding at most ``n`` letters (``n`` >= 1)."""
    start = end
    for s in range(end - 1, -1, -1):
        if akshara_len(text[s:end]) > n:
            break
        start = s
    return start


ISO_LETTER_CHARS = set("aāiīuūeēoōkṅcñṭṇtnpmyrlvḻḷṟṉśṣsjhgdbḍḥṃ" + "̥̄")


def non_iso_chars(text: str, *, extra_allowed: str = "") -> set[str]:
    """Characters that are not Tamil/Grantha ISO letters, digits, spaces or punctuation."""
    out = set()
    allowed = ".,-|/'()" + extra_allowed
    for ch in unicodedata.normalize("NFD", text.lower()):
        if ch.isspace() or ch.isdigit() or ch in allowed:
            continue
        if unicodedata.normalize("NFC", ch) in ISO_LETTER_CHARS or ch in ISO_LETTER_CHARS:
            continue
        if unicodedata.combining(ch) and ch in "\u0323\u0331\u0304\u0307\u0303\u0301\u0325\u032e":
            continue  # dots/macrons below/above used by ISO
        out.add(ch)
    return out
