"""Feedback and explanations in Tamil (default) and English. Template-based so they work offline."""

from __future__ import annotations

import unicodedata
from typing import Any

from ..text import LEVEL_NAMES, aksharas, iso_to_tamil

DYNASTY_TA = {"chola": "சோழர்", "cola": "சோழர்", "pallava": "பல்லவர்", "pandya": "பாண்டியர்",
              "pantiya": "பாண்டியர்", "chera": "சேரர்", "cera": "சேரர்", "katava": "காடவர்",
              "vijayanagara": "விஜயநகர", "nayaka": "நாயக்கர்"}


def _ascii_key(s: str) -> str:
    """'Cōḻa' -> 'cola': DHARMA dynasty names carry ISO diacritics."""
    return "".join(ch for ch in unicodedata.normalize("NFD", s.lower()) if not unicodedata.combining(ch))

VOWELS = ("a", "ā", "i", "ī", "u", "ū", "e", "ē", "ai", "o", "ō", "au")


def _letter_class(iso: str) -> tuple[str, str]:
    if iso in VOWELS:
        return "உயிர் எழுத்து", "a vowel"
    if not any(iso.endswith(v) for v in VOWELS):
        return "மெய் எழுத்து", "a pure consonant"
    return "உயிர்மெய் எழுத்து", "a consonant with a vowel"


# Tamil grammar groups consonants as vallinam (hard), mellinam (soft) and idaiyinam (medium); Grantha letters
# were borrowed for Sanskrit. Naming the group narrows the answer without giving it away.
CONSONANT_CLASS = {
    **{c: ("வல்லினம் (வலிய ஒலி)", "a hard consonant (vallinam)") for c in ("k", "c", "ṭ", "t", "p", "ṟ")},
    **{c: ("மெல்லினம் (மூக்கொலி)", "a soft, nasal consonant (mellinam)") for c in ("ṅ", "ñ", "ṇ", "n", "m", "ṉ")},
    **{c: ("இடையினம்", "a medium consonant (idaiyinam)") for c in ("y", "r", "l", "v", "ḻ", "ḷ")},
    **{c: ("கிரந்த எழுத்து", "a Grantha letter borrowed for Sanskrit sounds")
       for c in ("j", "ś", "ṣ", "s", "h", "kṣ")},
}
VOWEL_SIGN_TA = {"a": "அ", "ā": "ஆ", "i": "இ", "ī": "ஈ", "u": "உ", "ū": "ஊ", "e": "எ", "ē": "ஏ", "ai": "ஐ",
                 "o": "ஒ", "ō": "ஓ", "au": "ஔ"}


def _split_akshara(a: str) -> tuple[str, str | None]:
    """(consonant, vowel or None) of one ISO akshara."""
    for v in sorted(VOWELS, key=len, reverse=True):
        if a.endswith(v) and len(a) > len(v):
            return a[: -len(v)], v
    return a, None


def hint_for(item_type: str, answer_iso: str) -> tuple[str, str]:
    """A hint that narrows the answer without giving it away.

    Letters: the letter class, the consonant group (never the consonant itself, since "k" alone is accepted
    for "ka") and, when the vowel is not the inherent a, the vowel it carries. Words and lines: the length
    and the class of the first letter.
    """
    if item_type == "letter":
        cls_ta, cls_en = _letter_class(answer_iso)
        if answer_iso in VOWELS:
            length = ("நெடில் (நீண்ட ஒலி)", "a long vowel") if answer_iso in ("ā", "ī", "ū", "ē", "ō", "ai", "au") \
                else ("குறில் (குறுகிய ஒலி)", "a short vowel")
            return (f"குறிப்பு: இது ஒரு {cls_ta}; {length[0]}.", f"Hint: this is {cls_en}, {length[1]}.")
        cons, vowel = _split_akshara(aksharas(answer_iso)[0] if aksharas(answer_iso) else answer_iso)
        grp_ta, grp_en = CONSONANT_CLASS.get(cons, ("மெய் எழுத்து", "a consonant"))
        ta, en = f"குறிப்பு: இது ஒரு {cls_ta}; அதன் மெய் {grp_ta}.", f"Hint: this is {cls_en}; its consonant is {grp_en}."
        if vowel and vowel != "a":
            ta += f" அதில் «{VOWEL_SIGN_TA[vowel]}» உயிர் சேர்ந்துள்ளது."
            en += f" It carries the vowel «{vowel}»."
        return ta, en
    parts = aksharas(answer_iso.replace(" ", ""))
    first = parts[0] if parts else answer_iso[:1]
    f_ta, f_en = _letter_class(first)
    return (f"குறிப்பு: இதில் {len(parts)} எழுத்துகள் உள்ளன; முதல் எழுத்து ஒரு {f_ta}.",
            f"Hint: it has {len(parts)} letters; the first is {f_en}.")


