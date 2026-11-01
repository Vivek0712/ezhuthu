"""Banners: README hero (light/dark), social preview, OG image, video title cards, Builder Center header.

All text is outlined to paths so the SVGs render identically on GitHub, in <img> and in any browser.
Run: python design/tools/build_banners.py
"""
from __future__ import annotations

import random

from brandkit import (
    BRAHMI,
    FRAUNCES,
    FRAUNCES_I,
    INK,
    LAMP,
    LAMP_LIGHT,
    LATERITE,
    SANS,
    TA_SANS,
    TA_SERIF,
    c,
    p,
    svg,
    text,
    text_w,
    write,
)
from build_logos import tamil_word
from geom import bounds, transform
from vatteluttu import VATTELUTTU

LAT = {"wght": 500, "opsz": 72, "SOFT": 0, "WONK": 0}
LAT_I = {"wght": 400, "opsz": 72, "SOFT": 50, "WONK": 1}

THEME = {
    "light": dict(bg=c("stone", "100"), bg2=c("stone", "200"), ink=INK, muted=c("stone", "700"), faint=c("stone", "600"),
                  accent=LATERITE, lamp=LAMP, lamp_text=c("lamp", "700"), slab=c("stone", "50"),
                  slab_edge=c("stone", "300"), field="#5A4632", field_op=0.075, carve_hi="rgba(255,255,255,.85)",
                  carve_lo="rgba(70,45,20,.28)", unsure=c("neelam", "700"), leaf=c("palm", "100"),
                  grain=".07"),
    "dark": dict(bg=c("granite", "950"), bg2=c("granite", "900"), ink="#F3EADA", muted="#C9BBA3", faint="#A8997F",
                 accent=c("laterite", "300"), lamp=LAMP_LIGHT, lamp_text=c("lamp", "300"), slab=c("granite", "850"),
                 slab_edge=c("granite", "700"), field="#E8DCC6", field_op=0.05, carve_hi="rgba(255,255,255,.06)",
                 carve_lo="rgba(0,0,0,.7)", unsure=c("neelam", "300"), leaf="#30271A", grain=".10"),
}

BRAHMI_SET = [chr(cp) for cp in list(range(0x11005, 0x11013)) + list(range(0x11013, 0x11034)) + [0x11035, 0x11036]]


def defs(t, w, h) -> str:
    return (
        '<defs>'
        f'<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" '
        f'baseFrequency=".9" numOctaves="2" seed="7" stitchTiles="stitch"/><feColorMatrix values="0 0 0 0 .32  '
        f'0 0 0 0 .22  0 0 0 0 .12  0 0 0 {t["grain"]} 0"/></filter>'
        f'<radialGradient id="glow" cx=".82" cy=".25" r=".7"><stop offset="0" stop-color="{t["lamp"]}" '
        f'stop-opacity=".16"/><stop offset="1" stop-color="{t["lamp"]}" stop-opacity="0"/></radialGradient>'
        f'<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".45" stop-color="#fff" stop-opacity=".9"/><stop offset="1" stop-color="#fff"/></linearGradient>'
        f'<mask id="fieldmask"><rect width="{w}" height="{h}" fill="url(#fade)"/></mask>'
        '</defs>'
    )


def background(t, w, h) -> str:
    return (f'<rect width="{w}" height="{h}" fill="{t["bg"]}"/>'
            f'<rect width="{w}" height="{h}" fill="url(#glow)"/>')


def brahmi_field(t, w, h, size=34, seed=3, x0=0) -> str:
    """Faint rows of carved Tamil-Brahmi letters: the 'stone surface' texture."""
    rng = random.Random(seed)
    rows = []
    lh = size * 1.55
    y = size * 1.1
    while y < h + size:
        line = "".join(rng.choice(BRAHMI_SET) + (" " if rng.random() < 0.18 else "") for _ in range(int(w / size) + 6))
        off = rng.uniform(-size, 0)
        rows.append(text(line, BRAHMI, size, x0 + off, y, tracking=0.28))
        y += lh
    d = "".join(rows)
    return (f'<g mask="url(#fieldmask)" opacity="{t["field_op"]}">'
            f'<path d="{d}" fill="{t["field"]}"/></g>')


