"""Build the app's try-it samples from the benchmark: real DHARMA passages in two groups.

Writes app/web/src/samples/samples.json (the gallery) and app/web/src/samples/sample-images.json (the spec that
app/web/scripts/render-sample-images.mjs turns into the synthetic photos under app/web/public/samples/).

Groups (eval/reports/2026-11-02-samples.md):
- "masked" (the primary set): a span the DHARMA editor restored, hidden as [?N] in a passage of a VAL benchmark
  item. The edition's reading is shipped with the sample so the app can show it after the restorer's answer. VAL
  only: TEST is never shown, and TRAIN would be leaky (the 5-gram and retrieval read train text). The items are
  drawn by the pre-declared rule in `select_masked()`, not picked by hand.
- "unsolved": TRAIN passages whose gaps are all `blank`s (letters lost on the stone that the editor did not
  restore). Nobody knows the answer; the expected outcome is that the system proposes options and asks an expert.

Each sample carries `recorded`: what EzhuthuService.restore returned for it in the live recording
(app/web/src/samples/recorded-restores.json, made by scripts/record_sample_restores.py), which the mock API replays.

tests/test_samples.py enforces the split rules and that the committed JSON matches this script.

Editorial normalisation (stated in the gallery): DHARMA's line-break hyphens are joined into running text,
'‡' (an edition-specific mark, dropped as in the corpus's Tamil display text) is removed, editorial dashes '—' become '·',
editor brackets around damaged-but-read letters ("i[ṭai]") are removed, and Tamil numerals in the Tamil text
are written as the same digits the ISO text uses (the API accepts digits, not ௰). The Tamil text is derived
from the ISO passage with the corpus converter (ezhuthu.corpus.script.iso_to_tamil_display). Gap markers are kept exactly.

Run: .venv/bin/python scripts/build_samples.py          (add --check to verify the committed files)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
BENCH = REPO / "benchmark"
OUT_DIR = REPO / "app" / "web" / "src" / "samples"
RECORDED = OUT_DIR / "recorded-restores.json"
GAP_RE = re.compile(r"\[\?(\d{1,3})?\]")
TAMIL_DIGITS = {"௦": "0", "௧": "1", "௨": "2", "௩": "3", "௪": "4", "௫": "5", "௬": "6", "௭": "7", "௮": "8",
                "௯": "9", "௰": "10", "௱": "100", "௲": "1000"}

# era -> (Tamil name, English name, suggested Learn level)
ERAS = {
    "pallava": ("பல்லவர்", "Pallava", "L3"),
    "pandya": ("பாண்டியர்", "Pāṇḍya", "L4"),
    "chola": ("சோழர்", "Chola", "L2"),
    "rashtrakuta": ("இராஷ்டிரகூடர்", "Rāṣṭrakūṭa", "L2"),
    "vijayanagara": ("விஜயநகரம்", "Vijayanagara", "L1"),
}

# Hand-picked, in rough date order. `lines` is a 0-based [start, end) window into the edition's text lines.
# Facts in `why_*` come from the edition's own title, summary or text; numbers are read off the passage.
PICKS: list[dict] = [
    {
        "id": "hero-stone-naiya-vatukan", "inscription_id": "DHARMA_INSPallava00418", "era": "pallava", "lines": (0, 8),
        "title_ta": "நைய வடுகன் நடுகல்", "title_en": "Hero stone of Naiya Vaṭukaṉ",
        "place_ta": "வேடர்தட்டக்கல்", "place_en": "Vēṭartaṭṭakkal",
        "why_en": "A memorial stone for a fallen soldier, dated by the reign of the Pallava king Mahendravarman. "
               "The lost letters sit just before 'paṭṭāṉ', 'he fell'.",
        "why_ta": "போரில் வீழ்ந்த வீரனுக்கான நடுகல்; பல்லவ மன்னன் மகேந்திரவர்மனின் ஆட்சியாண்டால் காலம் "
               "குறிக்கப்படுகிறது. 'பட்டான்' (வீழ்ந்தான்) என்ற சொல்லுக்கு முன் எழுத்துகள் அழிந்துள்ளன.",
    },
    {
        "id": "mamallapuram-calf-pasture", "inscription_id": "DHARMA_INSPallava00092", "era": "pallava", "lines": (0, 11),
        "title_ta": "மாமல்லபுரத்தில் கன்று மேய் கழனி", "title_en": "A pasture for calves at Māmallapuram",
        "place_ta": "மாமல்லபுரம், ஆதிவராகர் கோயில்", "place_en": "Mahābalipuram, Ādivarāha",
        "why_en": "The town's merchants (nakarattār) buy land as grazing for calves in Nandivarman's 65th year. "
               "The stone names Māmallapuram itself.",
        "why_ta": "மாமல்லபுரத்து நகரத்தார் கன்றுகள் மேய நிலம் வாங்கிய பதிவு; நந்திவர்மனின் 65ஆம் ஆட்சியாண்டு. "
               "ஊரின் பெயரே கல்லில் உள்ளது.",
    },
    {
        "id": "uttiramerur-tank-gold", "inscription_id": "DHARMA_INSPallava00217", "era": "pallava", "lines": (0, 2),
        "title_ta": "உத்திரமேரூர் ஏரிக்கு ஆயிரம் கழஞ்சு பொன்", "title_en": "A thousand kaḻañcu of gold for Uttiramērūr's tank",
        "place_ta": "உத்திரமேரூர்", "place_en": "Uttiramērūr",
        "why_en": "Gold for the Vayiramēka tank in Kampavarman's 15th year, and the village assembly (sabhai) "
               "promising to dredge it every year.",
        "why_ta": "கம்பவர்மனின் 15ஆம் ஆண்டில் வயிரமேகத் தடாகத்துக்குப் பொன்; ஆண்டுதோறும் ஏரியைத் தூர்வார ஊர்ச் "
               "சபை உறுதியளிக்கிறது.",
    },
    {
        "id": "piranmalai-undying-goats", "inscription_id": "DHARMA_INSTamilNadu00406", "era": "pandya", "lines": (0, 8),
        "title_ta": "சாவா மூவாப் பேராடு", "title_en": "Goats that never die, for a lamp",
        "place_ta": "பிரான்மலை, மங்கைபாகர் கோயில்", "place_en": "Pirāṉmalai, Maṅkai Pākar temple",
        "why_en": "Dated by Sundara Pāṇḍya, 'who took the Chola country'. A devotee gives 50 'undying, unageing' "
               "goats (cāvā mūvā pēr āṭu): the flock is kept up for ever so the lamp's ghee never runs out.",
        "why_ta": "'சோணாடு கொண்டருளிய' சுந்தர பாண்டியனின் ஆட்சியாண்டு. ஓர் அடியார் 50 'சாவா மூவாப் பேராடு' "
               "அளிக்கிறார்: விளக்கின் நெய் என்றும் குறையாதபடி மந்தை என்றும் பேணப்படும்.",
    },
    {
        "id": "tiruppattur-tamil-singers", "inscription_id": "DHARMA_INStfaSIIv25p0i0099", "era": "pandya", "lines": (0, 8),
        "title_ta": "தமிழ் பாடுவார்க்குக் கொடை", "title_en": "A gift for the singers of Tamil",
        "place_ta": "திருப்பத்தூர், திருத்தளீசுவரர் கோயில்", "place_en": "Tiruppattūr, Tiruttaḷīśvara temple",
        "why_en": "In Kulaśekhara's reign a man marks his birthday star, Punarpūcam, with a festival and food "
               "offerings, and provides for the drummer and those who sing in Tamil (tamiḻ pāṭuvār).",
        "why_ta": "குலசேகரன் ஆட்சியில் ஒருவர் தம் பிறந்த நாளான புனர்பூசத்தன்று திருநாளும் அமுதுபடியும் "
               "ஏற்படுத்தி, மத்தளக்காரனுக்கும் தமிழ் பாடுவார்க்கும் வழிசெய்கிறார்.",
    },
    {
        "id": "melappaluvur-who-took-madurai", "inscription_id": "DHARMA_INSMelKil00001", "era": "chola", "lines": (0, 5),
        "title_ta": "'மதிரை கொண்ட' பராந்தகன்", "title_en": "'He who took Madurai'",
        "place_ta": "மேலப்பழுவூர், அகத்தீசுவரர் கோயில்", "place_en": "Mēlappaḻuvūr, Agastyeśvara temple",
        "why_en": "Opens with Parāntaka I's title 'matirai koṇṭa', 'who took Madurai'. Chola stones date "
               "themselves by such titles and the regnal year, here year 36.",
        "why_ta": "'மதிரை கொண்ட' என்ற முதலாம் பராந்தகனின் பட்டத்துடன் தொடங்குகிறது. சோழர் கல்வெட்டுகள் "
               "இப்படிப் பட்டத்தாலும் ஆட்சியாண்டாலும் (இங்கே 36) காலம் குறிக்கின்றன.",
    },
    {
        "id": "tiruvavaduturai-coconut-grove", "inscription_id": "DHARMA_INSTiruvavatuturai10135", "era": "chola",
        "lines": (0, 2),
        "title_ta": "இறைவனுக்குத் தென்னந்தோப்பு", "title_en": "A coconut grove for the god",
        "place_ta": "திருவாவடுதுறை, கோமுக்தீசுவரர் கோயில்", "place_en": "Tiruvāvaṭutuṟai, Gomuktīśvara temple",
        "why_en": "The assembly of Cāttaṉūr sells four mā of its common land, tax-free, to keep up a coconut "
               "garden for the temple, in Parāntaka I's 2nd year.",
        "why_ta": "சாத்தனூர் சபையார் தங்கள் பொது நிலத்தில் நான்கு மா நிலத்தை இறையிலியாக விற்று, கோயில் "
               "தென்னந்தோப்புக்கு அளித்தனர் (முதலாம் பராந்தகன், 2ஆம் ஆண்டு).",
    },
    {
        "id": "thanjavur-kuntavai-jewels", "inscription_id": "DHARMA_INStfaSIIv02p0i0002", "era": "chola", "lines": (23, 25),
        "title_ta": "குந்தவையின் அணிகலன்கள், தஞ்சைப் பெரிய கோயில்", "title_en": "Kuntavai's jewels for the Big Temple",
        "place_ta": "தஞ்சாவூர், பெருவுடையார் கோயில்", "place_en": "Thanjavur, Bṛhadīśvara temple",
        "why_en": "Rājarāja I's elder sister Kuntavai gives gold jewels to the Thanjavur temple; every piece is "
               "listed with its weight in kaḻañcu and mañcāṭi.",
        "why_ta": "இராசராசனின் தமக்கை குந்தவை தஞ்சைக் கோயிலுக்கு அளித்த பொன் அணிகலன்கள்; ஒவ்வொன்றின் எடையும் "
               "கழஞ்சு, மஞ்சாடியில் குறிக்கப்பட்டுள்ளது.",
    },
    {
        "id": "nagapattinam-srivijaya-gift", "inscription_id": "DHARMA_INSTamilNadu00166", "era": "chola", "lines": (0, 2),
        "title_ta": "நாகையில் ஸ்ரீவிஜயத்தின் கொடை", "title_en": "A gift from Śrīvijaya at Nākappaṭṭiṉam",
        "place_ta": "நாகப்பட்டினம், காயாரோகணர் கோயில்", "place_en": "Nākappaṭṭiṉam, Kāyārōkaṇam temple",
        "why_en": "An officer (kaṉmi) of the king of Śrīvijaya, across the sea in Southeast Asia, gives gold and "
               "jewels to the Nākai temple in Rājendra Cōḻa's 3rd year.",
        "why_ta": "கடல் கடந்த ஸ்ரீவிஜய அரசனின் கன்மி (அலுவலர்) ஒருவர், இராசேந்திர சோழனின் 3ஆம் ஆண்டில் நாகை "
               "இறைவனுக்குப் பொன்னும் மணிகளும் அளித்தார்.",
    },
    {
        "id": "narttamalai-carpenter", "inscription_id": "DHARMA_INStfaSIIv17p0i0387", "era": "chola", "lines": (0, 11),
        "title_ta": "கோயில் கட்டிய தச்சருக்கு நிலம்", "title_en": "Land for the carpenter who built the temples",
        "place_ta": "நார்த்தாமலை, திருமலைக்கடம்பர் கோயில்", "place_en": "Nārttāmalai, Tirumalaikkatampar temple",
        "why_en": "The temple's managers reward the carpenter Akaḷaṅka Ācāri with land for building the shrines: "
               "the stone names the builder, not only the donor.",
        "why_ta": "கோயில்களைக் கட்டிய தச்சர் அகளங்க ஆசாரிக்கு நிலம் கொடுத்த பதிவு; கொடையாளி மட்டுமல்ல, "
               "கட்டியவரின் பெயரும் கல்லில் நிற்கிறது.",
    },
    {
        "id": "darasuram-poyya-tamilar", "inscription_id": "DHARMA_INSTamilNadu00610", "era": "chola", "lines": (0, 2),
        "title_ta": "தாராசுரத்தில் 'பொய்யாத் தமிழர்'", "title_en": "'The Tamil who does not lie' at Darasuram",
        "place_ta": "தாராசுரம், ஐராவதேசுவரர் கோயில்", "place_en": "Tārācuram (Darasuram), Airāvateśvara temple",
        "why_en": "From a temple in the Great Living Chola Temples World Heritage site: an overseer named "
               "Poyyā-t-tamiḻar petitions for land for the god.",
        "why_ta": "'பெரும் சோழர் கோயில்கள்' உலகப் பாரம்பரியச் சின்னத்தில் உள்ள கோயில் இது; 'பொய்யாத் தமிழர்' என்ற "
               "கண்காணி இறைவனுக்கு நிலம் வேண்டி விண்ணப்பிக்கிறார்.",
    },
    {
        "id": "ukkal-who-took-kacci-tancai", "inscription_id": "DHARMA_INStfaSIIv03p0i0007", "era": "rashtrakuta",
        "lines": (0, 6),
        "title_ta": "'கச்சியும் தஞ்சையும் கொண்ட' கன்னரதேவன்", "title_en": "'He who took Kacci and Tañcai'",
        "place_ta": "உக்கல், பெருமாள் கோயில்", "place_en": "Ukkal, Perumāḷ temple",
        "why_en": "Dated by the Rāṣṭrakūṭa king Kaṇṇaradeva, 'who took Kacci and Tañcai' (Kanchipuram and "
               "Thanjavur): the village assembly records its rules on land and fines.",
        "why_ta": "'கச்சியும் தஞ்சையும் கொண்ட' இராஷ்டிரகூட மன்னன் கன்னரதேவனின் ஆட்சியாண்டில், ஊர்ச் சபை நிலம், "
               "தண்டம் பற்றிய தன் விதிகளைப் பதிகிறது.",
    },
    {
        "id": "tiruvannamalai-krishnadevaraya", "inscription_id": "DHARMA_INStfaSIIv08p0i0165", "era": "vijayanagara",
        "lines": (26, 32),
        "title_ta": "கிருஷ்ணதேவராயனின் படையெடுப்புகள்", "title_en": "Kṛṣṇadevarāya's campaigns",
        "place_ta": "திருவண்ணாமலை, அருணாசலேசுவரர் கோயில்", "place_en": "Tiruvaṇṇāmalai, Aruṇācaleśvara",
        "why_en": "Kṛṣṇadevarāya of Vijayanagara lists the hill forts he took before his gift at Tiruvaṇṇāmalai "
               "(Śaka 1438, 1516 CE): Tamil inscriptions carry on into the 16th century.",
        "why_ta": "விஜயநகர மன்னன் கிருஷ்ணதேவராயன் தான் கைப்பற்றிய மலைக்கோட்டைகளைப் பட்டியலிட்டுத் "
               "திருவண்ணாமலைக்குக் கொடை அளிக்கிறான் (சக 1438, கி.பி. 1516); தமிழ்க் கல்வெட்டு மரபு 16ஆம் "
               "நூற்றாண்டு வரை தொடர்கிறது.",
    },
]

# Synthetic photos for the upload/OCR flow, rendered from samples above (no third-party images).
IMAGES: list[dict] = [
    {"id": "stone-chola", "sample": "melappaluvur-who-took-madurai", "script": "tamil", "style": "stone", "lines": (0, 4),
         "title_en": "Carved granite, Tamil", "title_ta": "கருங்கல் செதுக்கல், தமிழ்"},
    {"id": "hero-stone", "sample": "hero-stone-naiya-vatukan", "script": "tamil", "style": "hero", "lines": (0, 8),
         "title_en": "Hero stone, Tamil", "title_ta": "நடுகல், தமிழ்"},
    {"id": "photo-angle", "sample": "nagapattinam-srivijaya-gift", "script": "tamil", "style": "photo", "lines": (0, 1),
         "title_en": "Temple wall photo, tilted", "title_ta": "கோயில் சுவர் படம், சாய்வாக"},
    {"id": "handout-iso", "sample": "mamallapuram-calf-pasture", "script": "iso15919", "style": "page", "lines": (0, 11),
         "title_en": "Printed transliteration", "title_ta": "அச்சிட்ட ஒலிபெயர்ப்பு"},
]


def norm_line(s: str) -> str:
    s = s.replace("‡", "").replace("—", "·")
    s = re.sub(r"\[(?!\?)([^\]]*)\]", r"\1", s)  # editor brackets around read-but-damaged letters
    return re.sub(r"[ \t]+", " ", s).strip()


def to_tamil(iso: str) -> str:
    """Tamil script with the corpus's own converter; numerals stay as the digits the ISO text uses."""
    from ezhuthu.corpus.script import iso_to_tamil_display

    return "".join(TAMIL_DIGITS.get(ch, ch) for ch in iso_to_tamil_display(iso))


