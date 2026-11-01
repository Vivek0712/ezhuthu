"""Matching keys for ISO-15919 inscription text.

DHARMA editions write the same word in many ways: hyphens and apostrophes mark sandhi, capitals
mark independent vowels, scribes geminate consonants after ``r`` (``varmma`` for ``varma``), and
the scripts themselves did not distinguish short and long e/o before the 18th century. A key
folds all of these so that a curated variant matches every spelling of it.

Folding (applied in order):
  * Unicode NFC, lower-case;
  * drop editorial marks: hyphen, apostrophes, middle dot, ``+``, brackets of the gap markers kept;
  * ``ē``->``e``, ``ō``->``o`` (no length contrast in Tamil script before Beschi's reform);
  * ``ś``/``ṣ``/``s``->``c`` (Tamil writes Sanskrit sibilants with ``c``);
  * consonant gemination after ``r`` collapsed (``rmm``->``rm``, ``rkk``->``rk``).
"""

from __future__ import annotations

import re
import unicodedata

_MARKS = re.compile(r"[-’'‘·+_.,;:!?()=§@*\"]")
_SPACE = re.compile(r"\s+")
_CONS = "kgṅcjñṭḍṇtdnpbmyrlvḻḷṟṉ"
_GEM_AFTER_R = re.compile(rf"r([{_CONS}])\1")


def fold(text: str) -> str:
    """Normalise ISO-15919 text but keep word spaces (use for token-aware matching)."""
    s = unicodedata.normalize("NFC", text).lower()
    s = _MARKS.sub("", s)
    s = s.replace("ē", "e").replace("ō", "o")
    s = s.replace("ś", "c").replace("ṣ", "c").replace("s", "c")
    s = _GEM_AFTER_R.sub(r"r\1", s)
    return _SPACE.sub(" ", s).strip()


def key(text: str) -> str:
    """Folded text with all spaces removed (compounds are split inconsistently in editions)."""
    return fold(text).replace(" ", "")


def slug(text: str) -> str:
    """ASCII slug for entity ids: ``Uttiramērūr`` -> ``uttiramerur``."""
    s = unicodedata.normalize("NFC", text.lower()).replace("ḻ", "zh")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("ḻ", "zh")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"
