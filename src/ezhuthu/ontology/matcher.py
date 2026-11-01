"""Variant matcher over ISO-15919 text.

A match must start at a word or compound-member boundary (whitespace or hyphen in the edition)
and may end anywhere, so a stem matches its case forms (``kāliyūr-k-kōṭṭattu`` matches the
variant ``kōṭṭattu``; ``vāriyamum`` matches ``vāriyam``). Text and variants are compared on
:func:`ezhuthu.ontology.normalize.key`, so spaces inside a compound, gemination and e/ē do not
matter.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from ezhuthu.ontology.normalize import key

_TOKEN = re.compile(r"[^\s\-]+")
MIN_KEY = 3


@dataclass(frozen=True)
class Match:
    entity_id: str
    variant: str
    start: int  # char offsets in the original text
    end: int
    surface: str


@dataclass
class KeyedText:
    """Concatenated keys of the tokens of ``text`` with a map back to char offsets."""

    text: str
    joined: str
    starts: dict[int, int]  # key offset of each token start -> original char start
    spans: list[tuple[int, int, int, int]]  # (key_start, key_end, char_start, char_end)

    @classmethod
    def of(cls, text: str) -> KeyedText:
        parts: list[str] = []
        starts: dict[int, int] = {}
        spans = []
        off = 0
        for m in _TOKEN.finditer(text):
            k = key(m.group())
            if not k:
                continue
            starts[off] = m.start()
            spans.append((off, off + len(k), m.start(), m.end()))
            parts.append(k)
            off += len(k)
        return cls(text, "".join(parts), starts, spans)

    def char_end(self, key_end: int) -> int:
        for ks, ke, _cs, ce in self.spans:
            if ks < key_end <= ke:
                return ce
        return len(self.text)


class VariantIndex:
    def __init__(self) -> None:
        self._by_prefix: dict[str, list[tuple[str, str, str]]] = defaultdict(list)  # k[:2] -> (key, id, variant)
        self.size = 0

    def add(self, entity_id: str, variant: str) -> None:
        k = key(variant)
        if len(k) < MIN_KEY:
            return
        bucket = self._by_prefix[k[:2]]
        if any(b[0] == k and b[1] == entity_id for b in bucket):
            return
        bucket.append((k, entity_id, variant))
        bucket.sort(key=lambda b: -len(b[0]))
        self.size += 1

    def variants(self):
        for bucket in self._by_prefix.values():
            yield from bucket

    def scan(self, text: str, overlapping: bool = False) -> list[Match]:
        """Find variant occurrences. By default the result is greedy, longest-first, non-overlapping."""
        kt = KeyedText.of(text)
        j = kt.joined
        found: list[tuple[int, int, str, str]] = []
        for off in kt.starts:
            for k, eid, variant in self._by_prefix.get(j[off : off + 2], ()):
                if j.startswith(k, off):
                    found.append((off, off + len(k), eid, variant))
        if not overlapping:
            found.sort(key=lambda f: (f[0], -(f[1] - f[0])))
            kept: list[tuple[int, int, str, str]] = []
            end = -1
            for f in found:
                if f[0] >= end:
                    kept.append(f)
                    end = f[1]
                elif kept and f[0] == kept[-1][0] and f[1] == kept[-1][1]:
                    kept.append(f)  # same span, different entity: keep both (ambiguous names)
            found = kept
        out = []
        for ks, ke, eid, variant in found:
            cs = kt.starts[ks]
            ce = kt.char_end(ke)
            out.append(Match(eid, variant, cs, ce, text[cs:ce]))
        return out