def join_lines(lines: list[str]) -> str:
    """Running text from edition lines. '-x' continues the previous word, '--x' continues it with a hyphen."""
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


def _letters(s: str) -> str:
    """Context key: letters and digits only, every gap marker as '?'."""
    s = unicodedata.normalize("NFC", GAP_RE.sub("?", s))
    return "".join(ch for ch in s if ch.isalnum() or ch == "?" or unicodedata.category(ch).startswith("M"))


def _wild(key: str) -> str:
    return "".join(".{0,12}" if ch == "?" else re.escape(ch) for ch in key)


def match_blanks(text: str, blanks: list[dict]) -> list[str]:
    """Benchmark blank ids for the gaps in `text` (running ISO text): the blank's own left and right context
    (up to 8 letters each side, at least 6 in all) must sit around the gap; a gap that ends or starts the
    passage is matched on its one remaining side."""
    found: list[str] = []
    for m in GAP_RE.finditer(text):
        left, right = _letters(text[:m.start()]), _letters(text[m.end():])
        for bl in blanks:
            if bl["id"] in found or bl["split"] != "train" or bl["kind"] != "blank":
                continue
            lk, rk = _letters(bl["left"])[-8:], _letters(bl["right"])[:8]
            # Near the passage's ends there may be fewer letters than the blank's context: compare what is there.
            if left and len(left) < len(lk):
                lk = lk[-len(left):]
            if right and len(right) < len(rk):
                rk = rk[:len(right)]
            # A gap at either end of the passage is matched on the side that the passage still has.
            # A '?' in the blank's context is a span the editor supplied; here it is spelled out.
            lk_ok = bool(re.search(_wild(lk) + "$", left)) if left else len(rk) >= 6
            rk_ok = bool(re.match(_wild(rk), right)) if right else len(lk) >= 6
            if len(lk) + len(rk) >= 6 and lk_ok and rk_ok:
                found.append(bl["id"])
                break
    return sorted(found)