def wordmark(t, x, y, height) -> tuple[str, tuple]:
    hole, solid, tri, rest = tamil_word()
    x0, y0, x1, y1 = bounds(solid + rest)
    s = height / (y1 - y0)
    tf = lambda d: transform(d, s, s, x - s * x0, y - s * y0)
    body = p(tf(solid), t["ink"]) + p(tf(tri), t["lamp"]) + p(tf(rest), t["ink"])
    return body, (x, y, x + s * (x1 - x0), y + height)


def vat(key, cx, cy, size, color, sw) -> str:
    d = VATTELUTTU[key]["d"]
    s = size / 100
    dd = transform(d, s, s, cx - 50 * s, cy - 50 * s)
    return (f'<path d="{dd}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" '
            f'stroke-linejoin="round"/>')


def ka_row(t, x, cy, cell, gap, letter="ka") -> str:
    """The five-stage evolution of one letter, as small carved tiles joined by a line."""
    v = VATTELUTTU[letter]
    stages = [("b", v["brahmi"], BRAHMI, None), ("v", None, None, None),
              ("g", {"ka": "\U00011315", "e": "\U0001130F", "a": "\U00011305", "ma": "\U0001132E"}[letter], "NotoSansGrantha-Regular.ttf", None),
              ("c", v["tamil"], TA_SERIF, {"wght": 600}), ("m", v["tamil"], TA_SANS, {"wght": 600})]
    out = []
    n = len(stages)
    total = n * cell + (n - 1) * gap
    out.append(f'<path d="M{x + cell / 2} {cy}H{x + total - cell / 2}" stroke="{t["slab_edge"]}" stroke-width="2" '
               f'stroke-dasharray="2 6" stroke-linecap="round"/>')
    for i, (k, ch, font, ax) in enumerate(stages):
        cx = x + i * (cell + gap) + cell / 2
        fill = t["leaf"] if k == "v" else t["slab"]
        out.append(f'<rect x="{cx - cell / 2}" y="{cy - cell / 2}" width="{cell}" height="{cell}" rx="{cell * 0.2}" '
                   f'fill="{fill}" stroke="{t["slab_edge"]}"/>')
        col = t["accent"] if k == "m" else t["ink"]
        if k == "v":
            out.append(vat(letter, cx, cy, cell * 0.62, col, cell * 0.06))
        else:
            d = text(ch, font, 100, 0, 0, ax)
            bx0, by0, bx1, by1 = bounds(d)
            s = cell * 0.56 / max(bx1 - bx0, by1 - by0)
            out.append(p(transform(d, s, s, cx - s * (bx0 + bx1) / 2, cy - s * (by0 + by1) / 2), col))
    return "".join(out)


