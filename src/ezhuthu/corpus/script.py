"""ISO-15919 (DHARMA flavour) to Tamil, Tamil-Brahmi and Grantha script.

DHARMA editions of Tamil inscriptions are written in ISO-15919 with three house conventions that
plain transliterators do not know about:

* an UPPER-CASE vowel (``Āvatu``, ``k-Il``) is an *independent* vowel letter even when it follows a
  consonant, whereas a lower-case vowel after a consonant is a vowel sign (hyphens are transparent:
  ``vāriyam-āka`` is one written sequence ``vāriyamāka``);
* ``·`` marks a puḷḷi (virama) that is physically engraved, and ``’`` marks an elided vowel;
* numerals are given sign by sign (``2 10 4`` = 2 x 10 + 4), as on the stone.

Tamil script is produced by a small deterministic converter in this module. We do not use
Aksharamukha for Tamil because its Tamil post-processing rewrites ``ṉ`` to ``ந`` in some contexts
(``paṉṉiraṇṭu`` comes out as ``பந்நிரண்டு``) and adds superscript digits (``bh`` -> ``ப⁴``), both of which
are wrong for teaching. Tamil-Brahmi and Grantha go through Aksharamukha (``TamilBrahmi``,
``Grantha``) after the DHARMA conventions above have been normalised.

Gap markers from ``contracts/restore-api.md`` (``[?]`` and ``[?N]``) pass through every converter
untouched.
"""

from __future__ import annotations

import re
import unicodedata
import warnings
from dataclasses import dataclass
from functools import lru_cache

GAP_MARKER_RE = re.compile(r"\[\?\d*\]")

# Longest match first. Values: Tamil base letter.
_CONSONANTS: dict[str, str] = {
    "kh": "க", "gh": "க", "ch": "ச", "jh": "ஜ", "ṭh": "ட", "ḍh": "ட", "th": "த", "dh": "த",
    "ph": "ப", "bh": "ப",
    "k": "க", "g": "க", "ṅ": "ங", "c": "ச", "j": "ஜ", "ñ": "ஞ", "ṭ": "ட", "ḍ": "ட", "ṇ": "ண",
    "t": "த", "d": "த", "n": "ந", "p": "ப", "b": "ப", "m": "ம", "y": "ய", "r": "ர", "l": "ல",
    "v": "வ", "ś": "ஶ", "ṣ": "ஷ", "s": "ஸ", "h": "ஹ", "ḷ": "ள", "ḻ": "ழ", "ṟ": "ற", "ṉ": "ன",
    "f": "ஃப", "z": "ஃஜ",
}
# vowel -> (independent letter, vowel sign)
_VOWELS: dict[str, tuple[str, str]] = {
    "ai": ("ஐ", "ை"), "au": ("ஔ", "ௌ"),
    "r̥̄": ("ரூ", "்ரூ"), "r̥": ("ரு", "்ரு"), "l̥̄": ("லூ", "்லூ"), "l̥": ("லு", "்லு"),
    # IAST-style dotted-below vocalic r used in some DHARMA files; same letters as r̥ / r̥̄
    "ṝ": ("ரூ", "்ரூ"), "ṛ": ("ரு", "்ரு"),
    "ā": ("ஆ", "ா"), "ī": ("ஈ", "ீ"), "ū": ("ஊ", "ூ"), "ē": ("ஏ", "ே"), "ō": ("ஓ", "ோ"),
    "a": ("அ", ""), "i": ("இ", "ி"), "u": ("உ", "ு"), "e": ("எ", "ெ"), "o": ("ஒ", "ொ"),
    # diaeresis breaks a diphthong: kaïlāsa = ka-i-lāsa
    "ï": ("இ", "ி"), "ü": ("உ", "ு"),
}
# ``ḵ`` is the ISO-15919 āytam (ஃ, aḵtu = அஃது): a letter of its own, written without puḷḷi, after
# which a vowel is written as an independent letter.
_SIGNS: dict[str, str] = {"ṃ": "ம்", "ṁ": "ம்", "ḥ": "ஃ", "m̐": "ம்", "ḵ": "ஃ"}
_LETTER_SIGNS = frozenset({"ḵ"})  # signs that count as a Tamil letter (gap_chars)
# canonical spelling used by normalise_for_scoring
_VOWEL_ALIASES = {"ṛ": "r̥", "ṝ": "r̥̄"}
_VIRAMA = "்"
_TAMIL_NUMERAL_SIGNS = {"10": "௰", "100": "௱", "1000": "௲"}
_TAMIL_DIGITS = str.maketrans("0123456789", "௦௧௨௩௪௫௬௭௮௯")