def wrap(line: str, width: int = 56) -> list[str]:
    """Break a long line at spaces so that the rendered image and `expected_text` have the same lines."""
    out: list[str] = []
    for word in line.split(" "):
        if out and len(out[-1]) + 1 + len(word) <= width:
            out[-1] += " " + word
        else:
            out.append(word)
    return out


def load_jsonl(name: str) -> list[dict]:
    with open(BENCH / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def held_out_ids() -> set[str]:
    ids = {r["id"] for r in load_jsonl("inscriptions.jsonl") if r["split"] != "train"}
    for name in ("items.val.jsonl", "items.test.jsonl", "items.test-hard.jsonl", "items.test-age.jsonl"):
        ids |= {r["inscription_id"] for r in load_jsonl(name)}
    return ids


# ---------------------------------------------------------------------------------------------------------------
# Masked samples: VAL benchmark items whose published restoration is known.
#
# SELECTION RULE (declared in eval/reports/2026-11-02-samples.md and committed before any live run; do not tune):
#   1. Pool: every item of benchmark/items.val.jsonl (VAL split only; never TEST, never TRAIN) with
#      1 <= gap_chars <= MASKED_MAX_GAP Tamil letters, whose edition declares CC BY-SA 4.0 and whose dynasty is one of
#      the app's five periods (VAL_ERAS). Hard and non-hard items alike; the `hard` flag is recorded per sample.
#   2. Context: the item's own left/right context (benchmark/DATA_CARD.md), cut at the nearest other gap marker on
#      each side so that the passage has exactly one gap; left keeps at most MASKED_LEFT_CHARS characters and right at
#      most MASKED_RIGHT_CHARS, both cut to whole words. Readable: at least MASKED_MIN_LEFT letters left and
#      MASKED_MIN_RIGHT letters right, and the API accepts the passage in both scripts.
#   3. Draw: the pool sorted by item id, shuffled with random.Random(MASKED_SEED); then round-robin over the periods
#      in ERAS order, each period taking its next shuffled item from an inscription not yet used, until MASKED_N items
#      are picked or the pool runs out.
#   4. Every picked item is run once through EzhuthuService.restore (scripts/record_sample_restores.py) and reported
#      as it comes out; none is replaced, whatever the result.
# ---------------------------------------------------------------------------------------------------------------
VAL_ERAS = {"Pallava": "pallava", "Pāṇḍya": "pandya", "Cōḻa": "chola", "Rāṣṭrakūṭa": "rashtrakuta",
            "Vijayanagara": "vijayanagara"}
MASKED_SEED = 38  # PR #38
MASKED_N = 10
MASKED_MAX_GAP = 8
MASKED_LEFT_CHARS, MASKED_RIGHT_CHARS = 160, 100
MASKED_MIN_LEFT, MASKED_MIN_RIGHT = 30, 15


def _n_letters(s: str) -> int:
    return sum(1 for ch in s if ch.isalpha())


def masked_context(item: dict) -> tuple[str, str] | None:
    """The item's left and right context cut at other gap markers and to whole words, or None when too short."""
    left = norm_line(GAP_RE.split(item["left"])[-1]) if GAP_RE.search(item["left"]) else norm_line(item["left"])
    right = norm_line(GAP_RE.split(item["right"])[0])
    # Rule 2: a side cut at a gap marker, or longer than its cap, starts/ends on a whole word.
    if len(left) > MASKED_LEFT_CHARS:
        left = left[-MASKED_LEFT_CHARS:]
        left = left[left.index(" ") + 1:] if " " in left else left
    elif GAP_RE.search(item["left"]) and " " in left:
        left = left[left.index(" ") + 1:]
    if len(right) > MASKED_RIGHT_CHARS:
        right = right[:MASKED_RIGHT_CHARS]
        right = right[:right.rindex(" ")] if " " in right else right
    elif GAP_RE.search(item["right"]) and " " in right:
        right = right[:right.rindex(" ")]
    # Keep the spacing the edition has right at the gap (the item's own left/right edges).
    if item["left"].endswith(" ") and not left.endswith(" "):
        left += " "
    if item["right"].startswith(" ") and not right.startswith(" "):
        right = " " + right
    if _n_letters(left) < MASKED_MIN_LEFT or _n_letters(right) < MASKED_MIN_RIGHT:
        return None
    return left.lstrip("-·.’' "), right.rstrip("-·.’' ")


def masked_text(item: dict) -> str | None:
    ctx = masked_context(item)
    return None if ctx is None else f"{ctx[0]}[?{item['gap_chars']}]{ctx[1]}"


def select_masked() -> list[dict]:
    """Rules 1 to 3 above: the VAL items behind the masked samples, in draw order."""
    import random

    from ezhuthu.api.limits import BadRequest, check_text

    rows = {r["id"]: r for r in load_jsonl("inscriptions.jsonl")}
    pool: list[dict] = []
    for it in load_jsonl("items.val.jsonl"):
        r = rows[it["inscription_id"]]
        if it["split"] != "val" or r["split"] != "val" or r["licence"] != "CC BY-SA 4.0":
            continue
        if not 1 <= it["gap_chars"] <= MASKED_MAX_GAP or it["dynasty"] not in VAL_ERAS:
            continue
        text = masked_text(it)
        if text is None:
            continue
        try:
            check_text(text, script="iso15919")
            check_text(to_tamil(text), script="tamil")
        except BadRequest:  # rule 2: the API must accept the passage
            continue
        pool.append(it)
    pool.sort(key=lambda x: x["id"])
    random.Random(MASKED_SEED).shuffle(pool)
    queues = {era: [it for it in pool if VAL_ERAS[it["dynasty"]] == era] for era in ERAS}
    picked: list[dict] = []
    used: set[str] = set()
    while len(picked) < MASKED_N and any(queues.values()):
        for era in ERAS:
            q = queues[era]
            while q and q[0]["inscription_id"] in used:
                q.pop(0)
            if q and len(picked) < MASKED_N:
                it = q.pop(0)
                used.add(it["inscription_id"])
                picked.append(it)
    return picked


# The old gallery's lacunae kept in the gallery as the "unsolved" group (chosen before the live run for few gaps and
# period spread; eval/reports/2026-11-02-samples.md). The other PICKS stay as sources for the sample images only.
UNSOLVED_IN_GALLERY = ("hero-stone-naiya-vatukan", "mamallapuram-calf-pasture", "tiruvannamalai-krishnadevaraya")

# Words for the masked samples, keyed by benchmark item id. Written after the draw (they describe the passage, not
# the result); facts come from the edition's title, summary and text. The Tamil is pending a native-speaker check.
MASKED: dict[str, dict] = {
    "DHARMA_INSPallava00219:23:0": {
        "id": "tiruvorriyur-paddy-for-worship", "title_ta": "திருவொற்றியூரில் வழிபாட்டுக்கு நெல்",
        "title_en": "Paddy for worship at Tiruvoṟṟiyūr", "place_ta": "திருவொற்றியூர்", "place_en": "Tiruvoṟṟiyūr",
        "why_en": "In the Pallava king Kampavarman's reign the villagers' assembly (ūrār) takes gold for the temple and "
                  "pays its interest in paddy, measured in kāṭi, to keep the worship going.",
        "why_ta": "பல்லவ மன்னன் கம்பவர்மனின் ஆட்சியில் ஊரார் கோயிலுக்கான பொன்னைப் பெற்று, அதன் வட்டியாக நெல்லைக் "
                  "காடி அளவில் அளந்து வழிபாட்டுக்குத் தருகின்றனர்.",
    },
    "DHARMA_INSTamilNadu00140:5:0": {
        "id": "tirunallaru-temple-office", "title_ta": "திருநள்ளாற்றில் ஒரு கோயில் பணி",
        "title_en": "A temple office at Tirunaḷḷāṟu", "place_ta": "திருநள்ளாறு, தர்ப்பாரண்யேசுவரர் கோயில்",
        "place_en": "Tirunaḷḷāṟu, Tarppāraṇyēcuvarar temple",
        "why_en": "Dated by Caṭaiyavarman Sundara Pāṇḍya: a man is given an office (niyōkam) in the service of the "
                  "lord of Tirunaḷḷāṟu. One letter is lost at the start of a word.",
        "why_ta": "சடையவர்மன் சுந்தர பாண்டியனின் ஆட்சியாண்டு: திருநள்ளாற்று இறைவனின் பணியில் ஒருவருக்கு நியோகம் "
                  "(பதவி) அளிக்கப்படுகிறது. ஒரு சொல்லின் முதல் எழுத்து மறைந்துள்ளது.",
    },
    "DHARMA_INStfaSIIv04p0i0139:9:0": {
        "id": "vellore-rajadhiraja-praise", "title_ta": "இராசாதிராசனின் மெய்க்கீர்த்தி",
        "title_en": "Rājādhirāja's praise of his own reign", "place_ta": "வேலூர்", "place_en": "Vēlūr (Vellore)",
        "why_en": "Part of the meykkīrtti, the poetic list of victories that opens Chola royal orders, of "
                  "Rājādhirāja I. The slab is in the ASI museum at Vellore.",
        "why_ta": "சோழ அரசாணைகளைத் தொடங்கும் வெற்றிப் பட்டியலான முதலாம் இராசாதிராசனின் மெய்க்கீர்த்தியின் ஒரு "
                  "பகுதி. இக்கல் வேலூர் தொல்லியல் அருங்காட்சியகத்தில் உள்ளது.",
    },
    "DHARMA_INSPandya00160:85:0": {
        "id": "tiruvalisvaram-district-name", "title_ta": "திருவாலீசுவரத்தில் ஒரு நாட்டுப் பெயர்",
        "title_en": "A district's name at Tiruvālīśvaram", "place_ta": "திருவாலீசுவரம், வாலீசுவரர் கோயில்",
        "place_en": "Tiruvālīśvaram, Vālīśvara temple",
        "why_en": "A long record of Sundara Cōḻapāṇḍya's 16th year. The gap sits inside the name of a district "
                  "(kūṟṟam), where a single joining letter is missing.",
        "why_ta": "சுந்தர சோழபாண்டியனின் 16ஆம் ஆண்டின் நீண்ட கல்வெட்டு. ஒரு கூற்றத்தின் (நாட்டுப் பிரிவு) பெயருக்குள் "
                  "இணைக்கும் ஓர் எழுத்து மறைந்துள்ளது.",
    },
    "DHARMA_INSTiruvavatuturai10142:23:0": {
        "id": "tiruvavaduturai-taxes-paid-in-gold", "title_ta": "பொன்னால் வரி நீக்கம்",
        "title_en": "Taxes paid off with gold", "place_ta": "திருவாவடுதுறை, கோமுக்தீசுவரர் கோயில்",
        "place_en": "Tiruvāvaṭutuṟai, Gomuktīśvara temple",
        "why_en": "In Parakesarivarman's 38th year a village assembly takes gold from Tirukkaṟṟaḷi Piccar and in "
                  "return pays the land's taxes for ever, so the god's land is tax-free. The stone lists the dues.",
        "why_ta": "பரகேசரிவர்மனின் 38ஆம் ஆண்டில் ஊர்ச் சபை திருக்கற்றளிப் பிச்சரிடம் பொன் பெற்று, இறைவனின் "
                  "நிலத்துக்கான வரிகளை என்றும் தானே செலுத்த ஒப்புகிறது; கல் அந்த வரிகளைப் பட்டியலிடுகிறது.",
    },
    "DHARMA_INSKotumpalur00038:20:0": {
        "id": "kodumbalur-four-boundaries", "title_ta": "கொடும்பாளூரில் நான்கெல்லை",
        "title_en": "Four boundaries at Koṭumpāḷūr", "place_ta": "கொடும்பாளூர், மூவர்கோயில்",
        "place_en": "Koṭumpāḷūr, Mūvarkōyil",
        "why_en": "From the Mūvarkōyil, dated by Vīra Pāṇḍya's 17th year: land is marked out by its four boundaries "
                  "with everything inside them, wet and dry fields, tank and house sites.",
        "why_ta": "வீரபாண்டியனின் 17ஆம் ஆண்டு, மூவர்கோயில் கல்வெட்டு: நன்செய், புன்செய், குளம், நத்தம் என உள்ளடங்கிய "
                  "அனைத்துடன் நிலம் அதன் நான்கெல்லைகளால் வரையறுக்கப்படுகிறது.",
    },
    "DHARMA_INSTamilOutsideTN00003:3:0": {
        "id": "kolar-rajendra-praise", "title_ta": "கோலாரில் இராசேந்திரனின் மெய்க்கீர்த்தி",
        "title_en": "Rājendra Cōḻa's praise, at Kōlār", "place_ta": "கோலார், கோலாரம்மா கோயில்",
        "place_en": "Kōlār, Kōlārammā temple",
        "why_en": "A Tamil inscription outside Tamil Nadu, in Karnataka, from Rājendra Cōḻa's 20th year. The king "
                  "is likened to Viṣṇu as the boar, lifting the earth unharmed.",
        "why_ta": "தமிழ்நாட்டுக்கு வெளியே, கர்நாடகத்தில் உள்ள தமிழ்க் கல்வெட்டு (இராசேந்திர சோழனின் 20ஆம் ஆண்டு). "
                  "மன்னன் நிலமகளைச் சலியாமல் எடுத்த வராகத் திருமாலுக்கு ஒப்பிடப்படுகிறான்.",
    },
    "DHARMA_INSCirkali00008:6:0": {
        "id": "sirkazhi-traitors-lands", "title_ta": "சீர்காழியில் துரோகிகளின் நிலம்",
        "title_en": "The traitors' lands at Cīrkāḻi", "place_ta": "சீர்காழி, பிரமபுரீசுவரர் கோயில்",
        "place_en": "Cīrkāḻi, Brahmapurīśvara temple",
        "why_en": "From Rājarāja I's reign: the lands of men who committed treason (turōkam) are taken and sold. "
                  "The gap is in the name of a division (vaḷanāṭu) called after a king.",
        "why_ta": "முதலாம் இராசராசனின் ஆட்சி: துரோகம் செய்தவர்களின் நிலங்கள் பறிக்கப்பட்டு விற்கப்படுகின்றன. ஓர் "
                  "அரசனின் பெயரால் அமைந்த வளநாட்டின் பெயரில் இடைவெளி உள்ளது.",
    },
    "DHARMA_INSCirkali00034:2:2": {
        "id": "sirkazhi-feeding-house", "title_ta": "சீர்காழியில் ஒரு சத்திரம்",
        "title_en": "A feeding house at Cīrkāḻi", "place_ta": "சீர்காழி, பிரமபுரீசுவரர் கோயில்",
        "place_en": "Cīrkāḻi, Brahmapurīśvara temple",
        "why_en": "In Kulottuṅga Cōḻa's 27th year a group of brothers receive money for a feeding house (catiram); "
                  "the stone names each of them in turn.",
        "why_ta": "குலோத்துங்க சோழனின் 27ஆம் ஆண்டில் உடன்பிறந்தோர் சிலர் ஒரு சத்திரத்துக்காகக் காசு பெறுகின்றனர்; "
                  "கல் அவர்களை ஒவ்வொருவராகப் பெயரிடுகிறது.",
    },
    "DHARMA_INSMelKil00011:3:0": {
        "id": "melappaluvur-rajendra-conquests", "title_ta": "இராசேந்திரனின் வெற்றிகள், கோயில் அடித்தளத்தில்",
        "title_en": "Rājendra I's conquests, on a temple base", "place_ta": "மேலப்பழுவூர், அகத்தீசுவரர் கோயில்",
        "place_en": "Mēlappaḻuvūr, Agastyeśvara temple",
        "why_en": "Carved round the base of a shrine in Rājendra I's 15th year (about 1027 CE): the list of lands "
                  "he took, from the Western Ghats to Sri Lanka.",
        "why_ta": "முதலாம் இராசேந்திரனின் 15ஆம் ஆண்டில் (சுமார் கி.பி. 1027) கருவறை அடித்தளத்தைச் சுற்றிச் "
                  "செதுக்கப்பட்டது: அவன் வென்ற நாடுகளின் பட்டியல்.",
    },
}


def passage_lines(masked_iso: str, passage: str) -> list[int]:
    """1-based first and last line (of the edition's text lines) that the passage's letters come from."""
    starts, full = [], ""
    for ln in masked_iso.split("\n"):
        starts.append(len(full))
        full += _letters(ln)
    key = _letters(passage)
    at = full.find(key)
    if at < 0 or full.find(key, at + 1) >= 0:
        raise SystemExit(f"passage not found exactly once in its edition: {passage[:60]}")
    def line_of(off: int) -> int:
        return max(i for i, s0 in enumerate(starts) if s0 <= off)

    return [line_of(at) + 1, line_of(at + len(key) - 1) + 1]


def load_recorded() -> dict:
    return json.loads(RECORDED.read_text("utf-8")) if RECORDED.exists() else {"samples": {}}


def recorded_summary(sample: dict, rec: dict) -> dict | None:
    """What the live recording returned for this sample, and (masked) how it compares with the edition."""
    from ezhuthu.corpus.script import normalise_for_scoring

    got = rec["samples"].get(sample["id"])
    if got is None:
        return None
    if got["text_iso"] != sample["text_iso"]:
        raise SystemExit(f"{sample['id']}: recorded text differs from the sample; re-run record_sample_restores.py")
    resp, gaps = got["response"], []
    for g in resp["gaps"]:
        best = g["candidates"][g["chosen"]] if g["decision"] == "fill" and g["chosen"] is not None else None
        top = g["candidates"][0] if g["candidates"] else None
        row = {"decision": g["decision"],
               "proposal_iso": (best or top or {}).get("text"), "proposal_tamil": (best or top or {}).get("text_tamil"),
               "confidence": (best or top or {}).get("confidence")}
        if sample["group"] == "masked":
            want = sample["edition_reading"]["norm"]
            row["top_matches"] = bool(top) and normalise_for_scoring(top["text"]) == want
            row["any_matches"] = any(normalise_for_scoring(c["text"]) == want for c in g["candidates"])
            row["outcome"] = ("open" if best is None else
                              "match" if normalise_for_scoring(best["text"]) == want else "differs")
        else:
            row["outcome"] = "filled" if best else "open"
        gaps.append(row)
    return {"date": rec["meta"]["date"], "models_used": resp["models_used"], "gaps": gaps}


def unsolved_passage(p: dict, rows: dict, blanks: dict, held: set[str]) -> dict:
    from ezhuthu.api.limits import check_text  # the API's own input check

    r = rows[p["inscription_id"]]
    if r["split"] != "train" or r["id"] in held:
        raise SystemExit(f"{r['id']} is not a train inscription")
    if r["licence"] != "CC BY-SA 4.0":  # the edition file itself must declare the licence we credit
        raise SystemExit(f"{r['id']}: edition licence is {r['licence']!r}, not CC BY-SA 4.0")
    a, b = p["lines"]
    text_iso = join_lines([norm_line(x) for x in r["text_iso"].split("\n")[a:b]])
    text_tamil = to_tamil(text_iso)
    n_iso, n_ta = len(GAP_RE.findall(text_iso)), len(GAP_RE.findall(text_tamil))
    if not 1 <= n_iso == n_ta:
        raise SystemExit(f"{p['id']}: gap counts ISO {n_iso} / Tamil {n_ta}")
    try:
        check_text(text_iso, script="iso15919")
        check_text(text_tamil, script="tamil")
    except Exception as e:
        raise SystemExit(f"{p['id']}: the API would reject this text: {e}") from e
    # Every gap is a benchmark blank (lost, unrestored) of this train inscription, matched by its context.
    ids = match_blanks(text_iso, blanks.get(r["id"], []))
    if len(ids) != n_iso:
        raise SystemExit(f"{p['id']}: {n_iso} gaps but {len(ids)} matched train blanks ({ids})")
    eta, een, level = ERAS[p["era"]]
    return {
        "id": p["id"], "group": "unsolved", "inscription_id": r["id"], "split": r["split"], "blank_ids": ids,
        "item_id": None, "hard": None,
        "era": p["era"], "era_ta": eta, "era_en": een, "learn_level": level,
        "title_ta": p["title_ta"], "title_en": p["title_en"], "place_ta": p["place_ta"], "place_en": p["place_en"],
        "edition_title": r["title"], "ruler": r["ruler"], "regnal_year": r["regnal_year"],
        "dynasty": r["dynasty"], "why_ta": p["why_ta"], "why_en": p["why_en"],
        "lines": [a + 1, b], "gaps": n_iso, "text_iso": text_iso, "text_tamil": text_tamil,
        "edition_reading": None,
        "dharma_url": r["dharmalekha_url"], "source_url": r["source_url"],
        "licence": r["licence"], "licence_url": r["licence_url"], "ta_review": "done",
    }


def masked_passage(it: dict, rows: dict) -> dict:
    from ezhuthu.corpus.script import normalise_for_scoring

    r = rows[it["inscription_id"]]
    if it["split"] != "val" or r["split"] != "val":
        raise SystemExit(f"{it['id']} is not a VAL item")
    note = MASKED.get(it["id"])
    if note is None:
        raise SystemExit(f"{it['id']}: drawn by select_masked() but has no MASKED entry")
    text_iso = masked_text(it)
    assert text_iso is not None
    era = VAL_ERAS[it["dynasty"]]
    eta, een, level = ERAS[era]
    return {
        "id": note["id"], "group": "masked", "inscription_id": r["id"], "split": "val", "blank_ids": [],
        "item_id": it["id"], "hard": it["hard"],
        "era": era, "era_ta": eta, "era_en": een, "learn_level": level,
        "title_ta": note["title_ta"], "title_en": note["title_en"],
        "place_ta": note["place_ta"], "place_en": note["place_en"],
        "edition_title": r["title"], "ruler": r["ruler"], "regnal_year": r["regnal_year"],
        "dynasty": r["dynasty"], "why_ta": note["why_ta"], "why_en": note["why_en"],
        "lines": passage_lines(r["text_iso_masked"], text_iso), "gaps": 1,
        "text_iso": text_iso, "text_tamil": to_tamil(text_iso),
        "edition_reading": {"text_iso": it["target"], "text_tamil": to_tamil(it["target"]),
                            "norm": normalise_for_scoring(it["target"])},
        "dharma_url": r["dharmalekha_url"], "source_url": r["source_url"],
        "licence": r["licence"], "licence_url": r["licence_url"], "ta_review": "pending",
    }


def build(recorded: dict | None = None) -> tuple[list[dict], list[dict]]:
    rows = {r["id"]: r for r in load_jsonl("inscriptions.jsonl")}
    blanks: dict[str, list[dict]] = {}
    for b in load_jsonl("blank.jsonl"):
        blanks.setdefault(b["inscription_id"], []).append(b)
    held = held_out_ids()
    sources = {p["id"]: unsolved_passage(p, rows, blanks, held) for p in PICKS}
    samples = [masked_passage(it, rows) for it in select_masked()]
    samples += [sources[i] for i in UNSOLVED_IN_GALLERY]
    rec = recorded if recorded is not None else load_recorded()
    for s in samples:
        s["recorded"] = recorded_summary(s, rec)
    images = []
    for im in IMAGES:
        s = sources[im["sample"]]
        r = rows[s["inscription_id"]]
        a0 = s["lines"][0] - 1
        a, b = im["lines"]
        lines = [norm_line(x) for x in r["text_iso"].split("\n")[a0 + a:a0 + b]]
        if im["script"] == "tamil":
            lines = [to_tamil(x.lstrip("-")) for x in lines]
        lines = [w for x in lines for w in wrap(x)]
        images.append({
            **{k: im[k] for k in ("id", "sample", "script", "style", "title_en", "title_ta")},
            "file": f"samples/{im['id']}.jpg", "inscription_id": s["inscription_id"], "lines": lines,
            "expected_text": "\n".join(lines),
            "credit": f"Synthetic render (Ezhuthu, Noto fonts SIL OFL) of the DHARMA edition {r['id']}, "
                      f"{r['licence']}",
            "dharma_url": s["dharma_url"], "licence": r["licence"], "licence_url": r["licence_url"],
        })
    return samples, images


def dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="fail if the committed JSON differs from a fresh build")
    args = ap.parse_args(argv)
    samples, images = build()
    outs = {OUT_DIR / "samples.json": dump(samples), OUT_DIR / "sample-images.json": dump(images)}
    if args.check:
        stale = [str(p.relative_to(REPO)) for p, txt in outs.items() if not p.exists() or p.read_text("utf-8") != txt]
        if stale:
            print("stale, run scripts/build_samples.py:", ", ".join(stale), file=sys.stderr)
            return 1
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for p, txt in outs.items():
        p.write_text(txt, encoding="utf-8")
        print(f"wrote {p.relative_to(REPO)}")
    print(f"{len(samples)} samples, {sum(s['gaps'] for s in samples)} gaps, {len(images)} image specs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
