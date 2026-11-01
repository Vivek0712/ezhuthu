"""Feedback and explanations in Tamil (default) and English. Template-based so they work offline."""

from __future__ import annotations

from typing import Any

from ..text import LEVEL_NAMES, aksharas, iso_to_tamil

DYNASTY_TA = {"chola": "சோழர்", "pallava": "பல்லவர்", "pandya": "பாண்டியர்", "chera": "சேரர்",
              "vijayanagara": "விஜயநகர", "nayaka": "நாயக்கர்"}

VOWELS = ("a", "ā", "i", "ī", "u", "ū", "e", "ē", "ai", "o", "ō", "au")


def _letter_class(iso: str) -> tuple[str, str]:
    if iso in VOWELS:
        return "உயிர் எழுத்து", "a vowel"
    if not any(iso.endswith(v) for v in VOWELS):
        return "மெய் எழுத்து", "a pure consonant"
    return "உயிர்மெய் எழுத்து", "a consonant with a vowel"


def hint_for(item_type: str, answer_iso: str) -> tuple[str, str]:
    """A hint that narrows the answer without giving it away."""
    if item_type == "letter":
        cls_ta, cls_en = _letter_class(answer_iso)
        if answer_iso in VOWELS:
            return (f"குறிப்பு: இது ஒரு {cls_ta}.", f"Hint: this is {cls_en}.")
        cons = aksharas(answer_iso)[0].rstrip("aāiīuūeēoō") or answer_iso
        row_ta = iso_to_tamil(cons + "a")
        return (f"குறிப்பு: இது ஒரு {cls_ta}; «{row_ta}» வரிசையைச் சேர்ந்தது.",
                f"Hint: this is {cls_en}, from the «{cons}a» row.")
    parts = aksharas(answer_iso.replace(" ", ""))
    first = parts[0] if parts else answer_iso[:1]
    return (f"குறிப்பு: இதில் {len(parts)} எழுத்துகள் உள்ளன; முதல் எழுத்து «{iso_to_tamil(first)}».",
            f"Hint: it has {len(parts)} letters; the first is «{first}».")


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
    dyn_ta = DYNASTY_TA.get(dyn.lower(), dyn)
    date = facts.get("approx_date")
    level = facts.get("level", "L1")
    lvl_en, lvl_ta = LEVEL_NAMES[level]
    ta, en = [], []
    if dyn:
        ta.append(f"இது {dyn_ta} காலக் கல்வெட்டு" + (f" ({date})." if date else "."))
        en.append(f"This is a {dyn} inscription" + (f" ({date})." if date else "."))
    for e in facts.get("entities", []):
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
