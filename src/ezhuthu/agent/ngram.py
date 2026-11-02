"""Character n-gram language model (stupid backoff) with beam search for gap filling."""

from __future__ import annotations

import heapq
import math
from collections import Counter, defaultdict
from collections.abc import Iterable

from .text import akshara_len, normalize_iso

BOS = "\x02"
EOS = "\x03"
MAX_CHARS_PER_LETTER = 3  # longest ISO spelling of one Tamil letter (kai, r̥̄ in NFC), for the beam's step cap


class CharNgram:
    def __init__(self, order: int = 5, backoff: float = 0.4):
        self.order = order
        self.backoff = backoff
        self.counts: list[dict[str, Counter[str]]] = [defaultdict(Counter) for _ in range(order)]
        self.totals: list[dict[str, int]] = [defaultdict(int) for _ in range(order)]
        self.vocab: set[str] = set()

    def fit(self, lines: Iterable[str]) -> CharNgram:
        for raw in lines:
            line = BOS * (self.order - 1) + normalize_iso(raw) + EOS
            for i in range(self.order - 1, len(line)):
                ch = line[i]
                self.vocab.add(ch)
                for n in range(self.order):
                    ctx = line[i - n: i]
                    self.counts[n][ctx][ch] += 1
                    self.totals[n][ctx] += 1
        return self

    def logprob(self, ctx: str, ch: str) -> float:
        mult = 1.0
        for n in range(self.order - 1, -1, -1):
            c = ctx[-n:] if n else ""
            if len(c) < n:
                continue
            tot = self.totals[n].get(c, 0)
            if tot:
                cnt = self.counts[n][c].get(ch, 0)
                if cnt:
                    return math.log(mult * cnt / tot)
            mult *= self.backoff
        return math.log(mult / max(1, len(self.vocab) + 1))

    def score(self, ctx: str, text: str) -> float:
        lp = 0.0
        for ch in text:
            lp += self.logprob(ctx, ch)
            ctx += ch
        return lp

    def fill(self, left: str, right: str, length: int, *, k: int = 5, beam: int = 16) -> list[tuple[str, float]]:
        """Top-k strings of ``length`` Tamil letters (aksharas, the unit of ``gap_chars``) between left and right,
        scored by fill + right continuation.

        The model is over ISO characters, and a letter is 1-3 of them (``k``, ``ka``, ``kai``), so the beam grows
        one character at a time, drops strings past ``length`` letters and collects every string of exactly
        ``length`` letters (issue #26: it used to emit ``length`` ISO characters, about half the letters)."""
        if not self.vocab or length <= 0:
            return []
        left_ctx = BOS * (self.order - 1) + normalize_iso(left) + (" " if left.endswith(" ") else "")
        right_n = normalize_iso(right)
        right_n = (" " + right_n) if right.startswith(" ") and right_n else right_n
        alphabet = [c for c in self.vocab if c not in (BOS, EOS)]
        letters: dict[str, int] = {}

        def n_letters(s: str) -> int:
            if s not in letters:
                letters[s] = akshara_len(s)
            return letters[s]

        beams: list[tuple[float, str]] = [(0.0, "")]
        done: dict[str, float] = {}
        for _ in range(MAX_CHARS_PER_LETTER * length + 4):  # + a few spaces/hyphens (not letters)
            nxt: list[tuple[float, str]] = []
            for lp, s in beams:
                ctx = left_ctx + s
                for ch in alphabet:
                    nxt.append((lp + self.logprob(ctx, ch), s + ch))
            # 2x the beam before the overshoot filter, so dropping too-long strings does not starve the beam
            beams = [(lp, s) for lp, s in heapq.nlargest(2 * beam, nxt, key=lambda x: x[0])
                     if n_letters(s) <= length][:beam]
            for lp, s in beams:
                if n_letters(s) == length and s.strip():
                    done[s] = max(lp, done.get(s, -math.inf))
            if not beams:
                break
        tail = right_n[: self.order] if right_n else EOS
        scored = [(s, lp + self.score(left_ctx + s, tail)) for s, lp in done.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        out, seen = [], set()
        for s, lp in scored:
            t = s.strip()
            if t and t not in seen:
                seen.add(t)
                out.append((t, lp))
            if len(out) >= k:
                break
        return out