def inscription_slab(t, x, y, w, h, scale=1.0) -> str:
    """A carved line of Chola-period Tamil with one gap and a proposed fill (illustrative, from the app mock)."""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{16 * scale}" fill="{t["slab"]}" '
           f'stroke="{t["slab_edge"]}"/>']
    size = 30 * scale
    before = "ஸ்வஸ்தி ஸ்ரீ மதிரைகொண்ட கோப்"
    after = "கேசரிவர்மற்கு"
    fill = "பர"
    by = y + h * 0.68
    full = (text_w(before + after, TA_SERIF, size, {"wght": 500}) + text_w(fill, TA_SERIF, size, {"wght": 600})
            + 22 * scale)
    size = min(size, size * (w * 0.88) / full)
    wb = text_w(before, TA_SERIF, size, {"wght": 500})
    wf = text_w(fill, TA_SERIF, size, {"wght": 600})
    wa = text_w(after, TA_SERIF, size, {"wght": 500})
    gap_w = wf + 22 * scale
    total = wb + gap_w + wa
    sx = x + (w - total) / 2
    carve = lambda d, col: (p(transform(d, 1, 1, 0, 1.2 * scale), t["carve_hi"]) + p(d, col))
    out.append(carve(text(before, TA_SERIF, size, sx, by, {"wght": 500}), t["ink"]))
    gx = sx + wb + 4 * scale
    out.append(f'<rect x="{gx}" y="{by - size * 0.98}" width="{gap_w - 8 * scale}" height="{size * 1.32}" '
               f'rx="{8 * scale}" fill="{t["lamp"]}" fill-opacity=".14" stroke="{t["lamp"]}" stroke-width="{1.6 * scale}" '
               f'stroke-dasharray="{5 * scale} {4 * scale}"/>')
    out.append(p(text(fill, TA_SERIF, size, gx + (gap_w - 8 * scale) / 2, by, {"wght": 600}, anchor="middle"),
                 t["lamp_text"]))
    out.append(carve(text(after, TA_SERIF, size, sx + wb + gap_w, by, {"wght": 500}), t["ink"]))
    # annotation above the gap
    ax = gx + (gap_w - 8 * scale) / 2
    ay = y + h * 0.2
    out.append(f'<path d="M{ax} {by - size * 1.02}V{ay + 10 * scale}" stroke="{t["lamp"]}" stroke-width="{1.4 * scale}"/>')
    out.append(f'<circle cx="{ax}" cy="{ay + 10 * scale}" r="{3 * scale}" fill="{t["lamp"]}"/>')
    lab = "proposed fill · முன்மொழிவு"
    lw = text_w(lab, SANS, 13 * scale, {"wght": 600})
    if ax + 10 * scale + lw > x + w - 16 * scale:
        out.append(p(text(lab, SANS, 13 * scale, ax - 10 * scale, ay + 14 * scale, {"wght": 600}, anchor="end"),
                     t["lamp_text"]))
    else:
        out.append(p(text(lab, SANS, 13 * scale, ax + 10 * scale, ay + 14 * scale, {"wght": 600}), t["lamp_text"]))
    return "".join(out)


def readme_hero(theme: str) -> str:
    t = THEME[theme]
    W, H = 1280, 400
    out = [defs(t, W, H), background(t, W, H), brahmi_field(t, W, H, 30, x0=380)]
    wm, (wx0, wy0, wx1, wy1) = wordmark(t, 72, 92, 92)
    out.append(wm)
    out.append(p(text("EZHUTHU", SANS, 14, 76, wy1 + 34, {"wght": 650}, tracking=0.42), t["accent"]))
    out.append(f'<path d="M{76 + text_w("EZHUTHU", SANS, 14, {"wght": 650}, 0.42) + 16} {wy1 + 29}h56" '
               f'stroke="{t["accent"]}" stroke-width="1.5"/>')
    out.append(p(text("Learn to read 2,000 years of Tamil", FRAUNCES, 30, 72, wy1 + 88, LAT), t["ink"]))
    out.append(p(text("inscriptions, ", FRAUNCES, 30, 72, wy1 + 126, LAT)
                 + text("in Tamil.", FRAUNCES_I, 30, 72 + text_w("inscriptions, ", FRAUNCES, 30, LAT), wy1 + 126,
                        LAT_I), t["ink"]))
    out.append(p(text("உங்கள் ஊர்க் கோயில் கல்வெட்டை நீங்களே படியுங்கள்.", TA_SANS, 16, 72, wy1 + 162,
                      {"wght": 500}), t["muted"]))
    # right: slab + evolution row
    out.append(inscription_slab(t, 690, 70, 520, 150))
    out.append(ka_row(t, 760, 300, 64, 18))
    out.append(p(text("க · ka, from Tamil-Brahmi to today", SANS, 13, 760 + (5 * 64 + 4 * 18) / 2, 360,
                      {"wght": 500}, anchor="middle"), t["faint"]))
    return svg(W, H, "".join(out), "Ezhuthu · எழுத்து",
               "Ezhuthu: learn to read 2,000 years of Tamil inscriptions, in Tamil.")


