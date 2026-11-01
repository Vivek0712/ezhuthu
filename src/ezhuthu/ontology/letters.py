"""Valid base letters (graphemes) per script stage, rendered with Aksharamukha.

A *letter* here is a base akshara the tutor asks a learner to read: an independent vowel, or a
consonant with the inherent/first vowel (``ka``). Inventories are written out explicitly below;
Aksharamukha renders each one into the Unicode script for that stage. Documented exceptions
(``EXCEPTIONS``) say where a stage departs from the modern Tamil inventory, with a source.
Corpus counts (how often each letter occurs in DHARMA editions of that stage) are added by the
build, so the tutor can prefer frequent letters.
"""

from __future__ import annotations

import functools
import re
import warnings

TAMIL_VOWELS = ["a", "ā", "i", "ī", "u", "ū", "e", "ē", "ai", "o", "ō", "au"]
TAMIL_CONSONANTS = ["k", "ṅ", "c", "ñ", "ṭ", "ṇ", "t", "n", "p", "m", "y", "r", "l", "v", "ḻ", "ḷ", "ṟ", "ṉ"]
GRANTHA_IN_TAMIL = ["j", "ś", "ṣ", "s", "h", "kṣ"]
SANSKRIT_VOWELS = ["a", "ā", "i", "ī", "u", "ū", "r̥", "r̥̄", "l̥", "e", "ai", "o", "au"]
SANSKRIT_CONSONANTS = [
    "k", "kh", "g", "gh", "ṅ", "c", "ch", "j", "jh", "ñ", "ṭ", "ṭh", "ḍ", "ḍh", "ṇ",
    "t", "th", "d", "dh", "n", "p", "ph", "b", "bh", "m", "y", "r", "l", "v", "ś", "ṣ", "s", "h", "ḷ",
]  # fmt: skip

# Stage id -> (label, Aksharamukha target script or None, era, default inventory note)
STAGES: dict[str, dict] = {
    "tamil-brahmi-1": {
        "label_ta": "தமிழ்-பிராமி I",
        "label_iso": "Tamil-Brāhmī I",
        "script": "TamilBrahmi",
        "era": "c. 2nd c. BCE onward (orthographic system, not a strict period)",
        "order": 1,
    },
    "tamil-brahmi-2": {
        "label_ta": "தமிழ்-பிராமி II","label_iso": "Tamil-Brāhmī II", "script": "TamilBrahmi", "era": None, "order": 2},
    "tamil-brahmi-3": {
        "label_ta": "தமிழ்-பிராமி III","label_iso": "Tamil-Brāhmī III", "script": "TamilBrahmi", "era": None, "order": 3},
    "vatteluttu": {
        "label_ta": "வட்டெழுத்து","label_iso": "Vaṭṭeḻuttu", "script": None, "era": "c. 6th–11th c. CE in the Tamil country", "order": 4},
    "grantha": {
        "label_ta": "கிரந்தம்","label_iso": "Grantha", "script": "Grantha", "era": "c. 6th c. CE onward", "order": 5},
    "pallava-tamil": {
        "label_ta": "பல்லவர் காலத் தமிழ்","label_iso": "Pallava Tamil", "script": "Tamil", "era": "c. 6th–9th c. CE", "order": 6},
    "chola-tamil": {
        "label_ta": "சோழர் காலத் தமிழ்","label_iso": "Chola Tamil", "script": "Tamil", "era": "c. 9th–13th c. CE", "order": 7},
    "later-tamil": {
        "label_ta": "பிற்காலத் தமிழ்","label_iso": "Later Tamil", "script": "Tamil", "era": "c. 14th c. CE onward", "order": 8},
}
# Tutor levels from contracts/restore-api.md mapped to stages.
LEVEL_STAGES = {
    "L1": ["later-tamil"],
    "L2": ["chola-tamil"],
    "L3": ["pallava-tamil", "grantha"],
    "L4": ["vatteluttu"],
    "L5": ["tamil-brahmi-1", "tamil-brahmi-2", "tamil-brahmi-3"],
}

