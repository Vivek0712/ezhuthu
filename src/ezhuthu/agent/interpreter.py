"""Interpreter: letters in, words, a modern Tamil phrase and a plain meaning out.

The Reader gives letters (one modern Tamil akshara per carved letter, with its probability) and the Restorer fills
or leaves open the letters it could not read. Inscriptions are carved without word spaces, in older spelling. The
Interpreter takes that letter stream and asks the model to

1. **divide it into words**, naming for each word the ids of the letters it is made of (so a page can animate the
   letters sliding into word groups, and nothing is attributed to letters that were not read);
2. **arrange the words as a readable modern Tamil phrase** (inscriptional conventions resolved: a missing pulli,
   a short vowel for a long one, a doubled consonant, sandhi), with its ISO-15919 transliteration;
3. **say what it means**, in one or two plain lines of English and of modern Tamil.

Grounding, before the model call and without a model:

* **lexicon**: words attested in published editions (the DHARMA *train* split, ``load_corpus_lines``; val/test are
  never read) that occur in the letter stream at letter boundaries, with how often they are attested;
* **ontology**: ``find_entities`` on the run-on transliteration (rulers, places, measures, formulae ...).

After the call, every word is checked against the same lexicon (``attested``). Routing follows the Reader: Sonnet 4.6
(``llm.default``) first, Opus 4.6 (``llm.escalate``) when Sonnet's own probability is under
``routing.escalate_if_confidence_below``; the more confident answer with words is kept. Replies are cached by the LLM
client (``.cache/llm``). Used offline for the home hero (scripts/hero_read.py interpret) and by ``POST /api/interpret``.
"""

from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from .config import ModelsConfig, load_models_config
from .llm import LiveCallsDisabled, LLMClient, LLMResponse, short_name
from .text import GAP_RE, iso_to_tamil, looks_tamil, normalize_iso, tamil_to_iso

log = logging.getLogger(__name__)

INTERPRETER_SYSTEM = (
    "You are an expert Tamil epigraphist helping a learner understand a stone inscription. Inscriptions are carved "
    "without spaces between words and in older spelling. You divide the letters into words, write them in today's "
    "Tamil spelling, and say plainly what they mean. You never invent history: you use only what the letters say, "
    "and you say when a word is unclear. Answer with JSON only."
)
MAX_LETTERS = 400
MAX_LEXICON_HINTS = 24
MIN_HINT_LETTERS = 3
UNREAD = "?"  # a letter nobody could read (the Reader named none, or the Restorer left the gap open)
_TA_AKSHARA = re.compile(r"[அ-ஔ]|[க-ஹ](?:்|[ா-ௌ]்?)?|ஃ")


class InterpretError(ValueError):
    status = 422

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Letter:
    """One letter of the stream: line and index (0-based), the modern Tamil letter ('' or None if unread) and the
    probability that it is right (None when it came from typed text)."""

    line: int
    index: int
    ta: str | None
    c: float | None = None

    @property
    def id(self) -> str:
        return f"{self.line + 1}.{self.index + 1}"

    @property
    def unread(self) -> bool:
        return not self.ta


def ta_aksharas(text: str) -> list[str]:
    """Split modern Tamil text into aksharas (vowel, consonant + vowel sign, consonant + pulli)."""
    return _TA_AKSHARA.findall(unicodedata.normalize("NFC", text))