_TOKEN_KEYS = sorted([*_CONSONANTS, *_VOWELS, *_SIGNS], key=len, reverse=True)


@dataclass(frozen=True)
class Token:
    kind: str  # "C" consonant, "V" vowel, "S" sign (anusvara/visarga), "O" other
    iso: str
    independent: bool = False  # for vowels written upper-case in DHARMA


def _nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def tokenize(text: str) -> list[Token]:
    """Split ISO-15919 text into consonant / vowel / sign / other tokens."""
    text = _nfc(text)
    out: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        lower_rest = text[i:i + 4]
        upper_vowel = ch.isupper()
        if upper_vowel:
            lower_rest = _nfc(unicodedata.normalize("NFD", lower_rest).lower())
        for key in _TOKEN_KEYS:
            if lower_rest.startswith(key):
                if key in _VOWELS:
                    kind = "V"
                elif key in _CONSONANTS:
                    kind = "C"
                else:
                    kind = "S"
                if upper_vowel and kind != "V":
                    # upper-case consonant (rare, e.g. proper names in some files): just a consonant
                    pass
                # length of the match in the original string (case folding keeps lengths in NFC)
                out.append(Token(kind, key, independent=upper_vowel and kind == "V"))
                i += len(key)
                break
        else:
            out.append(Token("O", ch))
            i += 1
    return out


def count_aksharas(text: str) -> int:
    """Number of Tamil letters (uyir, mey, uyirmey) in ``text``.

    This is the unit DHARMA uses for ``<gap unit="character" quantity="N">`` and the unit of
    ``gap_chars`` in the benchmark contract: every vowel is one letter, and so is every consonant
    that is not followed by a vowel (a mey letter with puḷḷi). Gap markers are not counted.
    """
    text = GAP_MARKER_RE.sub(" ", text)
    toks = [t for t in tokenize(text) if t.kind != "O" or t.iso not in "-·’'"]
    count = 0
    for k, tok in enumerate(toks):
        if tok.kind == "V" or (tok.kind == "S" and tok.iso in _LETTER_SIGNS):
            count += 1
        elif tok.kind == "C":
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            if nxt is None or nxt.kind != "V" or nxt.independent:
                count += 1
    return count


def _numerals_to_tamil(text: str) -> str:
    def repl(m: re.Match[str]) -> str:
        s = m.group(0)
        return _TAMIL_NUMERAL_SIGNS.get(s) or s.translate(_TAMIL_DIGITS)

    return re.sub(r"(?<![/\d])\d+(?![/\d])", repl, text)


