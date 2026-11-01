"""Mobile-first wireframes for the app team (design/ux/wireframes/*.svg).

Unlike the logos, wireframe text is live <text> (Noto Sans Tamil / Instrument Sans / Fraunces via Google
Fonts) so the app team can read and copy strings. Colours are the semantic light tokens.
Run: python3 design/tools/build_wireframes.py   (stdlib only)
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
TOK = json.loads((DESIGN / "tokens" / "tokens.json").read_text())


def col(fam, shade):
    return TOK["color"][fam][shade]["$value"]


C = dict(
    bg=col("stone", "100"), surface=col("stone", "50"), raised="#FFFDF8", sunk=col("stone", "200"),
    leaf=col("palm", "100"), border=col("stone", "300"), strong=col("stone", "600"), text=col("ink", "900"),
    muted=col("stone", "700"), faint=col("stone", "600"), accent=col("laterite", "600"),
    accent_soft=col("laterite", "100"), on_accent=col("stone", "50"), lamp=col("lamp", "500"),
    lamp_text=col("lamp", "700"), lamp_soft=col("lamp", "200"), ok=col("neem", "700"), ok_soft=col("neem", "100"),
    unsure=col("neelam", "700"), unsure_soft=col("neelam", "100"), error=col("kumkum", "700"),
    error_soft=col("kumkum", "100"),
)
TA = "'Noto Sans Tamil', 'Instrument Sans', sans-serif"
TA_SERIF = "'Noto Serif Tamil', serif"
UI = "'Instrument Sans', 'Noto Sans Tamil', sans-serif"
DISP = "'Fraunces', 'Noto Serif Tamil', serif"
BRAHMI = "'Noto Sans Brahmi', sans-serif"
GRANTHA = "'Noto Sans Grantha', sans-serif"
FONTS = ("@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400..700"
         "&amp;family=Instrument+Sans:wght@400..700&amp;family=Noto+Sans+Tamil:wght@400..700"
         "&amp;family=Noto+Serif+Tamil:wght@400..700&amp;family=Noto+Sans+Brahmi&amp;family=Noto+Sans+Grantha"
         "&amp;display=block');")

VAT_KA = "M50 13V87M17 47C25 38 39 39 50 50C61 61 75 62 83 53"
PX, PY, PW, PH = 40, 60, 390, 844  # phone frame


def t(x, y, s, size=15, fam=TA, fill=None, w=400, anchor="start", extra=""):
    return (f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{w}" '
            f'fill="{fill or C["text"]}" text-anchor="{anchor}"{extra}>{escape(s)}</text>')


def r(x, y, w, h, fill, rx=12, stroke=None, dash=False, extra=""):
    st = f' stroke="{stroke}"' if stroke else ""
    da = ' stroke-dasharray="5 4"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}"{st}{da}{extra}/>'


def btn(x, y, w, label, kind="primary", h=48):
    if kind == "primary":
        return r(x, y, w, h, C["accent"], h / 2) + t(x + w / 2, y + h / 2 + 6, label, 16, TA, C["on_accent"], 600,
                                                    "middle")
    return (r(x, y, w, h, "none", h / 2, C["strong"]) + t(x + w / 2, y + h / 2 + 6, label, 15, TA, C["text"], 600,
                                                          "middle"))


def chip(x, y, label, fg, bg, w=None):
    w = w or (len(label) * 7.6 + 22)
    return r(x, y, w, 26, bg, 13) + t(x + w / 2, y + 18, label, 12.5, UI, fg, 600, "middle")


def note(n, x, y, lines, ax=None, ay=None):
    """Numbered annotation on the right of the phone, with a leader to (ax, ay)."""
    out = []
    if ax is not None:
        out.append(f'<path d="M{ax} {ay}H{PX + PW + 24}L{x - 14} {y - 5}" fill="none" stroke="{C["lamp"]}" '
                   f'stroke-width="1.2"/>')
        out.append(f'<circle cx="{ax}" cy="{ay}" r="4" fill="{C["lamp"]}"/>')
    out.append(f'<circle cx="{x}" cy="{y - 5}" r="12" fill="{C["lamp"]}"/>')
    out.append(t(x, y, str(n), 13, UI, C["text"], 700, "middle"))
    for i, ln in enumerate(lines):
        out.append(t(x + 22, y + i * 20, ln, 14 if i else 15, UI, C["text"] if i == 0 else C["muted"], 600 if i == 0 else 400))
    return "".join(out)


def phone(body, title_ta, title_en, nav_active=0):
    x, y = PX, PY
    out = [r(x - 10, y - 10, PW + 20, PH + 20, "#2A221B", 54),
           f'<clipPath id="scr"><rect x="{x}" y="{y}" width="{PW}" height="{PH}" rx="44"/></clipPath>',
           '<g clip-path="url(#scr)">', r(x, y, PW, PH, C["bg"], 0)]
    # status + top bar
    out.append(t(x + 30, y + 30, "9:41", 14, UI, C["text"], 600))
    out.append(r(x, y + 48, PW, 56, C["bg"], 0))
    out.append(f'<path d="M{x} {y + 104}H{x + PW}" stroke="{C["border"]}"/>')
    out.append(t(x + 20, y + 84, "எழுத்து", 22, TA_SERIF, C["text"], 700))
    out.append(f'<path d="M{x + 26} {y + 80}l5 -9l5 9z" fill="{C["lamp"]}" opacity="0"/>')
    out.append(chip(x + PW - 128, y + 63, "English", C["text"], C["sunk"], 70))
    out.append(r(x + PW - 48, y + 60, 32, 32, C["sunk"], 16) + f'<path d="M{x + PW - 40} {y + 70}h16M{x + PW - 40} '
               f'{y + 76}h16M{x + PW - 40} {y + 82}h16" stroke="{C["text"]}" stroke-width="2" stroke-linecap="round"/>')
    out.append(t(x + 20, y + 140, title_ta, 24, TA_SERIF, C["text"], 700))
    out.append(t(x + 20, y + 164, title_en, 14, UI, C["muted"], 500))
    out.append(body)
    # bottom tab bar (mobile)
    by = y + PH - 78
    out.append(r(x, by, PW, 78, C["surface"], 0) + f'<path d="M{x} {by}H{x + PW}" stroke="{C["border"]}"/>')
    tabs = [("கற்க", "Learn"), ("மீட்டமை", "Restore"), ("முன்னேற்றம்", "Progress"), ("மதிப்பாய்வு", "Review")]
    for i, (ta, en) in enumerate(tabs):
        cx = x + PW / 8 + i * PW / 4
        active = i == nav_active
        if active:
            out.append(r(cx - 30, by + 10, 60, 28, C["accent_soft"], 14))
        out.append(f'<circle cx="{cx}" cy="{by + 24}" r="6" fill="{C["accent"] if active else "none"}" '
                   f'stroke="{C["accent"] if active else C["faint"]}" stroke-width="2"/>')
        out.append(t(cx, by + 56, ta, 11.5, TA, C["accent"] if active else C["muted"], 600 if active else 500,
                     "middle"))
    out.append("</g>")
    return "".join(out)


def page(name, title, phone_svg, notes):
    W, H = 1000, 980
    head = t(PX, 34, title, 18, UI, C["text"], 700) + t(W - 40, 34, "Ezhuthu · wireframe · mobile 390 × 844", 12,
                                                         UI, C["faint"], 500, "end")
    body = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
            f'aria-label="{escape(title)}"><style>{FONTS}</style>'
            f'<rect width="{W}" height="{H}" fill="#EFE8DA"/>{head}{phone_svg}{notes}</svg>\n')
    (DESIGN / "ux" / "wireframes").mkdir(parents=True, exist_ok=True)
    (DESIGN / "ux" / "wireframes" / f"{name}.svg").write_text(body)


NX = 500  # notes column


def learn():
    x, y = PX + 16, PY + 186
    out = [t(x + 4, y + 4, "நிலையைத் தேர்ந்தெடுங்கள் · Pick a level", 13, TA, C["muted"], 600)]
    levels = [("L1", "இன்றைய தமிழ்", "Modern Tamil", "க", TA, "done"),
              ("L2", "சோழர் தமிழ்", "Chola Tamil", "க", TA_SERIF, "current"),
              ("L3", "பல்லவர் தமிழ்", "Pallava (Grantha)", "\U00011315", GRANTHA, ""),
              ("L4", "வட்டெழுத்து", "Vatteluttu", None, None, ""),
              ("L5", "தமிழ்-பிராமி", "Tamil-Brahmi", "\U00011013", BRAHMI, "")]
    yy = y + 18
    for i, (lv, ta, en, g, fam, state) in enumerate(levels):
        h = 82
        cur = state == "current"
        out.append(r(x, yy, PW - 32, h, C["raised"] if not cur else C["surface"], 16,
                     C["accent"] if cur else C["border"]))
        out.append(r(x + 12, yy + 11, 60, 60, C["leaf"] if lv == "L4" else C["sunk"], 12))
        if g:
            out.append(t(x + 42, yy + 54, g, 30, fam, C["text"], 600, "middle"))
        else:
            out.append(f'<g transform="translate({x + 20} {yy + 19}) scale(.44)"><path d="{VAT_KA}" fill="none" '
                       f'stroke="{C["text"]}" stroke-width="9" stroke-linecap="round"/></g>')
        out.append(t(x + 86, yy + 34, f"{lv} · {ta}", 16, TA, C["text"], 700))
        out.append(t(x + 86, yy + 56, en, 13, UI, C["muted"], 500))
        if state == "done":
            out.append(chip(x + PW - 32 - 96, yy + 28, "✓ முடிந்தது", C["ok"], C["ok_soft"], 86))
        if cur:
            out.append(chip(x + PW - 32 - 84, yy + 28, "தொடர்க", C["on_accent"], C["accent"], 72))
        yy += h + 10
    out.append(btn(x, yy + 6, PW - 32, "பாடத்தைத் தொடங்கு · Start lesson"))
    notes = (note(1, NX, 150, ["Level ladder, easiest first", "L1 modern → L5 Tamil-Brahmi (contract order).",
                               "Each card: era glyph tile, Tamil name, English."], PX + PW - 20, PY + 230)
             + note(2, NX, 270, ["Glyph tile", "Unicode eras use Noto fonts; L4 draws the",
                                 "Vatteluttu SVG from design/glyphs/vatteluttu.json."], PX + 58, PY + 500)
             + note(3, NX, 390, ["State on the card, not by colour alone", "Done = neem chip with ✓ and text;",
                                 "current = laterite border + 'continue' chip."], PX + PW - 60, PY + 340)
             + note(4, NX, 510, ["One primary action per screen", "Full-width pill, 48 px tall (tap ≥ 44 px)."],
                    PX + 200, yy + 30)
             + note(5, NX, 610, ["Bottom tabs on mobile, top nav ≥ 1000 px", "Labels Tamil-first; English via the",
                                 "language toggle in the top bar."], PX + PW / 8, PY + PH - 50))
    page("01-learn", "Learn · கற்க", phone("".join(out), "கற்க", "Learn to read, one era at a time"), notes)


def lesson():
    x, y = PX + 16, PY + 186
    w = PW - 32
    out = [r(x, y, w, 64, C["surface"], 14, C["border"]),
           t(x + 14, y + 26, "பராந்தக சோழன் I · c. 10th c. CE", 13.5, TA, C["text"], 600),
           t(x + 14, y + 48, "Source: DHARMA edition ↗  ·  CC BY-SA 4.0", 12, UI, C["accent"], 500)]
    # progress
    py = y + 82
    out.append(t(x, py + 12, "3 / 10", 13, UI, C["muted"], 600))
    out.append(r(x + 52, py + 4, w - 52, 8, C["sunk"], 4) + r(x + 52, py + 4, (w - 52) * 0.3, 8, C["accent"], 4))
    # glyph card
    gy = py + 30
    out.append(r(x, gy, w, 190, C["raised"], 18, C["border"]))
    out.append(r(x + 14, gy + 14, w - 28, 124, C["leaf"], 12))
    out.append(chip(x + 24, gy + 24, "L4 · வட்டெழுத்து", C["accent"], C["surface"], 120))
    out.append(f'<g transform="translate({x + w / 2 - 50} {gy + 26}) scale(1.0)"><path d="{VAT_KA}" fill="none" '
               f'stroke="{C["text"]}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/></g>')
    out.append(t(x + 18, gy + 170, "இந்த எழுத்து என்ன? · Which letter is this?", 15, TA, C["text"], 700))
    # options
    oy = gy + 202
    opts = ["க", "த", "ப", "ம"]
    bw = (w - 12) / 2
    for i, o in enumerate(opts):
        ox = x + (i % 2) * (bw + 12)
        oyy = oy + (i // 2) * 62
        sel = i == 0
        out.append(r(ox, oyy, bw, 54, C["ok_soft"] if sel else C["raised"], 14, C["ok"] if sel else C["border"]))
        out.append(t(ox + bw / 2, oyy + 38, o, 28, TA, C["ok"] if sel else C["text"], 600, "middle"))
    fy = oy + 126
    out.append(r(x, fy, w, 86, C["ok_soft"], 14, C["ok"]))
    out.append(t(x + 16, fy + 28, "✓ சரியாகப் படித்தீர்கள்!", 16, TA, C["ok"], 700))
    out.append(t(x + 16, fy + 52, "குறுக்குக் கோடு வளைந்து க ஆனது.", 13.5, TA, C["text"], 500))
    out.append(t(x + 16, fy + 72, "The cross-bar became a wave: that is ka.", 12.5, UI, C["muted"], 500))
    out.append(btn(x, fy + 94, w * 0.62, "அடுத்தது · Next", h=44) + btn(x + w * 0.62 + 10, fy + 94, w * 0.38 - 10,
                                                                     "குறிப்பு", "ghost", 44))
    notes = (note(1, NX, 150, ["Inscription context first", "Ruler, date, and a link to the DHARMA edition",
                               "with its licence, on every lesson."], PX + PW - 30, PY + 210)
             + note(2, NX, 260, ["Glyph card (see glyph-card spec)", "Palm-leaf well, era chip, glyph ≥ 96 px.",
                                 "Drawn glyphs say so on long-press / tooltip."], PX + PW - 40, PY + 340)
             + note(3, NX, 380, ["Answer grid, 2 × 2", "Tamil letters at 28 px; 62 px targets.",
                                 "Selected-correct uses colour + ✓ + text."], PX + PW - 40, PY + 520)
             + note(4, NX, 500, ["Feedback in Tamil first", "feedback_ta, then feedback_en in muted text.",
                                 "next_action drives the buttons (advance/repeat/hint)."], PX + PW - 40, PY + 650)
             + note(5, NX, 620, ["Hint is always secondary", "Ghost button; never hides the answer grid."],
                    PX + PW - 60, PY + 735))
    page("02-lesson", "Lesson · பாடம்", phone("".join(out), "பாடம்", "Lesson · reading practice"), notes)


def meter(x, y, w, v, color):
    segs = 10
    gap = 3
    sw = (w - gap * (segs - 1)) / segs
    out = []
    for i in range(segs):
        on = (i + 1) / segs <= v + 1e-9
        out.append(r(x + i * (sw + gap), y, sw, 8, color if on else C["sunk"], 2))
    return "".join(out)


def restore():
    x, y = PX + 16, PY + 186
    w = PW - 32
    out = [r(x, y, w, 76, C["surface"], 14, C["border"]),
           t(x + 14, y + 30, "…கோப்", 17, TA_SERIF, C["text"], 500)]
    out.append(r(x + 76, y + 10, 46, 30, C["lamp_soft"], 8, C["lamp"], True))
    out.append(t(x + 99, y + 31, "பர", 17, TA_SERIF, C["lamp_text"], 700, "middle"))
    out.append(t(x + 130, y + 30, "கேசரிவர்மற்கு…", 17, TA_SERIF, C["text"], 500))
    out.append(t(x + 14, y + 60, "ஆண்டு", 17, TA_SERIF, C["text"], 500))
    out.append(r(x + 74, y + 42, 36, 28, C["unsure_soft"], 8, C["unsure"], True))
    out.append(t(x + 92, y + 62, "?", 16, UI, C["unsure"], 700, "middle"))
    out.append(t(x + 118, y + 60, "ஆவது", 17, TA_SERIF, C["text"], 500))
    # gap 1 card
    cy = y + 94
    out.append(r(x, cy, w, 204, C["raised"], 16, C["border"]))
    out.append(t(x + 14, cy + 28, "இடைவெளி 1 · ~4 எழுத்துகள்", 14.5, TA, C["text"], 700))
    out.append(chip(x + w - 74, cy + 12, "நிரப்பு", C["ok"], C["ok_soft"], 60))
    out.append(r(x + 10, cy + 42, w - 20, 92, C["surface"], 12, C["ok"]))
    out.append(t(x + 22, cy + 70, "பர", 20, TA_SERIF, C["text"], 700) + t(x + 62, cy + 70, "para", 14, DISP,
                                                                           C["muted"], 400, extra=' font-style="italic"'))
    out.append(chip(x + w - 104, cy + 54, "தேர்வு", C["ok"], C["ok_soft"], 54))
    out.append(meter(x + 22, cy + 84, w - 100, 0.8, C["accent"]))
    out.append(t(x + w - 30, cy + 93, "high", 12, UI, C["muted"], 600, "end"))
    out.append(chip(x + 22, cy + 100, "title: Parakesari", C["muted"], C["sunk"], 112)
               + chip(x + 140, cy + 100, "ruler: Parantaka I", C["muted"], C["sunk"], 120))
    out.append(t(x + 22, cy + 160, "இணைப் பகுதிகள் (1) ▸  Parallels", 13, TA, C["accent"], 600))
    out.append(t(x + 22, cy + 190, "+1 lower-confidence candidate", 12.5, UI, C["faint"], 500))
    # gap 2 abstain
    ay = cy + 220
    out.append(r(x, ay, w, 170, C["unsure_soft"], 16, C["unsure"], True))
    out.append(t(x + 16, ay + 30, "இடைவெளி 2", 14.5, TA, C["unsure"], 700))
    out.append(chip(x + w - 134, ay + 12, "விலகல் · abstain", C["unsure"], C["surface"], 122))
    out.append(t(x + 16, ay + 62, "வல்லுநர்களுக்கும் உறுதியில்லை", 17, TA_SERIF, C["text"], 700))
    out.append(t(x + 16, ay + 86, "Experts are unsure", 13.5, UI, C["muted"], 600))
    out.append(t(x + 16, ay + 112, "எந்த நிரப்பும் போதுமான உறுதியுடன் இல்லை.", 12.5, TA, C["text"], 500))
    out.append(t(x + 16, ay + 132, "This is an honest gap: experts leave it open too.", 12, UI, C["muted"], 500))
    out.append(t(x + 16, ay + 156, "Show candidates anyway ▸", 12.5, UI, C["unsure"], 600))
    out.append(t(x, ay + 194, "“Matches expert restorations”, never “correct”.", 12, UI, C["faint"], 500))
    notes = (note(1, NX, 150, ["Restored line, gaps marked in place", "Fill = lamp dashed box; abstain = neelam ?",
                               "Never colour alone: box style + glyph differ."], PX + 200, PY + 210)
             + note(2, NX, 270, ["Candidate row", "Text (Tamil) + ISO in italic, 10-step meter,",
                                 "verbal band (high / medium / low) beside it."], PX + PW - 40, PY + 360)
             + note(3, NX, 390, ["Confidence is banded, not decimal", "Show % only in expert mode; learners see",
                                 "bands. Thresholds come from the decider."], PX + PW - 60, PY + 375)
             + note(4, NX, 510, ["Abstain is a teaching moment", "Calm indigo, dashed edge, Tamil headline;",
                                 "candidates hidden behind a disclosure."], PX + PW - 40, PY + 520)
             + note(5, NX, 630, ["Ontology + parallels", "Chips for ruler/title/place; parallels open",
                                 "a sheet with DHARMA links."], PX + 100, PY + 380))
    page("03-restore", "Restore result · மீட்டமை", phone("".join(out), "மீட்டமை", "Restore a damaged line", 1),
         notes)


def progress():
    x, y = PX + 16, PY + 186
    w = PW - 32
    out = [chip(x + w - 96, y - 10, "SAMPLE DATA", C["lamp_text"], C["lamp_soft"], 96)]
    out.append(r(x, y + 24, w, 170, C["raised"], 16, C["border"]))
    out.append(t(x + 16, y + 54, "எழுத்து வாசிப்பு · Letters read", 14, TA, C["muted"], 600))
    for i, (lab, v, colr) in enumerate([("முன் · Pre", 0.3, C["strong"]), ("பின் · Post", 0.7, C["accent"])]):
        by = y + 78 + i * 46
        out.append(t(x + 16, by + 14, lab, 13, TA, C["text"], 600))
        out.append(r(x + 110, by, w - 180, 18, C["sunk"], 9) + r(x + 110, by, (w - 180) * v, 18, colr, 9))
        out.append(t(x + w - 16, by + 15, f"{int(v * 10)} / 10", 14, UI, C["text"], 700, "end"))
    out.append(t(x + 16, y + 180, "+4 எழுத்துகள் · gain", 16, TA, C["ok"], 700))
    # by level
    ly = y + 214
    out.append(r(x, ly, w, 200, C["raised"], 16, C["border"]))
    out.append(t(x + 16, ly + 30, "நிலைவாரியாக · By level", 14, TA, C["muted"], 600))
    vals = [0.9, 0.8, 0.5, 0.4, 0.2]
    bw = (w - 32 - 4 * 14) / 5
    for i, v in enumerate(vals):
        bx = x + 16 + i * (bw + 14)
        hh = 110 * v
        out.append(r(bx, ly + 160 - hh, bw, hh, C["accent"] if i < 4 else C["lamp"], 6))
        out.append(t(bx + bw / 2, ly + 182, f"L{i + 1}", 12, UI, C["muted"], 600, "middle"))
    my = ly + 218
    out.append(r(x, my, w, 74, C["surface"], 14, C["border"]))
    out.append(t(x + 16, my + 30, "ஒரு எழுத்துக்கு நேரம் (இடைநிலை)", 13.5, TA, C["muted"], 600))
    out.append(t(x + 16, my + 58, "4.2 s", 22, DISP, C["text"], 600) + t(x + 80, my + 58, "median per letter", 12.5,
                                                                         UI, C["muted"], 500))
    out.append(btn(x, my + 90, w, "பின் சோதனை எடு · Take post-test", "ghost"))
    notes = (note(1, NX, 150, ["Pre vs post, same scale", "Two bars, same axis; numbers as 'n / 10'.",
                               "Gain stated in words + colour + sign."], PX + PW - 40, PY + 290)
             + note(2, NX, 270, ["By level (letters_correct_by_level)", "Simple columns L1–L5; label every bar.",
                                 "No dual axes, no 3D, no pie."], PX + PW - 40, PY + 480)
             + note(3, NX, 390, ["Time per letter", "median_seconds_per_letter in Fraunces numerals."],
                    PX + PW - 60, PY + 640)
             + note(4, NX, 490, ["Values here are SAMPLE DATA", "Real numbers only from /api/progress and",
                                 "eval/reports/. Never hard-code a claim."], PX + PW - 60, PY + 180))
    page("04-progress", "Progress · முன்னேற்றம்", phone("".join(out), "முன்னேற்றம்", "Your pre/post gain", 2),
         notes)


def review():
    x, y = PX + 16, PY + 186
    w = PW - 32
    out = [chip(x, y - 6, "நிலுவையில் 3 · 3 pending", C["accent"], C["accent_soft"], 196)]
    yy = y + 32
    items = [("…கோப்[ ]கேசரி…", "பர", "Accepted top candidate", "learner · 2 min ago", C["ok"]),
             ("…ஆண்டு [ ] ஆவது", "இரண்டாவது", "Corrected by user", "guide · 1 h ago", C["lamp_text"]),
             ("…திருவாய்[ ]…", "மொழி", "Corrected by user", "learner · 3 h ago", C["lamp_text"])]
    for i, (ctx, fill, kind, who, kc) in enumerate(items):
        h = 170 if i == 0 else 112
        out.append(r(x, yy, w, h, C["raised"], 16, C["border"]))
        out.append(t(x + 16, yy + 30, ctx, 15, TA_SERIF, C["text"], 500))
        out.append(t(x + 16, yy + 58, "→ " + fill, 17, TA_SERIF, C["accent"], 700))
        out.append(t(x + 16, yy + 84, f"{kind} · {who}", 12.5, UI, kc, 600))
        if i == 0:
            out.append(btn(x + 16, yy + 104, 100, "ஏற்கவும்", "primary", 44)
                       + btn(x + 124, yy + 104, 100, "திருத்து", "ghost", 44)
                       + btn(x + 232, yy + 104, w - 248, "நிராகரி", "ghost", 44))
        yy += h + 12
    out.append(t(x, yy + 18, "Approve / edit / reject → POST /api/queue/{id}", 12, UI, C["faint"], 500))
    notes = (note(1, NX, 150, ["Expert queue (role: expert)", "Context line with the gap, then the",
                               "proposed text in laterite."], PX + PW - 40, PY + 250)
             + note(2, NX, 270, ["Provenance on every item", "Who and when; accepted vs corrected."],
                    PX + 250, PY + 302)
             + note(3, NX, 370, ["Three actions, one primary", "Approve primary; Edit opens an inline field;",
                                 "Reject asks for a reason (optional)."], PX + 200, PY + 345)
             + note(4, NX, 490, ["Keyboard: j/k move, a approve, e edit, r reject", "Desktop shows queue + detail",
                                 "side by side at ≥ 1000 px."]))
    page("05-review", "Review queue · மதிப்பாய்வு", phone("".join(out), "மதிப்பாய்வு", "Expert review queue", 3),
         notes)


def states():
    W, H = 1000, 520
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-label="States"><style>{FONTS}</style><rect width="{W}" height="{H}" fill="#EFE8DA"/>',
           t(40, 34, "States · நிலைகள்", 18, UI, C["text"], 700)]
    cards = [
        ("Empty", "இன்னும் பாடம் இல்லை", "No lessons yet", "நிலையைத் தேர்ந்தெடுங்கள்", C["surface"], C["border"],
         C["muted"], "empty"),
        ("Loading", "கல்லைப் படிக்கிறது…", "Reading the stone…", "skeleton lines, no spinner", C["surface"],
         C["border"], C["muted"], "loading"),
        ("Error", "இணைப்பு தோல்வி", "Could not reach Ezhuthu", "மீண்டும் முயல் · Retry", C["error_soft"],
         C["error"], C["error"], "error"),
        ("Abstain", "வல்லுநர்களுக்கும் உறுதியில்லை", "Experts are unsure", "an honest gap, not a failure",
         C["unsure_soft"], C["unsure"], C["unsure"], "abstain"),
    ]
    cw = 215
    for i, (lab, ta, en, sub, bg, edge, fg, kind) in enumerate(cards):
        x = 40 + i * (cw + 14)
        y = 60
        out.append(t(x, y + 10, lab.upper(), 12, UI, C["faint"], 700))
        out.append(r(x, y + 24, cw, 400, C["bg"], 24, C["border"]))
        out.append(r(x + 14, y + 120, cw - 28, 200, bg, 16, edge, kind in ("abstain", "empty")))
        if kind == "loading":
            for k in range(4):
                out.append(r(x + 30, y + 150 + k * 26, (cw - 60) * (1 - 0.18 * (k % 3)), 12, C["sunk"], 6))
        elif kind == "empty":
            out.append(f'<path d="M{x + cw / 2 - 24} {y + 190}l24 -40l24 40z" fill="none" stroke="{C["lamp"]}" '
                       f'stroke-width="5" stroke-linejoin="round"/>')
        elif kind == "error":
            out.append(f'<circle cx="{x + cw / 2}" cy="{y + 170}" r="20" fill="none" stroke="{C["error"]}" '
                       f'stroke-width="3"/>' + t(x + cw / 2, y + 178, "!", 22, UI, C["error"], 700, "middle"))
        else:
            out.append(t(x + cw / 2, y + 182, "?", 40, DISP, C["unsure"], 600, "middle"))
        out.append(t(x + cw / 2, y + 240 if kind != "loading" else y + 270, ta, 12, TA, C["text"] if kind != "error"
                     else C["error"], 700, "middle"))
        out.append(t(x + cw / 2, y + 262 if kind != "loading" else y + 292, en, 12.5, UI, C["muted"], 500, "middle"))
        out.append(t(x + cw / 2, y + 296 if kind != "loading" else y + 312, sub, 10.5, TA, fg, 600, "middle"))
    out.append("</svg>\n")
    (DESIGN / "ux" / "wireframes" / "06-states.svg").write_text("".join(out))


if __name__ == "__main__":
    learn()
    lesson()
    restore()
    progress()
    review()
    states()
    print("wireframes built")
