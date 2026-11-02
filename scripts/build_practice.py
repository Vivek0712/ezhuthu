"""Build the app's instant practice banks from the TRAIN split only.

Writes JSON under app/web/src/practice/banks/ for the client-side practice sessions (no LLM call):

- letters.json   era letter -> modern Tamil letter. Tamil-Brahmi and Grantha (the app's stand-in for Pallava letters)
                 are Unicode text drawn with the Noto Sans Brahmi / Noto Sans Grantha web fonts (SIL OFL 1.1); the
                 Vatteluttu shapes are the design system's teaching drawings (design/glyphs/vatteluttu.json, pending
                 epigrapher review). Which letters are drilled, and how often, comes from letter counts over TRAIN
                 inscription text.
- words.json     reading drill: real words from TRAIN inscriptions, ISO-15919 -> Tamil script, Tamil -> ISO, and
                 "Chola spelling" (no puḷḷi, no e/ē or o/ō contrast) -> today's spelling.
- gaps.json      fill the gap: a span the DHARMA editors restored in a TRAIN inscription (benchmark/items.train.jsonl,
                 kind "supplied"), masked. The answer is the editors' restoration; the other options are the
                 strongest different fills of a character 5-gram model fitted on TRAIN corpus lines (the model the
                 Restorer itself uses), topped up with other TRAIN restorations of the same length.
- formulas.json  spot the formula: common inscription formulas found in TRAIN lines, with their meaning.
- try.json       the home page's "try one now" mini-drill (a few easy letter and word items from the banks above).
- worked-example.json  the How-it-works page's worked example: one TRAIN passage (the Māmallapuram calf pasture) and
                 the restorer's real recorded answer for it (app/web/src/samples/recorded-restores.json, read only).

Never VAL or TEST: every inscription used is in the train split, shares no stone with a held-out inscription and is
not the inscription of any VAL/TEST item (tests/test_practice_banks.py checks the output and that it matches this
script). Deterministic: every choice goes through random.Random seeded from SEED and the item id.

Run: PYTHONPATH=src .venv/bin/python scripts/build_practice.py          (add --check to verify the committed files)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "benchmark"
OUT = REPO / "app" / "web" / "src" / "practice" / "banks"
SAMPLES = REPO / "app" / "web" / "src" / "samples"
SEED = 2026_11_02
GAP_RE = re.compile(r"\[\?\d*\]")
TA_REVIEW = "pending a native-speaker check"

TAMIL_CONS = ["k", "ṅ", "c", "ñ", "ṭ", "ṇ", "t", "n", "p", "m", "y", "r", "l", "v", "ḻ", "ḷ", "ṟ", "ṉ"]
TAMIL_VOWELS = ["a", "ā", "i", "ī", "u", "ū", "e", "ē", "ai", "o", "ō", "au"]
VOWEL_NAME = {"ā": "ā", "i": "i", "ī": "ī", "u": "u", "ū": "ū", "e": "e", "ē": "ē", "ai": "ai", "o": "o", "ō": "ō",
              "au": "au"}
# Grantha was made for Sanskrit: it has no letter of its own for ḻ, ṟ or ṉ (design/glyphs/REFERENCES.md).
NOT_IN_GRANTHA = {"ḻ", "ṟ", "ṉ"}


# ---------------------------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------------------------
def rng_for(*parts: object) -> random.Random:
    h = hashlib.sha256(":".join(str(p) for p in (SEED, *parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def load_jsonl(name: str) -> list[dict]:
    with open(BENCH / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def held_out_ids(ins: dict[str, dict]) -> set[str]:
    """Every inscription that is not TRAIN, every inscription of a VAL/TEST item, and every TRAIN inscription that
    shares a stone with one of them."""
    held = {i for i, r in ins.items() if r["split"] != "train"}
    for name in ("items.val.jsonl", "items.test.jsonl", "items.test-hard.jsonl", "items.test-age.jsonl"):
        held |= {r["inscription_id"] for r in load_jsonl(name)}
    for i, r in ins.items():
        if any(s in held for s in r.get("same_stone_as") or []):
            held.add(i)
    return held


def to_tamil(iso: str) -> str:
    from ezhuthu.corpus.script import iso_to_tamil_display

    return iso_to_tamil_display(iso)


def source(ins: dict, line_n: str | None = None) -> dict:
    out = {"inscription_id": ins["id"], "title": ins["title"], "url": ins["dharmalekha_url"]}
    if line_n is not None:
        out["line_n"] = str(line_n)
    return out


def join_lines(lines: list[str]) -> str:
    """Running text from edition lines: '-x' continues the previous word, '--x' continues it with a hyphen."""
    out = ""
    for i, a in enumerate(lines):
        if i == 0:
            out = a.lstrip("-")
        elif a.startswith("--"):
            out += "-" + a[2:]
        elif a.startswith("-"):
            out += a[1:]
        else:
            out += " " + a
    return out.strip()


def clean_token(tok: str) -> str | None:
    """A word fit for a drill: Tamil letters and hyphens only (no gap, numeral, editorial or elision mark, no
    upper-case independent-vowel convention), or None."""
    tok = nfc(tok.replace("=", "").strip(".,;:|/()"))
    if not tok or tok != tok.lower() or GAP_RE.search(tok):
        return None
    if re.search(r"[^a-zāīūēōṅñṭṇḻḷṟṉṁṃḥśṣr̥̥̄-]", tok):
        return None
    tok = tok.strip("-")
    return tok or None


WORD_INITIAL_BAD = ("ṅ", "ṇ", "ḻ", "ḷ", "ṟ", "ṉ", "r", "l")


def is_whole_word(w: str) -> bool:
    """A token that looks like a whole Tamil word, not a fragment cut at a line end or a gap: it starts with a
    vowel or a consonant with its vowel (never a puḷḷi consonant, nor a letter Tamil words do not start with)
    and does not end in a hyphenated sandhi consonant ("pattu-p")."""
    aks = akshara_list(w)
    if not aks or re.search(r"-[^aāiīuūeēoō-]+$", w) or re.match(r"^[^aāiīuūeēoō-]+-", w):
        return False
    c, v = split_cv(aks[0])
    if c is not None and v is None:
        return False
    return not w.startswith(WORD_INITIAL_BAD)


def akshara_list(iso: str) -> list[str]:
    from ezhuthu.agent.text import aksharas

    return aksharas(iso.replace("-", ""))


def is_tamil_akshara(a: str) -> bool:
    if a in TAMIL_VOWELS:
        return True
    for c in sorted(TAMIL_CONS, key=len, reverse=True):
        if a.startswith(c):
            rest = a[len(c):]
            return rest == "" or rest in TAMIL_VOWELS
    return False


def split_cv(a: str) -> tuple[str | None, str | None]:
    if a in TAMIL_VOWELS:
        return None, a
    for c in sorted(TAMIL_CONS, key=len, reverse=True):
        if a.startswith(c):
            return c, a[len(c):] or None
    return None, None


def lev(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def shuffle_options(rng: random.Random, answer: dict, distractors: list[dict]) -> tuple[list[dict], int]:
    opts = [answer, *distractors]
    rng.shuffle(opts)
    return opts, opts.index(answer)


# ---------------------------------------------------------------------------------------------------------------
# corpus (TRAIN only)
# ---------------------------------------------------------------------------------------------------------------
class Corpus:
    def __init__(self) -> None:
        self.ins = {r["id"]: r for r in load_jsonl("inscriptions.jsonl")}
        self.held = held_out_ids(self.ins)
        self.train = {i: r for i, r in self.ins.items() if i not in self.held and r["split"] == "train"}
        self.lines = [r for r in load_jsonl("corpus_lines.jsonl")
                      if r["inscription_id"] in self.train and r["lang"] == "tam-Latn"]

    def tamil_texts(self) -> dict[str, str]:
        """Running ISO text per TRAIN inscription, Tamil-language lines only."""
        by: dict[str, list[str]] = defaultdict(list)
        for r in self.lines:
            by[r["inscription_id"]].append(r["text"])
        return {i: join_lines(ls) for i, ls in sorted(by.items())}


# ---------------------------------------------------------------------------------------------------------------
# letters
# ---------------------------------------------------------------------------------------------------------------
def build_letters(corpus: Corpus) -> list[dict]:
    from ezhuthu.agent.text import render_level
    from ezhuthu.corpus.script import iso_to_tamil, iso_to_tamil_brahmi

    counts: Counter[str] = Counter()
    for text in corpus.tamil_texts().values():
        for tok in text.split():
            t = clean_token(tok)
            if t:
                counts.update(a for a in akshara_list(t) if is_tamil_akshara(a))
    pool = sorted((a for a, n in counts.items() if n >= 100), key=lambda a: (-counts[a], a))
    design = json.loads((REPO / "design" / "glyphs" / "vatteluttu.json").read_text(encoding="utf-8"))
    vglyphs = sorted(design["glyphs"])  # ISO keys with a drawing

    def opt(a: str) -> dict:
        return {"ta": iso_to_tamil(a), "iso": a}

    def distractors(a: str, cands: list[str], rng: random.Random) -> list[str]:
        c, v = split_cv(a)
        same_c = [x for x in cands if x != a and split_cv(x)[0] == c and c is not None]
        same_v = [x for x in cands if x != a and split_cv(x)[1] == v]
        rest = [x for x in cands if x != a]
        out: list[str] = []
        for group, k in ((same_c, 1), (same_v, 2), (rest, 3)):
            g = [x for x in group if x not in out]
            rng.shuffle(g)
            out += g[: max(0, min(k, 3 - len(out)))]
        rest2 = [x for x in rest if x not in out]
        rng.shuffle(rest2)
        out += rest2[: 3 - len(out)]
        return out[:3]

    items: list[dict] = []
    # Tamil-Brahmi
    for a in pool:
        c, v = split_cv(a)
        level = 1 if c is None or v in ("a", "ā") else 2  # vowels, ka and kā first; then other vowel signs
        glyph = iso_to_tamil_brahmi(a)
        if v is not None and "\U00011046" in glyph:
            continue  # a vowel sign stacked with the virama (short e/o): not drawn reliably by the font
        iid = f"letter:brahmi:{a}"
        rng = rng_for(iid)
        ds = distractors(a, pool, rng)
        opts, ans = shuffle_options(rng, opt(a), [opt(d) for d in ds])
        why_en, why_ta = letter_why(a, "brahmi")
        items.append({"id": iid, "level": level, "era": "brahmi", "glyph": glyph,
                      "options": opts, "answer": ans, "freq": counts[a], "why_en": why_en, "why_ta": why_ta})
    # Grantha (Pallava stand-in)
    gpool = [a for a in pool if split_cv(a)[0] not in NOT_IN_GRANTHA and split_cv(a)[1] is not None][:60]
    for a in gpool:
        glyph = render_level(a, "L3")["glyph_text"]
        if not glyph:
            continue
        iid = f"letter:grantha:{a}"
        rng = rng_for(iid)
        ds = distractors(a, gpool, rng)
        opts, ans = shuffle_options(rng, opt(a), [opt(d) for d in ds])
        why_en, why_ta = letter_why(a, "grantha")
        items.append({"id": iid, "level": 3, "era": "grantha", "glyph": glyph, "options": opts, "answer": ans,
                      "freq": counts[a], "why_en": why_en, "why_ta": why_ta})
    # Vatteluttu: two option sets per drawing (the drawings are few)
    for a in vglyphs:
        for k in (1, 2):
            iid = f"letter:vatteluttu:{a}:{k}"
            rng = rng_for(iid)
            near = [x for x in vglyphs if x != a]
            rng.shuffle(near)
            ds = near[:2] + [x for x in pool[:20] if x not in vglyphs and x != a][rng.randrange(0, 10):][:1]
            opts, ans = shuffle_options(rng, opt(a), [opt(d) for d in ds])
            why_en, why_ta = letter_why(a, "vatteluttu")
            items.append({"id": iid, "level": 3, "era": "vatteluttu", "glyph": f"vatteluttu:{a}", "options": opts,
                          "answer": ans, "freq": counts.get(a, 0), "why_en": why_en, "why_ta": why_ta})
    return items


ERA_EN = {"brahmi": "Tamil-Brahmi", "grantha": "Grantha (the closest Unicode script to Pallava letters)",
          "vatteluttu": "Vatteluttu (a drawn teaching form)"}
ERA_TA = {"brahmi": "தமிழ்-பிராமி", "grantha": "கிரந்தம் (பல்லவ எழுத்துக்கு நெருக்கமான யூனிகோட் எழுத்து)",
          "vatteluttu": "வட்டெழுத்து (கற்பிப்பதற்காக வரைந்த வடிவம்)"}


def letter_why(a: str, era: str) -> tuple[str, str]:
    from ezhuthu.corpus.script import iso_to_tamil

    c, v = split_cv(a)
    ta = iso_to_tamil(a)
    en = f"In {ERA_EN[era]} this is {a}, written {ta} in Tamil today."
    tam = f"{ERA_TA[era]} எழுத்தில் இது {a}; இன்று தமிழில் {ta} என்று எழுதுகிறோம்."
    if c and v and v != "a":
        base = iso_to_tamil(c + "a")
        en += f" The base letter is {base} ({c}a); the extra mark is the vowel sign for {VOWEL_NAME[v]}."
        tam += f" அடிப்படை எழுத்து {base} ({c}a); கூடுதல் குறி '{VOWEL_NAME[v]}' உயிர்க்குறி."
    elif c and not v:
        en += f" The mark on {c}a removes its vowel, like the dot (puḷḷi) in today's {ta}."
        tam += f" {c}a மேல் உள்ள குறி அதன் உயிரை நீக்குகிறது, இன்றைய {ta} இல் உள்ள புள்ளி போல."
    return en, tam


# ---------------------------------------------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------------------------------------------
def build_words(corpus: Corpus) -> list[dict]:
    from ezhuthu.agent.text import chola_orthography
    from ezhuthu.corpus.script import iso_to_tamil

    occ: dict[str, Counter[str]] = defaultdict(Counter)
    for iid, text in corpus.tamil_texts().items():
        for tok in text.split():
            t = clean_token(tok)
            if t and is_whole_word(t) and all(is_tamil_akshara(a) for a in akshara_list(t)):
                occ[t][iid] += 1
    # Real vocabulary: seen at least 3 times, in at least 2 inscriptions; 2 to 9 letters.
    vocab = {w: c for w, c in occ.items() if sum(c.values()) >= 3 and len(c) >= 2 and 2 <= len(akshara_list(w)) <= 9}
    by_form: dict[str, str] = {}
    for w in sorted(vocab, key=lambda w: (-sum(vocab[w].values()), w)):
        key = w.replace("-", "")
        by_form.setdefault(key, w)  # one spelling per word
    words = sorted(by_form.values(), key=lambda w: (-sum(vocab[w].values()), w))
    aks = {w: akshara_list(w) for w in words}

    def level(w: str) -> int:
        n = len(aks[w])
        return 1 if n <= 3 else 2 if n <= 5 else 3

    def ex_src(w: str) -> dict:
        first = sorted(vocab[w].items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        return source(corpus.train[first])

    def near(w: str, rng: random.Random) -> list[str]:
        n = len(aks[w])
        cands = [x for x in words if x != w and abs(len(aks[x]) - n) <= 1 and iso_to_tamil(x) != iso_to_tamil(w)]
        scored = sorted(cands, key=lambda x: (lev(aks[w], aks[x]), rng.random()))
        return scored[:3]

    def parts_en(w: str) -> str:
        return " + ".join(f"{iso_to_tamil(a)} {a}" for a in aks[w])

    items: list[dict] = []
    picked = words[:420]
    for w in picked:
        n_occ, n_ins = sum(vocab[w].values()), len(vocab[w])
        for direction in ("iso2ta", "ta2iso"):
            iid = f"word:{direction}:{w}"
            rng = rng_for(iid)
            # alternate directions so each word is drilled once
            if (rng_for("dir", w).random() < 0.5) != (direction == "iso2ta"):
                continue
            ds = near(w, rng)
            if len(ds) < 3:
                continue
            o = lambda x: {"ta": to_tamil(x), "iso": x}  # noqa: E731
            opts, ans = shuffle_options(rng, o(w), [o(d) for d in ds])
            why_en = (f"{w} is written {to_tamil(w)}: {parts_en(w)}. It occurs {n_occ} times in {n_ins} "
                      "training inscriptions.")
            why_ta = (f"{w} என்பது {to_tamil(w)}: {parts_en(w)}. பயிற்சிக் கல்வெட்டுகள் {n_ins} இல் {n_occ} முறை "
                      "வருகிறது.")
            items.append({"id": iid, "level": level(w), "dir": direction, "prompt": o(w), "options": opts,
                          "answer": ans, "why_en": why_en, "why_ta": why_ta, "src": ex_src(w)})
    # Chola spelling -> today's spelling: stones of the period write no puḷḷi and no e/ē, o/ō contrast.
    for w in words[:400]:
        chola_iso = chola_orthography(w.replace("-", ""))
        chola_ta = iso_to_tamil(chola_iso).replace("்", "")
        modern_ta = iso_to_tamil(w.replace("-", ""))
        if chola_ta == modern_ta:
            continue
        alts = chola_readings(chola_iso)
        alts = [a for a in alts if iso_to_tamil(a) != modern_ta]
        if len(alts) < 3:
            continue
        iid = f"word:chola2modern:{w}"
        rng = rng_for(iid)
        rng.shuffle(alts)
        o = lambda x: {"ta": iso_to_tamil(x), "iso": x}  # noqa: E731
        opts, ans = shuffle_options(rng, o(w.replace("-", "")), [o(a) for a in alts[:3]])
        why_en = (f"On the stone: {chola_ta}. Read with today's dots and long vowels it is {modern_ta} ({w}), the "
                  "word the edition reads here; the other readings are not words in these inscriptions.")
        why_ta = (f"கல்லில்: {chola_ta}. இன்றைய புள்ளிகளுடனும் நெடில்களுடனும் இது {modern_ta} ({w}); பதிப்பு "
                  "இங்கே இப்படியே படிக்கிறது. மற்ற வாசிப்புகள் இக்கல்வெட்டுகளில் வரும் சொற்கள் அல்ல.")
        items.append({"id": iid, "level": 3, "dir": "chola2modern", "prompt": {"ta": chola_ta, "iso": chola_iso},
                      "options": opts, "answer": ans, "why_en": why_en, "why_ta": why_ta, "src": ex_src(w)})
        if sum(1 for i in items if i["dir"] == "chola2modern") >= 120:
            break
    return items


def chola_readings(chola_iso: str) -> list[str]:
    """Other ways to read an unpointed Chola spelling: each bare consonant either with puḷḷi or with 'a', and e/o
    either short or long. Returns ISO strings (at most 64)."""
    aks = akshara_list(chola_iso)
    choices: list[list[str]] = []
    for a in aks:
        c, v = split_cv(a)
        if c and v is None:
            choices.append([c, c + "a"])
        elif c and v == "a":
            choices.append([c + "a", c])
        elif v in ("e", "o"):
            long_ = {"e": "ē", "o": "ō"}[v]
            choices.append([a, (c or "") + long_])
        else:
            choices.append([a])
    out = [""]
    for ch in choices:
        out = [o + x for o in out for x in ch][:256]
    from ezhuthu.corpus.script import iso_to_tamil

    seen, res = set(), []
    for o in out:
        t = iso_to_tamil(o)
        if t not in seen:
            seen.add(t)
            res.append(o)
    return res[:64]


# ---------------------------------------------------------------------------------------------------------------
# fill the gap
# ---------------------------------------------------------------------------------------------------------------
def build_gaps(corpus: Corpus) -> list[dict]:
    from ezhuthu.agent.ngram import CharNgram
    from ezhuthu.corpus.script import count_aksharas, normalise_for_scoring

    items_src = [r for r in load_jsonl("items.train.jsonl")
                 if r["split"] == "train" and r["inscription_id"] in corpus.train and r["kind"] == "supplied"
                 and r.get("lang") == "tam-Latn"]
    model = CharNgram(order=5).fit(r["text"] for r in corpus.lines)

    def ctx(left: str, right: str) -> tuple[str, str] | None:
        left = GAP_RE.split(left)[-1]
        right = GAP_RE.split(right)[0]
        left = re.sub(r"\[(?!\?)([^\]]*)\]", r"\1", left).replace("‡", "")
        right = re.sub(r"\[(?!\?)([^\]]*)\]", r"\1", right).replace("‡", "")
        if len(left) > 42:
            left = left[-42:]
            left = left[left.index(" ") + 1:] if " " in left else left
        if len(right) > 32:
            right = right[:32]
            right = right[: right.rindex(" ")] if " " in right else right
        if count_aksharas(left) < 6 or count_aksharas(right) < 4:
            return None
        if re.search(r"[0-9{}<>]", left + right):
            return None
        return left, right

    by_len: dict[int, list[str]] = defaultdict(list)
    for r in items_src:
        t = r["target"].strip()
        if re.fullmatch(r"[a-zāīūēōṅñṭṇḻḷṟṉśṣ\- ]+", t):
            by_len[r["gap_chars"]].append(t)
    for k in by_len:
        by_len[k] = sorted(set(by_len[k]))

    pool = sorted(items_src, key=lambda r: r["id"])
    rng_pool = rng_for("gaps-pool")
    rng_pool.shuffle(pool)
    per_ins: Counter[str] = Counter()
    per_level: Counter[int] = Counter()
    cap = {1: 170, 2: 160, 3: 110}
    out: list[dict] = []
    for r in pool:
        target = r["target"].strip()
        if not re.fullmatch(r"[a-zāīūēōṅñṭṇḻḷṟṉśṣ\- ]+", target) or not 1 <= r["gap_chars"] <= 6:
            continue
        level = 1 if r["gap_chars"] == 1 else 2 if r["gap_chars"] <= 3 else 3
        if per_level[level] >= cap[level] or per_ins[r["inscription_id"]] >= 3:
            continue
        c = ctx(r["left"], r["right"])
        if not c:
            continue
        left, right = c
        norm_t = normalise_for_scoring(target)
        fills = [f for f, _ in model.fill(r["left"], r["right"], r["gap_chars"], k=12)]
        ds: list[str] = []
        seen = {norm_t}
        for f in fills:
            n = normalise_for_scoring(f)
            if n and n not in seen and re.fullmatch(r"[a-zāīūēōṅñṭṇḻḷṟṉśṣ\- ]+", f):
                seen.add(n)
                ds.append(f)
            if len(ds) == 3:
                break
        rng = rng_for("gap", r["id"])
        if len(ds) < 3:
            extra = [t for t in by_len[r["gap_chars"]] if normalise_for_scoring(t) not in seen]
            rng.shuffle(extra)
            for t in extra:
                if len(ds) == 3:
                    break
                seen.add(normalise_for_scoring(t))
                ds.append(t)
        if len(ds) < 3:
            continue
        from_ngram = sum(1 for d in ds if d in fills)
        left = left.lstrip("-·.’' ")
        right = right.rstrip("-·.’' ")
        # Tamil shows each option as the whole word it completes: a vowel sign cannot stand alone in Tamil script.
        head = "" if left.endswith(" ") else left.split(" ")[-1]
        tail = "" if right.startswith(" ") else right.split(" ")[0]

        def o(x: str) -> dict:
            x = x.strip()
            return {"iso": x, "ta": to_tamil(head + x + tail), "word_iso": head + x + tail}

        opts, ans = shuffle_options(rng, o(target), [o(d) for d in ds])
        if len({x["ta"] for x in opts}) < 4:
            continue
        ins = corpus.train[r["inscription_id"]]
        why_en = (f"The DHARMA editors restored {target} ({to_tamil(target)}) here, {r['gap_chars']} letter"
                  f"{'s' if r['gap_chars'] > 1 else ''} lost on the stone. {from_ngram} of the other options are "
                  "fills that a letter-sequence model trained on these inscriptions also finds likely.")
        why_ta = (f"DHARMA பதிப்பாசிரியர்கள் இங்கே {to_tamil(target)} ({target}) என மீட்டனர்; கல்லில் "
                  f"{r['gap_chars']} எழுத்து அழிந்துள்ளது. மற்ற விடைகளில் {from_ngram}, இக்கல்வெட்டுகளில் பயின்ற "
                  "எழுத்துத்தொடர் மாதிரியும் பொருத்தமாகக் கருதும் நிரப்புகள்.")
        out.append({"id": f"gap:{r['id']}", "level": level, "gap_chars": r["gap_chars"],
                    "masked": {"iso": f"{left}[?{r['gap_chars']}]{right}",
                               "ta": to_tamil(f"{left}[?{r['gap_chars']}]{right}")},
                    "restored": {"iso": f"{left}{target}{right}", "ta": to_tamil(f"{left}{target}{right}")},
                    "options": opts, "answer": ans, "why_en": why_en, "why_ta": why_ta,
                    "src": source(ins, r["line_n"]), "hard": bool(r.get("hard"))})
        per_ins[r["inscription_id"]] += 1
        per_level[level] += 1
    out.sort(key=lambda x: (x["level"], x["id"]))
    return out


# ---------------------------------------------------------------------------------------------------------------
# formulas
# ---------------------------------------------------------------------------------------------------------------
# key, regex on one word (hyphens removed, lower case), optional regex on the next word, level, ISO shown,
# meaning (EN, TA), note (EN, TA). Meanings are standard glosses in South Indian epigraphy.
FORMULAS: list[dict] = [
    {"key": "svasti-sri", "re": r"^svasti$", "next": r"^śrī", "level": 1, "iso": "svasti śrī",
     "en": "Hail! Prosperity! (the blessing that opens an inscription)",
     "ta": "மங்கலம் உண்டாகுக! (கல்வெட்டைத் தொடங்கும் வாழ்த்து)",
     "note_en": "Most royal inscriptions open with it, before the king's name.",
     "note_ta": "பெரும்பாலான அரசர் கல்வெட்டுகள் மன்னன் பெயருக்கு முன் இதனுடன் தொடங்குகின்றன."},
    {"key": "yantu", "re": r"^yāṇṭu$", "level": 1, "iso": "yāṇṭu",
     "en": "year (of the king's reign)", "ta": "ஆண்டு (மன்னனின் ஆட்சியாண்டு)",
     "note_en": "Inscriptions are dated by the year of the reign, not by a calendar era.",
     "note_ta": "கல்வெட்டுகள் நாட்காட்டி ஆண்டால் அல்ல, ஆட்சியாண்டால் காலம் குறிக்கின்றன."},
    {"key": "avatu", "re": r"^.+āvatu$", "level": 2, "iso": "…āvatu",
     "en": "the …th (the ending of the regnal-year number: 'the 34th year')",
     "ta": "…ஆவது (ஆட்சியாண்டு எண்ணின் முடிவு: 'முப்பத்து நாலாவது')",
     "note_en": "With yāṇṭu it forms the regnal-year phrase: yāṇṭu muppattu nālāvatu, 'in the 34th year'.",
     "note_ta": "யாண்டு என்பதுடன் சேர்ந்து ஆட்சியாண்டுத் தொடர் ஆகிறது: யாண்டு முப்பத்து நாலாவது."},
    {"key": "parakesari", "re": r"^(kō)?(p)?parakē[cs]ari", "level": 2, "iso": "kō-p-parakēcari-",
     "en": "Parakesari, a title taken by every other Chola king",
     "ta": "பரகேசரி: சோழ மன்னர்கள் மாறி மாறிப் பூண்ட பட்டம்",
     "note_en": "Chola kings alternated the titles Parakesari and Rajakesari from one reign to the next.",
     "note_ta": "சோழ மன்னர்கள் ஓர் ஆட்சியில் பரகேசரி, அடுத்ததில் இராசகேசரி என மாறி மாறிப் பூண்டனர்."},
    {"key": "rajakesari", "re": r"^(kō)?(i)?(r)?rājakē[cs]ari", "level": 2, "iso": "kō-v-irājakēsari-",
     "en": "Rajakesari, the other title alternated by Chola kings",
     "ta": "இராசகேசரி: சோழ மன்னர்கள் மாறி மாறிப் பூண்ட மற்றொரு பட்டம்",
     "note_en": "The partner of Parakesari: a Rajakesari king was followed by a Parakesari.",
     "note_ta": "பரகேசரியின் இணை: இராசகேசரி மன்னனுக்குப் பின் பரகேசரி வருவார்."},
    {"key": "lamp", "re": r"^(tiru)?n[oa]n[dt]āviḷakk", "level": 2, "iso": "nontā-viḷakku",
     "en": "a perpetual lamp, kept burning day and night", "ta": "நந்தா விளக்கு: இரவும் பகலும் அணையாது எரியும் விளக்கு",
     "note_en": "Many gifts pay for one: sheep, cows or gold whose yield buys the ghee.",
     "note_ta": "பல கொடைகள் இதற்கே: நெய் வாங்க ஆடு, பசு அல்லது பொன் வைக்கப்பட்டது."},
    {"key": "moon-sun", "re": r"^can[dt]irā[dt]i[tc]ta", "level": 2, "iso": "cantirātitta-",
     "en": "as long as the moon and the sun endure: for ever", "ta": "சந்திராதித்தர் உள்ளவரை: என்றென்றும்",
     "note_en": "The usual promise that a gift will last for all time.",
     "note_ta": "கொடை என்றும் நிலைக்கும் என்ற வழக்கமான உறுதிமொழி."},
    {"key": "undying-sheep", "re": r"^cāvā", "next": r"^mūvā", "level": 3, "iso": "cāvā mūvā",
     "en": "'undying, unageing' (sheep or cattle given so that the herd never shrinks)",
     "ta": "சாவா மூவா: சாகாத, மூப்படையாத (எண்ணிக்கை குறையாத ஆடுமாடுகள்)",
     "note_en": "The herd is replaced as animals die, so the lamp's ghee never stops.",
     "note_ta": "ஆடுகள் இறந்தாலும் புதியவை சேர்க்கப்படும்; விளக்கின் நெய் நிற்காது."},
    {"key": "gave", "re": r"^k[uo]ṭutt", "level": 1, "iso": "kuṭutta",
     "en": "gave, given (the verb of a donation)", "ta": "கொடுத்த: கொடை வினை",
     "note_en": "Donation records turn on this verb: who gave what to whom.",
     "note_ta": "கொடைப் பதிவுகளின் மையம்: யார் யாருக்கு என்ன கொடுத்தார்."},
    {"key": "placed", "re": r"^vaitta", "level": 1, "iso": "vaitta",
     "en": "placed, set up (an endowment)", "ta": "வைத்த: (அறக்கொடையை) நிறுவிய",
     "note_en": "Used for lamps, gold or land set aside for a temple.",
     "note_ta": "கோயிலுக்காக வைத்த விளக்கு, பொன், நிலம் ஆகியவற்றுக்கு வருகிறது."},
    {"key": "kalanju", "re": r"^kaḻañcu", "level": 2, "iso": "kaḻañcu",
     "en": "kaḻañcu, a unit of weight for gold", "ta": "கழஞ்சு: பொன் நிறுக்கும் அளவை",
     "note_en": "Gold gifts are counted in kaḻañcu.", "note_ta": "பொன் கொடைகள் கழஞ்சில் கணக்கிடப்படுகின்றன."},
    {"key": "gold", "re": r"^poṉ$", "level": 1, "iso": "poṉ", "en": "gold", "ta": "பொன்",
     "note_en": "Often lent to a village, whose interest pays for a temple service.",
     "note_ta": "பெரும்பாலும் ஊருக்குக் கடனாகக் கொடுக்கப்பட்டு, அதன் வட்டி கோயில் பணிக்குச் செல்லும்."},
    {"key": "paddy", "re": r"^nel$", "level": 1, "iso": "nel", "en": "paddy (rice in the husk)", "ta": "நெல்",
     "note_en": "Measured in kalam, kuṟuṇi and nāḻi.", "note_ta": "கலம், குறுணி, நாழி என அளக்கப்படும்."},
    {"key": "land", "re": r"^nilam$", "level": 1, "iso": "nilam", "en": "land", "ta": "நிலம்",
     "note_en": "Land grants name the plot and its four boundaries.",
     "note_ta": "நிலக்கொடைகள் நிலத்தையும் அதன் நான்கு எல்லைகளையும் குறிப்பிடும்."},
    {"key": "assembly", "re": r"^sabhai", "level": 2, "iso": "sabhai",
     "en": "the assembly of a Brahmin village", "ta": "சபை: பிராமணர் ஊரின் மன்றம்",
     "note_en": "The sabhai often receives gold and promises a service in return.",
     "note_ta": "சபை பெரும்பாலும் பொன் பெற்று அதற்கு ஈடாகப் பணி செய்ய உறுதியளிக்கும்."},
    {"key": "brahmadeya", "re": r"^brahmat[eē]y", "level": 3, "iso": "brahmatēyam",
     "en": "a village granted to Brahmins (brahmadeya)", "ta": "பிரமதேயம்: பிராமணர்களுக்குக் கொடுத்த ஊர்",
     "note_en": "Such villages were run by a sabhai.", "note_ta": "இத்தகைய ஊர்களை சபை நிர்வகித்தது."},
    {"key": "devadana", "re": r"^[dt][eē]va[dt]āṉ", "level": 3, "iso": "tēvatāṉam",
     "en": "land given to a temple's god (devadana)", "ta": "தேவதானம்: கோயில் இறைவனுக்குக் கொடுத்த நிலம்",
     "note_en": "Its income belongs to the temple.", "note_ta": "அதன் வருவாய் கோயிலுக்கு உரியது."},
    {"key": "mahesvara", "re": r"^paṉ?māh[eē]śvara", "level": 3, "iso": "paṉ-māhēśvara-rakṣai",
     "en": "under the protection of all the devotees of Śiva (a closing formula)",
     "ta": "பன்மாகேசுவரர் காப்பு: எல்லாச் சிவனடியார்களின் பாதுகாப்பில் (முடிவு வாசகம்)",
     "note_en": "It puts the gift in the care of the whole Śaiva community.",
     "note_ta": "கொடையை முழுச் சைவ சமூகத்தின் பொறுப்பில் வைக்கிறது."},
    {"key": "great-god", "re": r"^mahā[dt][eē]var", "level": 2, "iso": "mahā-tēvar",
     "en": "the Great God (Śiva, the god of the temple)", "ta": "மகாதேவர்: கோயிலின் இறைவனான சிவன்",
     "note_en": "Gifts are made to the god himself, named by his temple.",
     "note_ta": "கொடைகள் கோயிலின் பெயரால் அழைக்கப்படும் இறைவனுக்கே செய்யப்படுகின்றன."},
    {"key": "sacred", "re": r"^tiru.{2,}", "level": 1, "iso": "tiru-",
     "en": "sacred, holy (a prefix of honour)", "ta": "திரு: புனிதம், மேன்மை (மரியாதை முன்னொட்டு)",
     "note_en": "As in tiru-k-kōyil, 'the sacred temple'.", "note_ta": "திருக்கோயில் என்பதில் உள்ளது போல."},
]


def build_formulas(corpus: Corpus) -> tuple[list[dict], list[dict]]:
    texts = corpus.tamil_texts()
    occ: dict[str, list[tuple[str, list[str], int, int]]] = defaultdict(list)
    for iid, text in texts.items():
        toks = text.split()
        used: set[str] = set()
        for i, tok in enumerate(toks):
            norm = nfc(tok.replace("-", "").replace("=", "").lower())
            for f in FORMULAS:
                if f["key"] in used or not re.search(f["re"], norm):
                    continue
                end = i + 1
                if "next" in f:
                    if i + 1 >= len(toks) or not re.search(f["next"], nfc(toks[i + 1].replace("-", "").lower())):
                        continue
                    end = i + 2
                window = toks[max(0, i - 4): end + 4]
                if any(GAP_RE.search(w) or re.search(r"[0-9{}]", w) for w in window):
                    continue
                if any(clean_token(w) is None for w in toks[i:end]):
                    continue
                occ[f["key"]].append((iid, toks, i, end))
                used.add(f["key"])
                break
    by_key = {f["key"]: f for f in FORMULAS}
    items: list[dict] = []
    for f in FORMULAS:
        rows = occ[f["key"]]
        rng0 = rng_for("formula-pool", f["key"])
        rows = sorted(rows, key=lambda r: r[0])
        rng0.shuffle(rows)
        for iid, toks, i, end in rows[:18]:
            item_id = f"formula:{f['key']}:{iid}"
            rng = rng_for(item_id)
            before, match, after = toks[max(0, i - 4): i], toks[i:end], toks[end: end + 4]
            line = {
                "before": {"iso": " ".join(before), "ta": to_tamil(" ".join(before))},
                "match": {"iso": " ".join(match), "ta": to_tamil(" ".join(match))},
                "after": {"iso": " ".join(after), "ta": to_tamil(" ".join(after))},
            }
            mode = "meaning" if rng.random() < 0.5 else "spot"
            if mode == "spot":
                others = [w for w in before + after
                          if clean_token(w) and is_whole_word(clean_token(w) or "") and len(akshara_list(w)) >= 2]
                others = sorted(set(others) - set(match))
                if len(others) < 3:
                    mode = "meaning"
            if mode == "meaning":
                pool = [x for x in FORMULAS if x["key"] != f["key"]]
                rng.shuffle(pool)
                opt = lambda x: {"en": x["en"], "ta": x["ta"], "key": x["key"]}  # noqa: E731
                opts, ans = shuffle_options(rng, opt(f), [opt(x) for x in pool[:3]])
            else:
                rng.shuffle(others)
                o = lambda x: {"ta": to_tamil(x), "iso": x}  # noqa: E731
                opts, ans = shuffle_options(rng, o(" ".join(match)), [o(x) for x in others[:3]])
            items.append({"id": item_id, "level": f["level"], "mode": mode, "formula": f["key"], "line": line,
                          "gloss": {"en": f["en"], "ta": f["ta"]},
                          "options": opts, "answer": ans,
                          "why_en": f"{line['match']['iso']} ({line['match']['ta']}) means: {f['en']}. {f['note_en']}",
                          "why_ta": f"{line['match']['ta']} ({line['match']['iso']}): {f['ta']}. {f['note_ta']}",
                          "src": source(corpus.train[iid])})
    glossary = [{"key": f["key"], "iso": f["iso"], "ta": to_tamil(f["iso"].replace("…", "")),
                 "en": f["en"], "ta_meaning": f["ta"], "level": f["level"], "found": len(occ[f["key"]])}
                for f in FORMULAS if occ[f["key"]]]
    del by_key
    return items, glossary


# ---------------------------------------------------------------------------------------------------------------
# worked example (How it works)
# ---------------------------------------------------------------------------------------------------------------
def build_worked_example(corpus: Corpus) -> dict:
    samples = json.loads((SAMPLES / "samples.json").read_text(encoding="utf-8"))
    recorded = json.loads((SAMPLES / "recorded-restores.json").read_text(encoding="utf-8"))
    calib = json.loads((REPO / "src" / "ezhuthu" / "agent" / "calibration.json").read_text(encoding="utf-8"))
    s = next(x for x in samples if x["id"] == "mamallapuram-calf-pasture")
    assert s["split"] == "train" and s["inscription_id"] in corpus.train
    rec = recorded["samples"][s["id"]]
    gap = rec["response"]["gaps"][0]
    text = rec["text_iso"]
    m = GAP_RE.search(text)
    assert m
    # A short window around the gap: four words either side.
    left_words = text[: m.start()].split()[-4:]
    right_words = text[m.end():].split()[:4]
    left = " ".join(left_words) + (" " if text[m.start() - 1] == " " else "")
    right = (" " if text[m.end()] == " " else "") + " ".join(right_words)
    top = gap["candidates"][0]
    key = f"{top['confidence_source']}|{top['decider_source']}|kall|llm-{top['model']}"
    threshold = calib["variants"].get(key, {}).get("threshold")
    cands = [{"iso": c["text"], "ta": c["text_tamil"], "confidence": c["confidence"], "model": c["model"],
              "sources": c["sources"]} for c in gap["candidates"][:3]]
    return {
        "sample_id": s["id"], "inscription_id": s["inscription_id"], "split": s["split"],
        "title_en": s["title_en"], "title_ta": s["title_ta"], "place_en": s["place_en"], "place_ta": s["place_ta"],
        "why_en": s["why_en"], "why_ta": s["why_ta"], "url": s["dharma_url"], "licence": s["licence"],
        "recorded_on": recorded["meta"]["date"],
        "left": {"iso": left, "ta": to_tamil(left)}, "right": {"iso": right, "ta": to_tamil(right)},
        "gap_chars": gap["gap_chars"], "decision": gap["decision"], "candidates": cands,
        "threshold": threshold, "calibration_key": key if threshold is not None else None,
        "word": {"iso": "makaṉ", "ta": to_tamil("makaṉ"), "en": "son", "ta_meaning": "மகன்"},
    }


# ---------------------------------------------------------------------------------------------------------------
def build() -> dict[str, object]:
    corpus = Corpus()
    letters = build_letters(corpus)
    words = build_words(corpus)
    gaps = build_gaps(corpus)
    formulas, glossary = build_formulas(corpus)
    meta = {
        "built_by": "scripts/build_practice.py", "seed": SEED, "split": "train",
        "credit": "Inscription texts: DHARMA project editions, CC BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/)",
        "ta_review": TA_REVIEW,
    }
    try_items = {
        "letters": [i for i in letters if i["era"] == "brahmi" and i["level"] == 1][:8],
        "words": [i for i in words if i["level"] == 1 and i["dir"] == "iso2ta"][:4],
    }
    return {
        "letters.json": {"meta": {**meta, "licences": {
            "brahmi": "Unicode Brahmi, drawn with Noto Sans Brahmi (SIL Open Font License 1.1)",
            "grantha": "Unicode Grantha, drawn with Noto Sans Grantha (SIL Open Font License 1.1); the closest "
                       "Unicode relative of Pallava letterforms",
            "vatteluttu": "Ezhuthu design system drawings (design/glyphs/vatteluttu.json), simplified teaching "
                          "forms pending epigrapher review",
            "frequency": "letters drilled are those seen at least 100 times in TRAIN inscription text"}},
            "items": letters},
        "words.json": {"meta": meta, "items": words},
        "gaps.json": {"meta": meta, "items": gaps},
        "formulas.json": {"meta": meta, "glossary": glossary, "items": formulas},
        "try.json": {"meta": meta, **try_items},
        "summary.json": {"meta": meta, "counts": {
            name: {str(lv): sum(1 for i in items if i["level"] == lv) for lv in (1, 2, 3)}
            for name, items in (("letters", letters), ("words", words), ("gaps", gaps), ("formulas", formulas))}},
        "worked-example.json": {"meta": meta, **build_worked_example(corpus)},
    }


def dump(obj: object) -> str:
    """One item per line: compact, but still readable in a diff."""
    if isinstance(obj, dict):
        lines = []
        for k, v in obj.items():
            if isinstance(v, list) and v and isinstance(v[0], dict):
                inner = ",\n  ".join(json.dumps(x, ensure_ascii=False) for x in v)
                lines.append(f"{json.dumps(k)}: [\n  {inner}\n ]")
            else:
                lines.append(f"{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}")
        return "{\n " + ",\n ".join(lines) + "\n}\n"
    return json.dumps(obj, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="fail if the committed files differ from a fresh build")
    args = ap.parse_args(argv)
    files = build()
    bad = []
    for name, obj in files.items():
        path = OUT / name
        text = dump(obj)
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                bad.append(name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for name in ("letters.json", "words.json", "gaps.json", "formulas.json"):
        items = files[name]["items"]  # type: ignore[index]
        by = Counter(i["level"] for i in items)
        print(f"{name}: {len(items)} items, by level {dict(sorted(by.items()))}")
    if bad:
        print("out of date:", ", ".join(bad), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