def _iso_chunk_to_tamil(text: str, keep_hyphens: bool) -> str:
    toks = tokenize(text)
    out: list[str] = []
    prev_consonant = False  # the last emitted letter is a consonant still waiting for a vowel
    for tok in toks:
        if tok.kind == "C":
            if prev_consonant:
                out.append(_VIRAMA)
            out.append(_CONSONANTS[tok.iso])
            prev_consonant = True
        elif tok.kind == "V":
            indep, sign = _VOWELS[tok.iso]
            if prev_consonant and not tok.independent:
                out.append(sign)
            else:
                if prev_consonant:
                    out.append(_VIRAMA)
                out.append(indep)
            prev_consonant = False
        elif tok.kind == "S":
            if prev_consonant:
                out.append(_VIRAMA)
            out.append(_SIGNS[tok.iso])
            prev_consonant = False
        else:
            ch = tok.iso
            if ch == "-":
                # hyphens are editorial word splits; the following vowel still attaches
                if keep_hyphens:
                    if prev_consonant:
                        out.append(_VIRAMA)
                        prev_consonant = False
                    out.append("-")
                continue
            if ch == "·":
                # engraved puḷḷi: the virama is emitted when the next token is not a vowel sign
                continue
            if prev_consonant:
                out.append(_VIRAMA)
                prev_consonant = False
            if ch in "’'":
                continue
            out.append(ch)
    if prev_consonant:
        out.append(_VIRAMA)
    return _numerals_to_tamil("".join(out))


def iso_to_tamil(text: str, keep_hyphens: bool = False) -> str:
    """ISO-15919 (DHARMA conventions) to Tamil script. Gap markers are preserved."""
    parts: list[str] = []
    pos = 0
    for m in GAP_MARKER_RE.finditer(text):
        parts.append(_iso_chunk_to_tamil(text[pos:m.start()], keep_hyphens))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(_iso_chunk_to_tamil(text[pos:], keep_hyphens))
    return "".join(parts)


# Editorial marks that DHARMA editions use inside the text but that are not letters: ``=`` (a
# sandhi / word-division mark), ``‡`` and ``⌈ ⌉`` (edition-specific symbols), ``_`` and quote marks.
# They are kept in ``text_iso``; the display form of Tamil text and the scoring form drop them.
# The apostrophes ``’`` and ``'`` are not here: they mark an elided vowel and change the spelling.
EDITORIAL_MARKS = "=‡⌈⌉⌊⌋_\"“”„‘`´\ufffd"
_EDITORIAL_RE = re.compile("[" + re.escape(EDITORIAL_MARKS) + "]")


