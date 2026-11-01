"""Era glyph art: per-letter Vatteluttu SVGs, glyphs.json for the app, and the evolution strip.

Run: python design/tools/build_glyphs.py
"""
from __future__ import annotations

import json

from brandkit import (
    BRAHMI,
    FRAUNCES,
    GRANTHA,
    INK,
    LAMP,
    LAMP_LIGHT,
    LATERITE,
    SANS,
    STONE_50,
    TA_SANS,
    TA_SERIF,
    c,
    p,
    svg,
    text,
    text_w,
    write,
)
from geom import bounds, transform
from outline import path
from vatteluttu import STROKE, VATTELUTTU, iso, svg_for

LETTERS = ["a", "ka", "ma", "e", "lla"]
STAGES = [
    # key, Tamil name, English name, period, font
    ("brahmi", "தமிழ்-பிராமி", "Tamil-Brahmi", "c. 3rd c. BCE onward", BRAHMI),
    ("vatteluttu", "வட்டெழுத்து", "Vatteluttu", "c. 6th–11th c. CE", None),
    ("grantha", "பல்லவ-கிரந்தம்", "Grantha / Pallava", "c. 6th–9th c. CE", GRANTHA),
    ("chola", "சோழர் தமிழ்", "Chola Tamil", "c. 9th–13th c. CE", TA_SERIF),
    ("modern", "இன்றைய தமிழ்", "Modern Tamil", "today", TA_SANS),
]
GRANTHA_CP = {"a": "\U00011305", "ka": "\U00011315", "ma": "\U0001132E", "e": "\U0001130F", "lla": None}

THEMES = {
    "light": dict(bg=c("stone", "100"), cell=STONE_50, cell_edge=c("stone", "300"), ink=INK,
                  muted=c("stone", "700"), faint=c("stone", "600"), accent=LATERITE, lamp=LAMP,
                  carve_lo="rgba(60,40,20,.20)", carve_hi="rgba(255,255,255,.9)", leaf=c("palm", "100")),
    "dark": dict(bg=c("granite", "950"), cell=c("granite", "900"), cell_edge=c("granite", "700"), ink="#F3EADA",
                 muted="#C9BBA3", faint="#A8997F", accent=c("laterite", "300"), lamp=LAMP_LIGHT,
                 carve_lo="rgba(0,0,0,.6)", carve_hi="rgba(255,255,255,.05)", leaf="#30271A"),
}


def glyph_paths(stage: str, letter: str, font):
    """Return ('fill', d) for font glyphs or ('stroke', d) for drawn Vatteluttu; None if absent."""
    v = VATTELUTTU[letter]
    if stage == "vatteluttu":
        return "stroke", v["d"]
    if stage == "brahmi":
        ch = v["brahmi"]
    elif stage == "grantha":
        ch = GRANTHA_CP[letter]
        if ch is None:
            return None
    else:
        ch = v["tamil"]
    axes = {"wght": 600} if stage == "chola" else ({"wght": 500} if stage == "modern" else None)
    d, _ = path(ch, font, 100, 0, 0, axes)
    return "fill", d


def fit_into(d: str, cx: float, cy: float, box: float, stroke_pad: float = 0.0):
    x0, y0, x1, y1 = bounds(d)
    w, h = x1 - x0 + stroke_pad, y1 - y0 + stroke_pad
    s = box / max(w, h)
    return transform(d, s, s, cx - s * (x0 + x1) / 2, cy - s * (y0 + y1) / 2), s