MAHADEVAN = "I. Mahadevan, Early Tamil Epigraphy (2003; rev. 2014)"
EXCEPTIONS: dict[str, list[dict]] = {
    "_tamil_script_pre_modern": [
        {
            "rule": "no-e-o-length-contrast",
            "text": "Short and long e (e/ē) and o (o/ō) are written with the same sign; the distinction was "
            "introduced in the 18th century (attributed to C. J. Beschi). Editors supply the length in ISO "
            "transliteration, so the tutor accepts either value for these signs.",
            "source": "standard history of Tamil script; DHARMA editions normalise length in transliteration",
        },
        {
            "rule": "pulli-often-unwritten",
            "text": "The pulli (dot marking a vowel-less consonant) is usually not written in medieval stone "
            "inscriptions; a consonant sign may stand for C or Ca and must be read from context.",
            "source": "general palaeographic observation; DHARMA editions transliterate the intended reading",
        },
    ],
    "tamil-brahmi": [
        {
            "rule": "no-e-o-length-contrast",
            "text": "No e/ē or o/ō contrast.",
            "source": MAHADEVAN,
        },
        {
            "rule": "special-letters",
            "text": "Tamil-Brāhmī adds letters for the Tamil sounds ḻ, ḷ, ṟ and ṉ that Aśokan Brāhmī lacks "
            "(Unicode: BRAHMI LETTER OLD TAMIL LLLA/RRA/NNNA, U+11035–U+11037, and LLA U+11034).",
            "source": MAHADEVAN + "; Unicode Standard, Brahmi block",
        },
        {
            "rule": "no-aspirates-or-sibilants",
            "text": "Tamil-Brāhmī writes Tamil and has no letters for Sanskrit aspirates or sibilants in this "
            "inventory; Prakrit loan words in the corpus may use a few Brāhmī letters (e.g. dha, sa) and "
            "are not part of the core set.",
            "source": MAHADEVAN,
        },
    ],
    "tamil-brahmi-1": [
        {
            "rule": "TB-I-no-inherent-vowel",
            "text": "Tamil-Brāhmī I: a bare consonant sign is the consonant without vowel; Ca is written with the "
            "same stroke as Cā (a/ā ambiguity).",
            "source": MAHADEVAN,
        }
    ],
    "tamil-brahmi-2": [
        {
            "rule": "TB-II-inherent-vowel",
            "text": "Tamil-Brāhmī II: the bare consonant sign carries inherent a (as in Aśokan Brāhmī), so a "
            "vowel-less consonant is not distinguished from Ca.",
            "source": MAHADEVAN,
        }
    ],
    "tamil-brahmi-3": [
        {
            "rule": "TB-III-pulli",
            "text": "Tamil-Brāhmī III: the pulli (dot) marks the vowel-less consonant; the bare sign is Ca.",
            "source": MAHADEVAN,
        }
    ],
    "vatteluttu": [
        {
            "rule": "no-unicode",
            "text": "Vaṭṭeḻuttu has no Unicode encoding; Aksharamukha maps it to Tamil code points. The app ships "
            "SVG glyphs and shows the ISO-15919 value (contracts/restore-api.md).",
            "source": "Aksharamukha ScriptMap/MainIndic/Vatteluttu.py; Unicode pipeline (not encoded)",
        },
        {
            "rule": "no-grantha-letters",
            "text": "Sanskrit sounds (j, ś, ṣ, s, h) are not part of Vaṭṭeḻuttu; Sanskrit words are written in "
            "Grantha alongside it.",
            "source": "DHARMA editions mark such passages with <hi rend='grantha'>",
        },
    ],
    "grantha": [
        {
            "rule": "sanskrit-inventory",
            "text": "Grantha writes Sanskrit: full Sanskrit inventory (aspirates, sibilants, r̥, l̥). e and o are "
            "long in Sanskrit; there is no short/long contrast to teach.",
            "source": "Unicode Standard, Grantha block; Aksharamukha Grantha map",
        }
    ],
    "pallava-tamil": [
        {
            "rule": "grantha-letters-in-tamil",
            "text": "Tamil-script inscriptions of this period write Sanskrit words with Grantha letters "
            "(j, ś, ṣ, s, h, kṣ); they are included and flagged grantha=true.",
            "source": "DHARMA <hi rend='grantha'> markup (10,247 spans in the six collections)",
        }
    ],
    "chola-tamil": [
        {
            "rule": "grantha-letters-in-tamil",
            "text": "Grantha letters (j, ś, ṣ, s, h, kṣ) appear inside Tamil text for Sanskrit words; included "
            "and flagged grantha=true.",
            "source": "DHARMA <hi rend='grantha'> markup",
        }
    ],
    "later-tamil": [],
}


def _inventory(stage: str) -> list[dict]:
    if stage.startswith("tamil-brahmi"):
        vowels = ["a", "ā", "i", "ī", "u", "ū", "e", "ai", "o"]
        return [{"iso": v, "type": "vowel"} for v in vowels] + [
            {"iso": c + "a", "type": "consonant"} for c in TAMIL_CONSONANTS
        ]
    if stage == "grantha":
        return [{"iso": v, "type": "vowel"} for v in SANSKRIT_VOWELS] + [
            {"iso": c + "a", "type": "consonant"} for c in SANSKRIT_CONSONANTS
        ]
    vowels = [v for v in TAMIL_VOWELS if v not in ("ē", "ō")]  # merged with e/o before the 18th c.
    letters = [{"iso": v, "type": "vowel"} for v in vowels]
    letters += [{"iso": c + "a", "type": "consonant"} for c in TAMIL_CONSONANTS]
    if stage != "vatteluttu":
        letters += [{"iso": c + "a", "type": "consonant", "grantha": True} for c in GRANTHA_IN_TAMIL]
    letters.append({"iso": "ḵ", "type": "aytam"})
    return letters