def social(theme: str, W=1280, H=640, foot=True) -> str:
    t = THEME[theme]
    out = [defs(t, W, H), background(t, W, H), brahmi_field(t, W, H, 34, seed=11, x0=0)]
    # wordmark centred
    hole, solid, tri, rest = tamil_word()
    x0, y0, x1, y1 = bounds(solid + rest)
    wh = H * 0.19
    s = wh / (y1 - y0)
    ww = s * (x1 - x0)
    wx, wy = (W - ww) / 2, H * 0.17
    tf = lambda d: transform(d, s, s, wx - s * x0, wy - s * y0)
    out.append(p(tf(solid), t["ink"]) + p(tf(tri), t["lamp"]) + p(tf(rest), t["ink"]))
    ty = wy + wh + H * 0.11
    fs = H * 0.052
    l1 = "Learn to read 2,000 years of Tamil inscriptions, "
    l2 = "in Tamil."
    w1 = text_w(l1, FRAUNCES, fs, LAT)
    w2 = text_w(l2, FRAUNCES_I, fs, LAT_I)
    sx = (W - w1 - w2) / 2
    out.append(p(text(l1, FRAUNCES, fs, sx, ty, LAT) + text(l2, FRAUNCES_I, fs, sx + w1, ty, LAT_I), t["ink"]))
    out.append(p(text("2,000 ஆண்டுத் தமிழ்க் கல்வெட்டுகளைத் தமிழிலேயே படிக்கக் கற்றுக்கொள்ளுங்கள்.", TA_SANS,
                      H * 0.03, W / 2, ty + H * 0.07, {"wght": 500}, anchor="middle"), t["muted"]))
    cell = H * 0.12
    gap = cell * 0.3
    total = 5 * cell + 4 * gap
    out.append(ka_row(t, (W - total) / 2, ty + H * 0.2, cell, gap, letter="e"))
    if foot:
        foot_t = "Built with Strands Agents  ·  Amazon Bedrock AgentCore  ·  Inscription texts: DHARMA, CC BY-SA 4.0"
        out.append(p(text(foot_t, SANS, H * 0.022, W / 2, H - H * 0.055, {"wght": 500}, anchor="middle"), t["faint"]))
    return svg(W, H, "".join(out), "Ezhuthu · எழுத்து",
               "Ezhuthu: an AI tutor for reading Tamil inscriptions, built with Strands Agents.")


def video_card(theme: str, kicker_ta: str, kicker_en: str, title_ta: str, title_en: str, foot: str,
               num: str | None = None) -> str:
    t = THEME[theme]
    W, H = 1920, 1080
    out = [defs(t, W, H), background(t, W, H), brahmi_field(t, W, H, 46, seed=sum(map(ord, title_en)) % 97, x0=700)]
    x = 140
    # small lockup top-left
    wm, _ = wordmark(t, x, 110, 58)
    out.append(wm)
    if num:
        out.append(p(text(num, FRAUNCES, 300, W - 140, 980, {"wght": 300, "opsz": 144}, anchor="end"), t["lamp"]))
    out.append(p(text(kicker_en.upper(), SANS, 26, x, 470, {"wght": 650}, tracking=0.2), t["accent"]))
    out.append(p(text(kicker_ta, TA_SANS, 26, x, 520, {"wght": 600}), t["accent"]))
    out.append(p(text(title_ta, TA_SERIF, 84, x, 660, {"wght": 700}), t["ink"]))
    out.append(p(text(title_en, FRAUNCES, 58, x, 760, LAT), t["muted"]))
    out.append(f'<path d="M{x} 880h120" stroke="{t["lamp"]}" stroke-width="4" stroke-linecap="round"/>')
    out.append(p(text(foot, SANS, 24, x, 940, {"wght": 500}), t["faint"]))
    return svg(W, H, "".join(out), title_en, f"{kicker_en}: {title_en}")


def video_title(theme: str) -> str:
    t = THEME[theme]
    W, H = 1920, 1080
    out = [defs(t, W, H), background(t, W, H), brahmi_field(t, W, H, 46, seed=5, x0=0)]
    hole, solid, tri, rest = tamil_word()
    x0, y0, x1, y1 = bounds(solid + rest)
    wh = 240
    s = wh / (y1 - y0)
    ww = s * (x1 - x0)
    wx, wy = (W - ww) / 2, 250
    tf = lambda d: transform(d, s, s, wx - s * x0, wy - s * y0)
    out.append(p(tf(solid), t["ink"]) + p(tf(tri), t["lamp"]) + p(tf(rest), t["ink"]))
    out.append(p(text("EZHUTHU", SANS, 30, W / 2, wy + wh + 80, {"wght": 650}, anchor="middle", tracking=0.5),
                 t["accent"]))
    l1, l2 = "An AI tutor for 2,000 years of Tamil inscriptions, ", "in Tamil."
    w1 = text_w(l1, FRAUNCES, 52, LAT)
    w2 = text_w(l2, FRAUNCES_I, 52, LAT_I)
    out.append(p(text(l1, FRAUNCES, 52, (W - w1 - w2) / 2, wy + wh + 190, LAT)
                 + text(l2, FRAUNCES_I, 52, (W - w1 - w2) / 2 + w1, wy + wh + 190, LAT_I), t["ink"]))
    out.append(p(text("Education track  ·  Built with Strands Agents  ·  Amazon Bedrock AgentCore", SANS, 26, W / 2,
                      H - 90, {"wght": 500}, anchor="middle"), t["faint"]))
    return svg(W, H, "".join(out), "Ezhuthu title card", "Hackathon video title card.")