def feedback(correct: bool, action: str, item_type: str, answer_iso: str) -> dict[str, str]:
    ta_ans = iso_to_tamil(answer_iso)
    if correct:
        return {"feedback_ta": f"நன்றாகப் படித்தீர்கள்! இது «{ta_ans}» ({answer_iso}).",
                "feedback_en": f"Well read! This is «{ta_ans}» ({answer_iso})."}
    if action == "hint":
        h_ta, h_en = hint_for(item_type, answer_iso)
        return {"feedback_ta": "இன்னும் கொஞ்சம்! மீண்டும் முயலுங்கள்.", "feedback_en": "Almost! Try again.",
                "hint_ta": h_ta, "hint_en": h_en}
    if action == "repeat":
        return {"feedback_ta": f"இது «{ta_ans}» ({answer_iso}). இதைப் பின்னர் மீண்டும் பயிற்சி செய்வோம்.",
                "feedback_en": f"This is «{ta_ans}» ({answer_iso}). We will practise it again later."}
    return {"feedback_ta": f"பரவாயில்லை! இது «{ta_ans}» ({answer_iso}). அடுத்ததுக்குச் செல்வோம்.",
            "feedback_en": f"No problem! This is «{ta_ans}» ({answer_iso}). Let's move on."}


def explain_template(facts: dict[str, Any]) -> dict[str, str]:
    """Explanation built only from facts (metadata + ontology entities). Nothing is inferred."""
    dyn = (facts.get("dynasty") or "").strip()
    dyn_ta = DYNASTY_TA.get(_ascii_key(dyn), dyn)
    date = facts.get("approx_date")
    level = facts.get("level", "L1")
    lvl_en, lvl_ta = LEVEL_NAMES[level]
    ta, en = [], []
    if dyn:
        ta.append(f"இது {dyn_ta} காலக் கல்வெட்டு" + (f" ({date})." if date else "."))
        en.append(f"This is a {dyn} inscription" + (f" ({date})." if date else "."))
    ruler, year = (facts.get("ruler") or "").strip(), facts.get("regnal_year")
    if ruler:
        ta.append(f"இது {iso_to_tamil(ruler.lower())} ஆட்சிக் காலத்தைச் சேர்ந்தது"
                  + (f" (ஆட்சியாண்டு {year})." if year else "."))
        en.append(f"It dates from the reign of {ruler}" + (f" (regnal year {year})." if year else "."))
    for e in facts.get("entities", []):
        if ruler and e["kind"] in ("ruler", "title") and _ascii_key(e["label"]) == _ascii_key(ruler):
            continue
        label_ta = e.get("label_ta") or iso_to_tamil(e["label"])
        kind = e["kind"]
        if kind in ("ruler", "title"):
            ta.append(f"இதில் «{label_ta}» என்ற அரசப் பெயர் வருகிறது.")
            en.append(f"It names the royal title or ruler «{e['label']}».")
        elif kind in ("grant", "grant_type"):
            ta.append(f"இது «{label_ta}» என்ற கொடையைப் பதிவு செய்கிறது.")
            en.append(f"It records a «{e['label']}» endowment.")
        elif kind in ("place", "temple"):
            ta.append(f"«{label_ta}» என்ற இடம் குறிப்பிடப்படுகிறது.")
            en.append(f"It mentions the place «{e['label']}».")
    ta.append(f"இன்று இதை {lvl_ta} எழுத்தில் படிக்கப் பழகுவோம்.")
    en.append(f"Today we practise reading it in {lvl_en} script.")
    if facts.get("abstained_gaps"):
        ta.append("சில இடங்களில் கல் சிதைந்துள்ளது; அங்கே என்ன இருந்தது என்பதில் நிபுணர்களுக்கும் உறுதியில்லை.")
        en.append("Parts of the stone are damaged; there, experts are unsure what was written.")
    elif facts.get("restored_gaps"):
        ta.append("சிதைந்த இடங்களில் நிரப்பிய எழுத்துகள் Ezhuthu-வின் முன்மொழிவுகள்; அவை உறுதியானவை அல்ல.")
        en.append("Letters filled into damaged places are Ezhuthu's proposals, not certainties.")
    return {"explain_ta": " ".join(ta), "explain_en": " ".join(en)}