def strip(theme: str) -> str:
    t = THEMES[theme]
    W, H = 1440, 940
    left, top = 196, 236
    cw, rh = 240, 118
    gx = 14
    out = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>']
    out.append(f'<defs><filter id="carve" x="-5%" y="-5%" width="110%" height="110%">'
               f'<feDropShadow dx="0" dy="1.2" stdDeviation="0.6" flood-color="{t["carve_hi"]}"/></filter></defs>')
    # title
    out.append(p(text("ஒரே எழுத்து, இரண்டாயிரம் ஆண்டுகள்", TA_SERIF, 30, 56, 70, {"wght": 700}), t["ink"]))
    out.append(p(text("One letter, two thousand years. Read left to right, oldest to newest.", SANS, 17, 56, 104,
                      {"wght": 450}), t["muted"]))
    # timeline axis
    ax_y = 182
    out.append(f'<path d="M{left} {ax_y}H{left + cw * 5 - gx}" stroke="{t["cell_edge"]}" stroke-width="2"/>')
    out.append(f'<path d="M{left + cw * 5 - gx - 10} {ax_y - 6}l10 6l-10 6" fill="none" stroke="{t["cell_edge"]}" '
               f'stroke-width="2" stroke-linejoin="round"/>')
    for i, (key, ta, en, period, font) in enumerate(STAGES):
        x = left + i * cw
        cx = x + (cw - gx) / 2
        out.append(f'<circle cx="{cx}" cy="{ax_y}" r="5" fill="{t["lamp"] if i == 0 else t["accent"]}"/>')
        out.append(p(text(ta, TA_SANS, 15, cx, ax_y - 34, {"wght": 600}, anchor="middle"), t["ink"]))
        out.append(p(text(en.upper(), SANS, 11, cx, ax_y - 16, {"wght": 650}, anchor="middle", tracking=0.12),
                     t["accent"]))
        out.append(p(text(period, SANS, 13, cx, ax_y + 28, {"wght": 450}, anchor="middle"), t["faint"]))
    # rows
    for r, letter in enumerate(LETTERS):
        y = top + r * rh
        cy = y + (rh - 12) / 2
        v = VATTELUTTU[letter]
        out.append(p(text(v["tamil"], TA_SANS, 40, 64, cy + 14, {"wght": 600}), t["ink"]))
        out.append(p(text(iso(letter), FRAUNCES, 20, 120, cy + 8, {"wght": 400, "opsz": 24}), t["muted"]))
        for i, (key, ta, en, period, font) in enumerate(STAGES):
            x = left + i * cw
            w = cw - gx
            hh = rh - 12
            cx = x + w / 2
            fill = t["leaf"] if key == "vatteluttu" else t["cell"]
            out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hh}" rx="14" fill="{fill}" '
                       f'stroke="{t["cell_edge"]}"/>')
            g = glyph_paths(key, letter, font)
            if g is None:
                out.append(p(text("Grantha has no ḻa", SANS, 13, cx, cy + 5, {"wght": 500}, anchor="middle"),
                             t["faint"]))
                out.append(f'<path d="M{cx - 18} {cy - 18}h36" stroke="{t["cell_edge"]}" stroke-width="2"/>')
                continue
            kind, d = g
            if kind == "stroke":
                dd, s = fit_into(d, cx, cy, 70, STROKE)
                sw = 8.6 / s * s  # visual stroke ~8.6px to match the Noto stems at this size
                out.append(f'<path d="{dd}" fill="none" stroke="{t["ink"]}" stroke-width="{sw:.1f}" '
                           f'stroke-linecap="round" stroke-linejoin="round" filter="url(#carve)"/>')
            else:
                dd, _ = fit_into(d, cx, cy, 70)
                col = t["accent"] if key == "modern" else t["ink"]
                out.append(f'<path d="{dd}" fill="{col}" filter="url(#carve)"/>')
    # notes
    ny = top + len(LETTERS) * rh + 26
    notes = [
        "Tamil-Brahmi, Grantha and Tamil use Noto fonts (SIL OFL). Vatteluttu has no Unicode, so it is drawn by hand "
        "after published charts (design/glyphs/REFERENCES.md);",
        "those drawings are teaching shapes pending an epigrapher's review. The Pallava stage is shown with Unicode "
        "Grantha. In Chola inscriptions எ also served for ē;",
        "the எ / ஏ distinction is an 18th-century reform. ḻa (ழ) is a Tamil letter: Tamil-Brahmi has it, Grantha, "
        "made for Sanskrit, does not.",
    ]
    for i, line in enumerate(notes):
        out.append(p(text(line, SANS, 14, 56, ny + i * 22, {"wght": 420}), t["faint"]))
    out.append(p(text("எழுத்து · Ezhuthu", TA_SANS, 14, W - 56, ny + 44, {"wght": 600}, anchor="end"), t["accent"]))
    _ = text_w
    return svg(W, H, "".join(out), "Evolution of five Tamil letters",
               "The letters a, ka, ma, e and ḻa in Tamil-Brahmi, Vatteluttu, Grantha/Pallava, Chola and modern Tamil.")


def card(theme: str) -> str:
    """Glyph-card component reference (one card, annotated), used by UX.md."""
    t = THEMES[theme]
    W, H = 360, 420
    out = [f'<rect width="{W}" height="{H}" fill="{t["bg"]}"/>']
    x, y, w, h = 30, 30, 300, 360
    out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{t["cell"]}" stroke="{t["cell_edge"]}"/>')
    out.append(f'<rect x="{x + 18}" y="{y + 18}" width="{w - 36}" height="200" rx="12" fill="{t["leaf"]}"/>')
    d, _ = fit_into(VATTELUTTU["ka"]["d"], x + w / 2, y + 118, 120, STROKE)
    out.append(f'<path d="{d}" fill="none" stroke="{t["ink"]}" stroke-width="10" stroke-linecap="round" '
               f'stroke-linejoin="round"/>')
    out.append(p(text("L4 · வட்டெழுத்து", TA_SANS, 13, x + 26, y + 42, {"wght": 600}), t["accent"]))
    out.append(p(text("க", TA_SANS, 34, x + 22, y + 270, {"wght": 600}), t["ink"]))
    out.append(p(text("ka", FRAUNCES, 22, x + 70, y + 266, {"wght": 400, "opsz": 24}), t["muted"]))
    out.append(p(text("c. 6th–11th c. CE · drawn glyph", SANS, 13, x + 22, y + 300, {"wght": 450}), t["faint"]))
    out.append(f'<rect x="{x + 22}" y="{y + 318}" width="122" height="26" rx="13" fill="none" '
               f'stroke="{t["cell_edge"]}"/>')
    out.append(p(text("Hear it · கேள்", TA_SANS, 12, x + 83, y + 336, {"wght": 600}, anchor="middle"), t["ink"]))
    return svg(W, H, "".join(out), "Glyph card", "A glyph card: script sample, Tamil letter, ISO value, era.")


def main():
    for k in VATTELUTTU:
        write(f"glyphs/vatteluttu/{k}.svg", svg_for(k))
    data = {
        "$comment": "Vatteluttu teaching glyphs. Centre-line paths on a 100x100 grid; stroke with round caps/joins, "
                    "width 'stroke'. Keys are ISO-15919 (the API's glyph_svg is 'vatteluttu:<iso>'). "
                    "Pending epigrapher review; see design/glyphs/REFERENCES.md.",
        "stroke": STROKE,
        "viewBox": "0 0 100 100",
        "glyphs": {iso(k): {"tamil": v["tamil"], "brahmi": v["brahmi"], "d": v["d"]} for k, v in VATTELUTTU.items()},
    }
    write("glyphs/vatteluttu.json", json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    for th in THEMES:
        write(f"glyphs/evolution-strip-{th}.svg", strip(th))
        write(f"glyphs/glyph-card-{th}.svg", card(th))
    print("glyphs built")


if __name__ == "__main__":
    main()