def builder_header(theme: str) -> str:
    t = THEME[theme]
    W, H = 1600, 900
    out = [defs(t, W, H), background(t, W, H), brahmi_field(t, W, H, 40, seed=21, x0=500)]
    wm, (_, _, _, wy1) = wordmark(t, 110, 120, 80)
    out.append(wm)
    out.append(p(text("Teaching 2,000 years of Tamil", FRAUNCES, 64, 110, 400, LAT), t["ink"]))
    out.append(p(text("inscriptions with ", FRAUNCES, 64, 110, 480, LAT)
                 + text("Strands Agents", FRAUNCES_I, 64, 110 + text_w("inscriptions with ", FRAUNCES, 64, LAT), 480,
                        LAT_I), t["ink"]))
    out.append(p(text("A restoration engine that abstains when experts would, and a tutor that teaches in Tamil.",
                      SANS, 24, 110, 550, {"wght": 450}), t["muted"]))
    out.append(inscription_slab(t, 110, 620, 760, 180, 1.25))
    out.append(ka_row(t, 1010, 710, 92, 22, letter="ka"))
    out.append(p(text("Built with Strands Agents · Amazon Bedrock AgentCore · DHARMA texts, CC BY-SA 4.0", SANS, 18,
                      W - 110, H - 50, {"wght": 500}, anchor="end"), t["faint"]))
    return svg(W, H, "".join(out), "Ezhuthu article header", "Builder Center article header.")


CARDS = [
    ("01-problem", "சிக்கல்", "The problem", "கோயில் சுவரை யாரால் படிக்க முடியும்?",
     "Who can still read the temple wall?", "Most learners cannot read the inscriptions in their own villages.", "1"),
    ("02-how", "எப்படி வேலை செய்கிறது", "How it works", "ஒரு கல்வெட்டு, ஐந்து நிலைகள்",
     "One inscription, five levels", "Modern Tamil → Chola → Pallava → Vatteluttu → Tamil-Brahmi", "2"),
    ("03-restore", "மீட்டமைப்பு", "Restoration", "உறுதியில்லாதபோது, சொல்கிறது",
     "When it is unsure, it says so", "Calibrated fills, and an honest abstain: “experts are unsure”.", "3"),
    ("04-results", "அளவீடு", "Measured gain", "முன் சோதனை, பின் சோதனை",
     "Pre-test, post-test", "Every number on screen comes from eval/reports/.", "4"),
    ("05-credits", "நன்றி", "Credits", "எழுத்து · Ezhuthu",
     "Built with Strands Agents", "Amazon Bedrock AgentCore · Inscription texts from DHARMA (CC BY-SA 4.0)", None),
]


def main():
    for th in THEME:
        write(f"brand/banners/readme-hero-{th}.svg", readme_hero(th))
        write(f"brand/banners/social-preview-{th}.svg", social(th))
    write("brand/banners/og-image.svg", social("light", 1200, 630))
    write("brand/banners/video/00-title-dark.svg", video_title("dark"))
    write("brand/banners/video/00-title-light.svg", video_title("light"))
    for slug, kta, ken, tta, ten, foot, num in CARDS:
        write(f"brand/banners/video/{slug}.svg", video_card("dark", kta, ken, tta, ten, foot, num))
    write("brand/banners/builder-center-header.svg", builder_header("light"))
    print("banners built")


if __name__ == "__main__":
    main()