def strip_editorial_marks(text: str) -> str:
    """Remove the non-letter editorial marks in :data:`EDITORIAL_MARKS`. Gap markers are kept."""
    parts: list[str] = []
    pos = 0
    for m in GAP_MARKER_RE.finditer(text):
        parts.append(_EDITORIAL_RE.sub("", text[pos:m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(_EDITORIAL_RE.sub("", text[pos:]))
    return "".join(parts)


# Editors' prose inside the text: "[text not available]", "{wavy line}". Shown as a gap / dropped.
_NOTE_BRACKET_RE = re.compile(r"\[(?!\?\d*\])[^\]\n]*[A-Za-z]{3,}[^\]\n]*\]")
_NOTE_BRACE_RE = re.compile(r"\{[^}\n]*\}")
_KEY_CHARS = frozenset("".join(_TOKEN_KEYS))


def _fold_stray_letters(text: str) -> str:
    """Letters no ISO-15919 key starts with (source typos such as ``ţ``, ``ḿ``, ``ȧ``, ``Å``) are
    folded to their base letter when that is a key letter (``ţ`` -> ``t``) and dropped otherwise
    (``x``, ``w``), so that no Latin letter reaches Tamil display text."""
    out: list[str] = []
    for ch in _nfc(text):
        if ch.isalpha() and not ("\u0b80" <= ch <= "\u0bff") and ch.lower() not in _KEY_CHARS:
            base = unicodedata.normalize("NFD", ch)[0]
            out.append(base if base.lower() in _KEY_CHARS else "")
        else:
            out.append(ch)
    return "".join(out)


def iso_to_tamil_display(text: str) -> str:
    """Tamil script for learners: :func:`iso_to_tamil` with editorial marks removed, editors' notes
    in brackets shown as ``[?]`` (``{...}`` notes dropped), stray Latin letters folded or dropped, and
    runs of spaces collapsed (line breaks kept). Gap markers are preserved. ``text_iso`` keeps the raw
    marks; use this only for what learners read or hear."""
    text = _NOTE_BRACE_RE.sub("", _NOTE_BRACKET_RE.sub("[?]", text))
    out = iso_to_tamil(_fold_stray_letters(strip_editorial_marks(text)))
    return "\n".join(re.sub(r"[ \t]{2,}", " ", row).strip(" ") for row in out.split("\n"))


def normalise_for_scoring(text: str) -> str:
    """The form in which restorations are compared (CER, top-1 exact match): letters only.

    ISO-15919 letters (consonants, vowels, anusvāra / visarga / āytam) are kept, lower-cased and in
    one canonical spelling (``ṛ`` -> ``r̥``); everything else is dropped: spaces, hyphens, ``·``,
    ``’``, digits, punctuation, gap markers and the editorial marks in :data:`EDITORIAL_MARKS`.
    The upper-case convention for independent vowels is ignored (``k-Il`` and ``kil`` score the same).

    >>> normalise_for_scoring("nan=ti-p ‡pōttaraiyar 2 10")
    'nantippōttaraiyar'
    """
    text = GAP_MARKER_RE.sub(" ", _nfc(text))
    return "".join(_VOWEL_ALIASES.get(t.iso, t.iso) for t in tokenize(text) if t.kind != "O")


def normalize_iso(text: str) -> str:
    """Make DHARMA ISO text safe for generic transliterators.

    Upper-case vowels become ``_`` + lower-case vowel (``_`` breaks the consonant-vowel join in
    Aksharamukha and is removed afterwards), hyphens and ``’``/``·`` are dropped.
    """
    text = _nfc(text)
    out: list[str] = []
    for tok in tokenize(text):
        if tok.kind == "V" and (tok.independent or tok.iso in ("ï", "ü")):
            out.append("_" + {"ï": "i", "ü": "u"}.get(tok.iso, tok.iso))
        elif tok.kind == "O" and tok.iso in "-·’'":
            continue
        else:
            out.append(tok.iso)
    return "".join(out)


@lru_cache(maxsize=1)
def _aksharamukha():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        from aksharamukha import transliterate

    return transliterate


def _via_aksharamukha(text: str, target: str) -> str:
    tr = _aksharamukha()
    parts: list[str] = []
    pos = 0

    def conv(chunk: str) -> str:
        if not chunk.strip():
            return chunk
        # convert each "_"-separated segment on its own so that an independent vowel stays independent
        segs = normalize_iso(chunk).split("_")
        return "".join(tr.process("ISO", target, s) if s else "" for s in segs)

    for m in GAP_MARKER_RE.finditer(text):
        parts.append(conv(text[pos:m.start()]))
        parts.append(m.group(0))
        pos = m.end()
    parts.append(conv(text[pos:]))
    return "".join(parts)


def iso_to_tamil_brahmi(text: str) -> str:
    """ISO-15919 to Tamil-Brahmi (Unicode Brahmi block, Aksharamukha ``TamilBrahmi``)."""
    return _via_aksharamukha(text, "TamilBrahmi")


def iso_to_grantha(text: str) -> str:
    """ISO-15919 to Grantha (Unicode Grantha block, Aksharamukha ``Grantha``)."""
    return _via_aksharamukha(text, "Grantha")


def convert(text: str, target: str) -> str:
    """Dispatch by script name: ``tamil``, ``tamil_brahmi`` or ``grantha``."""
    target = target.lower().replace("-", "_")
    if target == "tamil":
        return iso_to_tamil(text)
    if target in ("tamil_brahmi", "tamilbrahmi", "brahmi"):
        return iso_to_tamil_brahmi(text)
    if target == "grantha":
        return iso_to_grantha(text)
    raise ValueError(f"unknown target script: {target}")