@functools.lru_cache(maxsize=4096)
def render(iso: str, script: str | None) -> str | None:
    if not script:
        return None
    from aksharamukha import transliterate

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = transliterate.process("ISO", script, iso)
    return out if out and out != iso else None


def _merged_values(iso: str, stage: str) -> list[str]:
    if stage == "grantha":
        return [iso]
    if iso == "e":
        return ["e", "ē"]
    if iso == "o":
        return ["o", "ō"]
    return [iso]


def letters_for(stage: str) -> list[dict]:
    meta = STAGES[stage]
    out = []
    for item in _inventory(stage):
        iso = item["iso"]
        values = _merged_values(iso, stage)
        # Merged e/o: Tamil script shows the older single sign (today's short எ/ஒ; the long forms
        # are Beschi's later marking). Brāhmī shows the plain sign (Aksharamukha marks short e/o
        # with a virama-like diacritic, a modern convention). Grantha e/o are Sanskrit long vowels.
        if stage == "grantha" or stage.startswith("tamil-brahmi"):
            glyph_src = {"e": "ē", "o": "ō"}.get(iso, iso)
        else:
            glyph_src = values[0]
        out.append(
            {
                **item,
                "iso_values": values,
                "glyph": render(glyph_src, meta["script"]),
                "script": meta["script"],
            }
        )
    return out


def exceptions_for(stage: str) -> list[dict]:
    ex = list(EXCEPTIONS.get(stage, []))
    if stage.startswith("tamil-brahmi"):
        ex = EXCEPTIONS["tamil-brahmi"] + ex
    elif stage in ("vatteluttu", "pallava-tamil", "chola-tamil", "later-tamil"):
        ex = EXCEPTIONS["_tamil_script_pre_modern"] + ex
    return ex


# --- akshara segmentation, used for corpus letter counts --------------------------------------
_CONS = set(SANSKRIT_CONSONANTS + TAMIL_CONSONANTS + ["kṣ"])
_VOW = set(SANSKRIT_VOWELS + TAMIL_VOWELS + ["r̥̄"])
_UNIT = re.compile("|".join(re.escape(x) for x in sorted(_CONS | _VOW | {"ḵ"}, key=len, reverse=True)))


def base_letters(text: str) -> list[str]:
    """Split ISO-15919 text into base letters: ``kōṭṭam`` -> ``['ka', 'ṭa', 'ṭa', 'ma']``.

    A consonant counts as its ``Ca`` letter whatever vowel follows; an independent vowel counts
    when it starts a word or follows another vowel.
    """
    import unicodedata

    out: list[str] = []
    for word in re.split(r"[^\ẁ-ͯ]+", unicodedata.normalize("NFC", text).lower()):
        prev_vowel = True
        for m in _UNIT.finditer(word):
            u = m.group()
            if u in _CONS:
                out.append(u + "a")
                prev_vowel = False
            elif u == "ḵ":
                out.append(u)
                prev_vowel = False
            else:
                if prev_vowel:
                    out.append(u)
                prev_vowel = True
    return out


_LETTER_ASCII = [
    ("r̥̄", "rii"), ("r̥", "ri"), ("l̥", "li"), ("ā", "aa"), ("ī", "ii"), ("ū", "uu"), ("ē", "ee"), ("ō", "oo"),
    ("ṅ", "ng"), ("ñ", "ny"), ("ṭ", "tt"), ("ḍ", "dd"), ("ṇ", "nn"), ("ḻ", "zh"), ("ḷ", "ll"), ("ṟ", "rr"),
    ("ṉ", "nnn"), ("ś", "sh"), ("ṣ", "ss"), ("ḵ", "aytam"), ("ṁ", "m"), ("ḥ", "h"),
]


def letter_slug(iso: str) -> str:
    """Distinct ASCII slug for a letter: ``ṉa`` -> ``nnna``, ``ā`` -> ``aa``."""
    import unicodedata

    s = unicodedata.normalize("NFC", iso)
    for a, b in _LETTER_ASCII:
        s = s.replace(unicodedata.normalize("NFC", a), b)
    return s


def letter_count(text: str) -> int:
    """Number of Tamil letters (uyir, mey, uyirmey) in ISO-15919 ``text``.

    Same unit as the benchmark's ``gap_chars`` and DHARMA's ``<gap unit="character">``: every
    vowel is one letter, and so is every consonant not followed by a vowel.
    """
    import unicodedata

    units = _UNIT.findall(unicodedata.normalize("NFC", re.sub(r"\[\?\d*\]", " ", text)).lower())
    count = 0
    for i, u in enumerate(units):
        if u in _VOW:
            count += 1
        elif u in _CONS or u == "ḵ":
            nxt = units[i + 1] if i + 1 < len(units) else None
            if nxt is None or nxt not in _VOW:
                count += 1
    return count
