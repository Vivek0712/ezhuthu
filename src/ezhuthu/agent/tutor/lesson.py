"""Lesson Builder: levelled practice items from a (restored) inscription, plus the letter bank for tests."""

from __future__ import annotations

import random
import re
import uuid
from dataclasses import asdict, dataclass
from typing import Any

from ..text import (
    LEVELS,
    aksharas,
    chola_orthography,
    iso_to_tamil,
    looks_tamil,
    normalize_iso,
    render_level,
    tamil_to_iso,
)

PROMPTS = {
    "letter": ("இந்த எழுத்தைப் படியுங்கள். ஒலியைத் தமிழிலோ ISO எழுத்திலோ தட்டச்சு செய்யுங்கள்.",
               "Read this letter. Type its sound in Tamil or ISO-15919."),
    "word": ("இந்தச் சொல்லைப் படியுங்கள்.", "Read this word."),
    "line": ("இந்த வரியைப் படியுங்கள்.", "Read this line."),
}

# Letters for pre/post tests: common aksharas across vowel classes and the Tamil-specific consonants.
LETTER_BANK = (
    "a", "ā", "i", "u", "e", "ka", "ca", "ṭa", "ta", "pa", "ma", "ya", "ra", "la", "va", "ḻa", "ḷa", "ṟa",
    "ṉa", "ṇa", "ña", "ṅa", "ki", "ku", "kā", "ti", "mu", "pi", "ṭu", "ṟu", "nā", "kō", "mē", "tu",
)
ASSESSMENT_ITEMS_PER_LEVEL = 2  # 5 levels x 2 = the 10 items the contract specifies


@dataclass
class Item:
    item_id: str
    type: str  # letter | word | line
    script_level: str
    answer: str  # ISO-15919, never sent to the client
    glyph_text: str | None
    glyph_svg: str | None
    font: str | None
    prompt_ta: str
    prompt_en: str
    phase: str = "lesson"  # lesson | pre | post

    def to_api(self) -> dict[str, Any]:
        d = {"item_id": self.item_id, "type": self.type, "prompt_ta": self.prompt_ta, "prompt_en": self.prompt_en,
             "script_level": self.script_level, "answer_hidden": True, "font": self.font}
        if self.glyph_svg:
            d["glyph_svg"] = self.glyph_svg
        d["glyph_text"] = self.glyph_text
        return d

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_item(kind: str, iso: str, level: str, phase: str = "lesson") -> Item:
    r = render_level(iso, level)
    ta, en = PROMPTS[kind]
    return Item(item_id=f"{phase}-{uuid.uuid4().hex[:10]}", type=kind, script_level=level, answer=iso,
                glyph_text=r["glyph_text"], glyph_svg=r["glyph_svg"], font=r["font"], prompt_ta=ta, prompt_en=en,
                phase=phase)


_WORD_RE = re.compile(r"[^\s\[\]?0-9.,|/-]+")


def words_of(text: str) -> list[str]:
    """Words with no gap markers or digits."""
    clean = re.sub(r"\[\?\d*\]", " ", text)
    return [w for w in _WORD_RE.findall(normalize_iso(clean)) if len(w) >= 2]


def build_items(text: str, level: str, *, n_letters: int = 6, n_words: int = 3, seed: int | None = None) -> list[Item]:
    """Letters first (distinct aksharas in order of appearance), then words, then one line."""
    if level not in LEVELS:
        raise ValueError(f"level must be one of {LEVELS}")
    rng = random.Random(seed)
    lines = [ln for ln in text.split("\n") if ln.strip()]
    words = words_of(text)
    letters: list[str] = []
    for w in words:
        for a in aksharas(w):
            if a not in letters:
                letters.append(a)
    # Prefer consonant+vowel and vowel letters (what learners read first); pure consonants fill the rest.
    voiced = [a for a in letters if a[-1] in "aāiīuūeēoō"] + [a for a in letters if a[-1] not in "aāiīuūeēoō"]
    items = [make_item("letter", a, level) for a in voiced[:n_letters]]
    # Prefer mid-length words (3-6 aksharas): long compounds are for the line item.
    uniq = list(dict.fromkeys(words))
    pool = [w for w in uniq if 3 <= len(aksharas(w)) <= 6]
    picked = rng.sample(pool, min(n_words, len(pool)))
    picked += [w for w in uniq if w not in picked][: n_words - len(picked)]
    for w in picked:
        items.append(make_item("word", w, level))
    clean_lines = [ln for ln in lines if "[?" not in ln] or lines
    if clean_lines:
        line = min(clean_lines, key=lambda x: abs(len(x) - 40))
        items.append(make_item("line", normalize_iso(re.sub(r"\[\?\d*\]", "…", line)), level))
    return items


def assessment_items(phase: str, seed: int) -> list[Item]:
    rng = random.Random(f"{seed}:{phase}")
    out = []
    for level in LEVELS:
        for a in rng.sample(LETTER_BANK, ASSESSMENT_ITEMS_PER_LEVEL):
            out.append(make_item("letter", a, level, phase=phase))
    return out


def answer_to_iso(answer: str) -> str:
    a = (answer or "").strip()
    return normalize_iso(tamil_to_iso(a) if looks_tamil(a) else a)


def _canon(s: str, level: str) -> str:
    s = normalize_iso(s).replace("…", "").replace(" ", "")
    if level in ("L2", "L3", "L4", "L5"):  # pre-modern scripts do not mark e/ē, o/ō length
        s = chola_orthography(s)
    return s


def cer(ref: str, hyp: str) -> float:
    from rapidfuzz.distance import Levenshtein

    return Levenshtein.distance(ref, hyp) / max(1, len(ref))


def grade(item: Item, answer: str) -> tuple[bool, float]:
    """(correct, character error rate). Letters and words need an exact reading; lines allow CER <= 0.15."""
    ref = _canon(item.answer, item.script_level)
    hyp = _canon(answer_to_iso(answer), item.script_level)
    if item.type == "letter" and ref.endswith("a") and hyp == ref[:-1]:
        hyp = ref  # "k" for "ka": the inherent vowel is often left off
    err = cer(ref, hyp)
    return (err == 0.0 if item.type in ("letter", "word") else err <= 0.15), round(err, 4)


def tamil_of(iso: str) -> str:
    return iso_to_tamil(iso)