def letters_from_text(text: str) -> list[list[Letter]]:
    """Typed or read text (Tamil script or ISO-15919, ``[?N]`` / ``[?]`` gaps) as letter lines. Spaces are dropped:
    the Interpreter divides the words itself. A ``[?N]`` gap becomes N unread letters (``[?]`` one)."""
    lines: list[list[Letter]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        out: list[Letter] = []
        pos = 0
        for m in [*GAP_RE.finditer(raw), None]:
            chunk = raw[pos: m.start() if m else len(raw)]
            ta = chunk if looks_tamil(chunk) else iso_to_tamil(normalize_iso(chunk))
            for a in ta_aksharas(ta):
                out.append(Letter(len(lines), len(out), a))
            if m:
                for _ in range(int(m.group(1) or 1)):
                    out.append(Letter(len(lines), len(out), None))
                pos = m.end()
        if out:
            lines.append(out)
    return lines


# ---- lexicon (DHARMA train split) -------------------------------------------------------------------------------

_WORD_SPLIT = re.compile(r"[\s\-=·.,;:|/()\[\]'’‘?0-9]+")


@lru_cache(maxsize=1)
def train_lexicon() -> dict[str, int]:
    """Tamil-script word -> number of attestations in the train-split corpus lines (words of 2+ letters)."""
    from .data import load_corpus_lines

    iso_counts: Counter[str] = Counter()
    for ln in load_corpus_lines():
        for w in _WORD_SPLIT.split(ln.text):
            if len(w) >= 2 and re.search(r"[aāiīuūeēoō]", w):
                iso_counts[w] += 1
    words = sorted(iso_counts)
    # One transliteration call for all distinct words (a call per word takes seconds for ~30k words).
    tamil = _translit_many(words)
    counts: Counter[str] = Counter()
    for w, ta in zip(words, tamil, strict=True):
        aks = ta_aksharas(ta)
        # A word that starts with a doubled consonant (க்கு...) is the tail of a sandhi split, not a word; Grantha
        # conjuncts (ஶ்ரீ, ஸ்வஸ்தி) are kept.
        doubled = aks[0].endswith("்") and len(aks) > 1 and aks[1][0] == aks[0][0]
        if len(aks) >= 2 and "".join(aks) == ta and not doubled:
            counts[ta] += iso_counts[w]
    return dict(counts)


def _translit_many(words: list[str]) -> list[str]:
    """ISO -> Tamil for many words at once, joined by newlines (the transliterator keeps line breaks)."""
    out: list[str] = []
    step = 2000
    for k in range(0, len(words), step):
        chunk = words[k: k + step]
        res = iso_to_tamil.__wrapped__("\n".join(chunk)).split("\n")  # type: ignore[attr-defined]
        out.extend(res if len(res) == len(chunk) else [iso_to_tamil(w) for w in chunk])
    return out


def _strip_pulli(s: str) -> str:
    """Inscriptions rarely mark the pulli: compare words with and without it."""
    return s.replace("்", "")


@lru_cache(maxsize=1)
def _lexicon_bare() -> dict[str, tuple[str, int]]:
    out: dict[str, tuple[str, int]] = {}
    for w, n in train_lexicon().items():
        k = _strip_pulli(w)
        if k not in out or n > out[k][1]:
            out[k] = (w, n)
    return out


def attested(word_ta: str, lexicon: dict[str, int] | None = None) -> bool:
    lex = train_lexicon() if lexicon is None else lexicon
    w = unicodedata.normalize("NFC", word_ta).replace(" ", "")
    if w in lex:
        return True
    bare = _lexicon_bare() if lexicon is None else {_strip_pulli(k): (k, v) for k, v in lex.items()}
    return _strip_pulli(w) in bare


def lexicon_hints(lines: list[list[Letter]], *, lexicon: dict[str, int] | None = None,
                  k: int = MAX_LEXICON_HINTS) -> list[dict[str, Any]]:
    """Attested words that occur in the run-on letter stream, starting and ending at letter boundaries (a word may
    run on to the next line), compared without pulli. Longest and most attested first."""
    lex = train_lexicon() if lexicon is None else lexicon
    bare: dict[str, tuple[str, int]] = {}
    for w, n in lex.items():
        b = _strip_pulli(w)
        if b not in bare or n > bare[b][1]:
            bare[b] = (w, n)
    stream = [ltr for line in lines for ltr in line]
    found: dict[str, dict[str, Any]] = {}
    for i in range(len(stream)):
        if stream[i].unread:
            continue
        s = ""
        for j in range(i, min(len(stream), i + 10)):
            if stream[j].unread:
                break
            s += _strip_pulli(stream[j].ta or "")
            n = j - i + 1
            if n >= MIN_HINT_LETTERS and s in bare:
                w, cnt = bare[s]
                if w not in found:
                    found[w] = {"ta": w, "iso": tamil_to_iso(w), "attested": cnt,
                                "letters": [stream[x].id for x in range(i, j + 1)]}
    ranked = sorted(found.values(), key=lambda h: (-len(h["letters"]), -h["attested"], h["letters"][0]))
    return ranked[:k]


# ---- prompt and reply --------------------------------------------------------------------------------------------

def interpret_prompt(lines: list[list[Letter]], *, lex: list[dict[str, Any]], entities: list[dict[str, str]],
                     context: str | None = None) -> str:
    def fmt(ltr: Letter) -> str:
        if ltr.unread:
            return f"{ltr.id} {UNREAD}"
        return f"{ltr.id} {ltr.ta}" + (f" ({ltr.c:.2f})" if ltr.c is not None else "")

    body = "\n".join(f"Line {n + 1}: " + " · ".join(fmt(x) for x in line) for n, line in enumerate(lines))
    lex_txt = "\n".join(f"- {h['ta']} ({h['iso']}), attested {h['attested']}x, letters {h['letters'][0]}-"
                        f"{h['letters'][-1]}" for h in lex) or "- none"
    ent_txt = "\n".join(f"- {e['kind']}: {e['label']}" for e in entities) or "- none"
    ctx = f"\nAbout the stone: {context[:300]}" if context else ""
    return (
        "Letters read from a photo of a Tamil inscription, line by line in reading order. Each letter has an id "
        "(line.letter), the modern Tamil letter it was matched to and, in brackets, the probability that the match "
        f"is right. {UNREAD!r} is a letter nobody could read. The stone has no word spaces and older spelling; a "
        "word may run on from one line to the next." + ctx + "\n\n" + body + "\n\n"
        "Words from published editions (DHARMA) that occur in this letter stream, as a hint only:\n" + lex_txt + "\n"
        "Names and terms the ontology found:\n" + ent_txt + "\n\n"
        "1. WORDS: divide the letters into words, in reading order. Give each word the ids of its letters, in "
        "order; use every id at most once; leave out only letters that belong to no word you can make out.\n"
        "2. For each word: its spelling in today's Tamil (inscriptional conventions resolved: missing pulli, vowel "
        "length, doubled consonants), ISO-15919, an English gloss of 1 to 4 words, and your probability (0 to 1) "
        "that the word is right. An unclear word gets a low probability; never force a meaning.\n"
        "3. PHRASE: the words arranged as a readable phrase in today's Tamil (same order; sandhi and spelling "
        "normalised; an unreadable stretch as …), and its ISO-15919.\n"
        "4. MEANING: what the words say, in plain English (at most 30 words) and in plain today's Tamil (at most "
        "25 words), for a learner: start with the content, not with remarks about the reading. If this is a "
        "fragment of a longer text, say what kind of passage it seems to be. No dates, kings or events the letters "
        "do not name.\n"
        "5. notes: at most two short sentences on the most uncertain words.\n"
        "Reply with ONE line of JSON: {\"words\": [{\"ids\": [\"1.1\", \"1.2\"], \"ta\": \"...\", \"iso\": \"...\", "
        "\"en\": \"...\", \"p\": 0.0}], \"phrase_ta\": \"...\", \"phrase_iso\": \"...\", \"meaning_en\": \"...\", "
        "\"meaning_ta\": \"...\", \"notes\": \"...\", \"p\": 0.0} where the last p is your probability that the "
        "meaning is right."
    )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _prob(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else round(min(1.0, max(0.0, f)), 3)


def _clean(v: Any, n: int) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip()[:n]


def parse_interpret_reply(text: str, lines: list[list[Letter]]) -> dict[str, Any]:
    """Validate the model's words against the letters: unknown ids are dropped, each id is used once, words keep
    reading order (a word whose letters all come before the previous word's last letter is dropped)."""
    raw = text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\s*|\s*```$", "", raw)
    m = _JSON_RE.search(raw)
    data: dict[str, Any] = {}
    if m:
        try:
            parsed = json.loads(m.group(0))
            data = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            data = {}
    stream = [x for line in lines for x in line]
    order = {ltr.id: k for k, ltr in enumerate(stream)}
    groups: list[list[int]] = []  # reading-order positions of each kept word's letters
    kept: list[dict[str, Any]] = []
    for w in data.get("words") or []:
        if not isinstance(w, dict):
            continue
        ta = unicodedata.normalize("NFC", _clean(w.get("ta"), 60))
        pos = sorted({order[str(i)] for i in (w.get("ids") or w.get("letters") or []) if str(i) in order})
        if not pos or not ta:
            continue
        if groups:
            prev = groups[-1]
            # A letter shared with the previous word (sandhi: kuṭik-kuḷam) goes to this word, if the previous word
            # keeps at least one letter; letters before the previous word's end are otherwise dropped.
            shared = [p for p in pos if p in prev]
            if shared and len(prev) > len(shared) and min(shared) > prev[0]:
                groups[-1] = [p for p in prev if p not in shared]
            pos = [p for p in pos if p > groups[-1][-1]]
            if not pos:
                continue
            # The word's spelling starts with the previous word's last letter but its ids do not (குளம் given ள ம்
            # while கு closed the previous word): move that letter over, if the previous word keeps one.
            head = ta_aksharas(ta)[:1]
            prev = groups[-1]
            last = stream[prev[-1]]
            if (head and len(prev) > 1 and prev[-1] == pos[0] - 1 and last.ta
                    and _strip_pulli(head[0]) != _strip_pulli(stream[pos[0]].ta or "")
                    and _strip_pulli(head[0]) == _strip_pulli(last.ta)):
                groups[-1] = prev[:-1]
                pos = [prev[-1], *pos]
        # An unread letter inside the word's span belongs to it (the model may leave '?' out of the ids).
        pos = sorted(set(pos) | {k for k in range(pos[0], pos[-1] + 1) if stream[k].unread})
        groups.append(pos)
        kept.append(w | {"_ta": ta})
    words = []
    for w, pos in zip(kept, groups, strict=True):
        ta = w["_ta"]
        iso = _clean(w.get("iso"), 80) or tamil_to_iso(ta)
        words.append({"tamil": ta, "iso": unicodedata.normalize("NFC", iso), "en": _clean(w.get("en"), 60) or None,
                      "letters": [[stream[p].line, stream[p].index] for p in pos], "confidence": _prob(w.get("p"))})
    used = {p for g in groups for p in g}
    unassigned = [[x.line, x.index] for k, x in enumerate(stream) if k not in used and not x.unread]
    return {
        "words": words,
        "phrase_tamil": unicodedata.normalize("NFC", _clean(data.get("phrase_ta"), 400)) or None,
        "phrase_iso": unicodedata.normalize("NFC", _clean(data.get("phrase_iso"), 500)) or None,
        "meaning_en": _clean(data.get("meaning_en"), 400) or None,
        "meaning_ta": unicodedata.normalize("NFC", _clean(data.get("meaning_ta"), 400)) or None,
        "notes": _clean(data.get("notes"), 400) or None,
        "confidence": _prob(data.get("p")),
        "unassigned": unassigned,
    }


# ---- the agent ---------------------------------------------------------------------------------------------------

class Interpreter:
    """Letters -> words -> phrase -> meaning. ``llm`` is any ``LLMClient`` (BedrockLLM, BudgetedLLM, FakeLLM)."""

    def __init__(self, llm: LLMClient | None, config: ModelsConfig | None = None, *, ontology: Any = "default",
                 lexicon: dict[str, int] | None = None, max_tokens: int = 2000):
        self.llm = llm
        self.config = config or (llm.config if llm is not None else load_models_config())
        self._ontology = ontology
        self._lexicon = lexicon
        self.max_tokens = max_tokens

    @property
    def escalate_below(self) -> float:
        return self.config.routing.escalate_if_confidence_below

    def _entities(self, lines: list[list[Letter]]) -> list[dict[str, str]]:
        onto = self._ontology
        if onto is None:
            return []
        if onto == "default":
            try:
                from .ontology_port import get_ontology

                onto = get_ontology()
            except Exception as exc:  # noqa: BLE001  (no ontology here: interpret without it)
                log.warning("interpreter: no ontology (%s)", type(exc).__name__)
                return []
        iso = " ".join("".join(tamil_to_iso(x.ta) for x in line if x.ta) for line in lines)
        try:
            hints = onto.find_entities(iso)
        except Exception as exc:  # noqa: BLE001
            log.warning("interpreter: ontology lookup failed (%s)", type(exc).__name__)
            return []
        out, seen = [], set()
        for h in hints[:12]:
            if h.id not in seen:
                seen.add(h.id)
                out.append({"id": h.id, "kind": h.kind, "label": h.label})
        return out

    def _ask(self, role: str, prompt: str, lines: list[list[Letter]]) -> tuple[dict[str, Any], LLMResponse]:
        r = self.llm.complete(role, INTERPRETER_SYSTEM, prompt, max_tokens=self.max_tokens)  # type: ignore[union-attr]
        return parse_interpret_reply(r.text, lines), r

    def interpret(self, lines: list[list[Letter]], *, context: str | None = None,
                  router: str = "routed") -> dict[str, Any]:
        if self.llm is None:
            raise LiveCallsDisabled("interpreting needs a live model (EZHUTHU_LIVE=1)")
        n = sum(len(x) for x in lines)
        if not n:
            raise InterpretError("no_text", "no letters to interpret")
        if n > MAX_LETTERS:
            raise InterpretError("too_long", f"at most {MAX_LETTERS} letters per request")
        if all(x.unread for line in lines for x in line):
            raise InterpretError("no_text", "every letter is unread")
        lex = lexicon_hints(lines, lexicon=self._lexicon)
        ents = self._entities(lines)
        prompt = interpret_prompt(lines, lex=lex, entities=ents, context=context)
        first_role = "escalate" if router == "opus" else "default"
        best, resp = self._ask(first_role, prompt, lines)
        models = [short_name(resp.model_id)]
        model = models[0]
        escalated = first_role == "escalate"
        conf = best["confidence"]
        if router == "routed" and (conf is None or conf < self.escalate_below or not best["words"]):
            try:
                second, r2 = self._ask("escalate", prompt, lines)
            except LiveCallsDisabled:
                second = None
            except Exception as exc:  # noqa: BLE001  (throttled / Bedrock error: keep the first answer)
                log.warning("interpreter escalation failed (%s); keeping the first answer", type(exc).__name__)
                second = None
            if second is not None:
                escalated = True
                models.append(short_name(r2.model_id))
                if second["words"] and (not best["words"] or (second["confidence"] or 0) > (conf or 0)):
                    best, model = second, short_name(r2.model_id)
        for w in best["words"]:
            w["attested"] = attested(w["tamil"], self._lexicon)
        best.update({"model": model, "models_used": list(dict.fromkeys(models)), "escalated": escalated,
                     "lexicon_hints": lex, "ontology_hints": ents,
                     "letters": n, "words_attested": sum(w["attested"] for w in best["words"])})
        return best

    def interpret_text(self, text: str, **kw: Any) -> dict[str, Any]:
        lines = letters_from_text(text)
        out = self.interpret(lines, **kw)
        out["input"] = {"lines": ["".join(x.ta or UNREAD for x in line) for line in lines]}
        return out
