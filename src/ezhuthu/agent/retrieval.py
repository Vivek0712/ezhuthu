"""Parallel-passage retrieval: BM25 over character n-grams, re-ranked with rapidfuzz.

Inscriptions repeat formulae (regnal openings, grant clauses, imprecations), so the best
evidence for a gap is often the same formula in another inscription. ``align_fill`` reads
the text that sits between the gap's left and right context inside a parallel line.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from rank_bm25 import BM25Okapi
from rapidfuzz import fuzz

from .data import CorpusLine
from .text import GAP_RE, normalize_iso

NGRAM = 3
CONTEXT_CHARS = 24
MIN_ANCHOR = 3


def char_ngrams(text: str, n: int = NGRAM) -> list[str]:
    t = f" {normalize_iso(text)} "
    return [t[i: i + n] for i in range(max(1, len(t) - n + 1))]


@dataclass(frozen=True)
class Parallel:
    inscription_id: str
    line_n: str
    snippet: str
    url: str | None
    score: float  # 0..100 fuzzy context match
    fill: str | None  # text aligned with the gap, if anchors were found

    def to_api(self) -> dict[str, str | None]:
        return {"inscription_id": self.inscription_id, "line_n": self.line_n, "snippet": self.snippet,
                "url": self.url}


def _clean(s: str) -> str:
    """NFC + lower + collapse whitespace, keeping one edge space (it marks a word boundary)."""
    core = normalize_iso(s)
    if not core:
        return " " if s and s.isspace() else ""
    return (" " if s[:1].isspace() else "") + core + (" " if s[-1:].isspace() else "")


def _context(left: str, right: str) -> tuple[str, str]:
    # Other gaps on the same line are markers; drop them from the query.
    left = _clean(GAP_RE.sub(" ", left.split("\n")[-1]))
    right = _clean(GAP_RE.sub(" ", right.split("\n")[0]))
    return left[-CONTEXT_CHARS:], right[:CONTEXT_CHARS]


@dataclass(frozen=True)
class Alignment:
    fill: str | None
    left_len: int  # chars of left context matched exactly next to the gap
    right_len: int


def _anchor_left(line: str, left: str) -> tuple[int, int] | None:
    """(end offset in ``line``, matched length) of the longest suffix of ``left``."""
    for k in range(len(left), MIN_ANCHOR - 1, -1):
        suffix = left[-k:]
        if not suffix.strip():
            continue
        pos = line.find(suffix)
        if pos >= 0:
            return pos + k, k
    return None


def _anchor_right(line: str, right: str, start: int) -> tuple[int, int] | None:
    """(start offset in ``line[start:]``, matched length) of the longest prefix of ``right``."""
    for k in range(len(right), MIN_ANCHOR - 1, -1):
        prefix = right[:k]
        if not prefix.strip():
            continue
        pos = line.find(prefix, start)
        if pos >= 0:
            return pos, k
    return None


def _extend_to_word(line: str, start: int, end: int, slack: int = 3) -> int:
    """``[?N]`` is approximate: finish a word that is cut by at most ``slack`` chars."""
    stop = end
    while stop < len(line) and stop - end < slack and not line[stop].isspace():
        stop += 1
    return stop if stop >= len(line) or line[stop].isspace() else end


def align(line: str, left: str, right: str, gap_chars: int | None) -> Alignment:
    """Text in ``line`` between the left and right context of a gap."""
    line = normalize_iso(line)
    la = _anchor_left(line, left) if left.strip() else None
    if la is not None:
        lpos, llen = la
        ra = _anchor_right(line, right, lpos) if right.strip() else None
        if ra is not None and ra[0] > lpos:
            return Alignment(line[lpos:ra[0]].strip() or None, llen, ra[1])
        if gap_chars:
            end = _extend_to_word(line, lpos, lpos + gap_chars)
            return Alignment(line[lpos:end].strip() or None, llen, 0)
        return Alignment(None, llen, 0)
    if right.strip() and gap_chars:
        ra = _anchor_right(line, right, 0)
        if ra is not None and ra[0] > 0:
            return Alignment(line[max(0, ra[0] - gap_chars): ra[0]].strip() or None, 0, ra[1])
        return Alignment(None, 0, ra[1] if ra else 0)
    return Alignment(None, 0, 0)


def align_fill(line: str, left: str, right: str, gap_chars: int | None) -> str | None:
    lctx, rctx = _context(left, right)
    return align(line, lctx, rctx, gap_chars).fill


class ParallelIndex:
    def __init__(self, lines: Sequence[CorpusLine]):
        self.lines = list(lines)
        self._bm25 = BM25Okapi([char_ngrams(ln.text) for ln in self.lines]) if self.lines else None

    def __len__(self) -> int:
        return len(self.lines)

    def search(self, left: str, right: str, *, gap_chars: int | None = None, k: int = 5,
               exclude_inscription: str | None = None, pool: int = 50) -> list[Parallel]:
        if not self._bm25:
            return []
        lctx, rctx = _context(left, right)
        query = char_ngrams(f"{lctx} {rctx}")
        scores = self._bm25.get_scores(query)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:pool]
        out: list[Parallel] = []
        for i in order:
            if scores[i] <= 0:
                break
            ln = self.lines[i]
            if exclude_inscription and ln.inscription_id == exclude_inscription:
                continue
            al = align(ln.text, lctx, rctx, gap_chars)
            ctx_len = len(lctx.strip()) + len(rctx.strip())
            exact = 100.0 * (al.left_len + al.right_len) / max(1, ctx_len)
            fuzzy = fuzz.partial_ratio(f"{lctx}{rctx}".strip(), ln.text)
            score = 0.7 * min(100.0, exact) + 0.3 * fuzzy
            out.append(Parallel(ln.inscription_id, ln.line_n, ln.text, ln.source_url, round(score, 2), al.fill))
        out.sort(key=lambda p: p.score, reverse=True)
        return out[:k]
