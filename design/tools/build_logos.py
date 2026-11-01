"""Build the logo system (mark, wordmarks, lockups) and icon sources as pure-path SVGs.

Run: python design/tools/build_logos.py  (needs fonttools, uharfbuzz, skia-pathops; see design/README.md)
"""
from __future__ import annotations

from brandkit import (
    FRAUNCES,
    GRANITE,
    INK,
    LAMP,
    LAMP_LIGHT,
    LATERITE,
    LATERITE_DEEP,
    STONE_50,
    STONE_600,
    TA_SERIF,
    c,
    mark_e,
    p,
    place,
    svg,
    text,
    write,
)
from geom import bounds, transform
from outline import shape

WM_WEIGHT = 800
LATIN_AXES = {"wght": 540, "opsz": 144, "SOFT": 0, "WONK": 0}

# Colourways: (letter, triangle, knockout?) ; knockout means the triangle is cut out of the letter.
WAYS = {
    "color": (LATERITE, LAMP, False),
    "ink": (INK, LAMP, False),
    "mono": (INK, None, True),
    "reversed": (STONE_50, LAMP_LIGHT, False),
    "reversed-mono": (STONE_50, None, True),
}
WORD_WAYS = {
    "color": (INK, LAMP, False),
    "mono": (INK, None, True),
    "reversed": (STONE_50, LAMP_LIGHT, False),
    "reversed-mono": (STONE_50, None, True),
}


def mark_paths(weight: int, size: float = 100.0, x: float = 0, y: float = 0):
    hole, solid, t = mark_e(weight, size)
    return [transform(d, 1, 1, x, y) for d in (hole, solid, t)]


def paint(hole: str, solid: str, t: str, letter: str, tri_fill: str | None, knock: bool) -> str:
    if knock or tri_fill is None:
        return p(hole, letter)
    return p(solid, letter) + p(t, tri_fill)


def tamil_word(weight: int = WM_WEIGHT, size: float = 100.0):
    """Returns (hole, solid, tri, rest) for எழுத்து with the mark e, baseline 0, x from 0."""
    hole, solid, t = mark_paths(weight, size)
    _, adv, _ = shape("எ", TA_SERIF, size, {"wght": weight})
    rest = text("ழுத்து", TA_SERIF, size, adv, 0, {"wght": weight})
    return hole, solid, t, rest


def boxed(parts: list[str], pad: float):
    xs = [bounds(d) for d in parts]
    x0 = min(b[0] for b in xs) - pad
    y0 = min(b[1] for b in xs) - pad
    x1 = max(b[2] for b in xs) + pad
    y1 = max(b[3] for b in xs) + pad
    return x0, y0, x1 - x0, y1 - y0


def emit(name: str, body: str, box, title: str, desc: str, scale: float = 1.0):
    x0, y0, w, h = box
    write(f"brand/logo/{name}.svg",
          svg(round(w * scale), round(h * scale), body, title, desc, vb=f"{x0:.1f} {y0:.1f} {w:.1f} {h:.1f}"))


def build_mark():
    hole, solid, t = mark_paths(900)
    x0, y0, x1, y1 = bounds(solid)
    bowl_h = 34.4  # bowl height at size 100, the clear-space unit "b"
    pad = bowl_h * 0.5
    box = (x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad)
    for way, (letter, tri_fill, knock) in WAYS.items():
        emit(f"mark-{way}", paint(hole, solid, t, letter, tri_fill, knock), box,
             "Ezhuthu mark", "The Tamil letter e (எ) holding its ancestor, Tamil-Brahmi e (a triangle).", 2.4)


def build_wordmark_ta():
    hole, solid, t, rest = tamil_word()
    box = boxed([solid, rest], 14)
    for way, (letter, tri_fill, knock) in WORD_WAYS.items():
        emit(f"wordmark-ta-{way}", paint(hole, solid, t, letter, tri_fill, knock) + p(rest, letter), box,
             "எழுத்து", "Ezhuthu Tamil wordmark: the first letter carries the Tamil-Brahmi e.", 1.6)


def build_wordmark_en():
    # Mark at cap height, then Ezhuthu in Fraunces.
    size = 100
    lat = text("Ezhuthu", FRAUNCES, size, 0, 0, LATIN_AXES)
    lx0, ly0, lx1, ly1 = bounds(lat)
    cap = -ly0  # cap height ~ ink top of E (h ascender slightly taller)
    hole, solid, t = mark_paths(900)
    (h2, s2, t2), sc = place([hole, solid, t], 0, 0, 0, ref=solid, h=cap * 0.64)
    mx0, my0, mx1, my1 = bounds(s2)
    shift_y = -my1 + 0  # sit on baseline
    gap = cap * 0.32
    h2, s2, t2 = (transform(d, 1, 1, -mx0, shift_y) for d in (h2, s2, t2))
    mw = mx1 - mx0
    lat = text("Ezhuthu", FRAUNCES, size, mw + gap, 0, LATIN_AXES)
    box = boxed([s2, lat], 14)
    for way, (letter, tri_fill, knock) in WAYS.items():
        if way == "ink":
            continue
        word = INK if way in ("color", "mono") else STONE_50
        emit(f"wordmark-en-{way}", paint(h2, s2, t2, letter, tri_fill, knock) + p(lat, word), box,
             "Ezhuthu", "Ezhuthu Latin wordmark with the mark.", 1.4)


def build_lockups():
    hole, solid, t, rest = tamil_word()
    ta_box = boxed([solid, rest], 0)
    ta_h = ta_box[3]
    # Horizontal: Tamil wordmark | rule | Ezhuthu
    x_end = ta_box[0] + ta_box[2]
    gap = 34
    rule_x = x_end + gap
    lat_size = 74
    lat = text("Ezhuthu", FRAUNCES, lat_size, rule_x + gap, 0, LATIN_AXES)
    rule_top, rule_bot = -ta_h * 0.62, 6
    rule = f"M{rule_x - 1.5:.1f} {rule_top:.1f}H{rule_x + 1.5:.1f}V{rule_bot:.1f}H{rule_x - 1.5:.1f}Z"
    box = boxed([solid, rest, lat, rule], 16)
    for way, (letter, tri_fill, knock) in WORD_WAYS.items():
        rule_c = LAMP if way == "color" else (LAMP_LIGHT if way == "reversed" else letter)
        emit(f"lockup-horizontal-{way}",
             paint(hole, solid, t, letter, tri_fill, knock) + p(rest, letter) + p(rule, rule_c) + p(lat, letter),
             box, "எழுத்து · Ezhuthu", "Ezhuthu bilingual horizontal lockup.", 1.0)
    # Stacked: Tamil wordmark over spaced Latin, centred
    cx = ta_box[0] + ta_box[2] / 2
    lat2 = text("EZHUTHU", "InstrumentSans.ttf", 30, cx, ta_box[1] + ta_h + 46, {"wght": 600, "wdth": 100},
                anchor="middle", tracking=0.42)
    lb = bounds(lat2)
    dash_y = (lb[1] + lb[3]) / 2
    dl = f"M{lb[0] - 46:.1f} {dash_y - 1.2:.1f}h30v2.4h-30Z"
    dr = f"M{lb[2] + 16:.1f} {dash_y - 1.2:.1f}h30v2.4h-30Z"
    box = boxed([solid, rest, lat2, dl, dr], 18)
    for way, (letter, tri_fill, knock) in WORD_WAYS.items():
        sub = STONE_600 if way == "color" else letter
        if way == "reversed":
            sub = c("stone", "300")
        acc = LAMP if way == "color" else (LAMP_LIGHT if way == "reversed" else letter)
        emit(f"lockup-stacked-{way}",
             paint(hole, solid, t, letter, tri_fill, knock) + p(rest, letter) + p(lat2, sub) + p(dl, acc) + p(dr, acc),
             box, "எழுத்து · Ezhuthu", "Ezhuthu bilingual stacked lockup.", 1.0)


def tile(size: float, radius_ratio: float, glyph_w_ratio: float, full_bleed: bool = False, flat: bool = False,
         knock: bool = False, plain: bool = False) -> str:
    """App icon / favicon artwork on a laterite tile."""
    s = size
    r = 0 if full_bleed else s * radius_ratio
    hole, solid, t = mark_paths(900)
    (h2, s2, t2), _ = place([hole, solid, t], 0, 0, s * glyph_w_ratio, ref=solid, cx=s / 2, cy=s * 0.515)
    defs = ""
    bg = LATERITE
    if not flat:
        defs = (f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="{c("laterite", "500")}"/><stop offset="1" stop-color="{LATERITE_DEEP}"/>'
                f'</linearGradient></defs>')
        bg = "url(#g)"
    rim = "" if flat or full_bleed else (
        f'<rect x="{s * 0.012:.2f}" y="{s * 0.012:.2f}" width="{s * 0.976:.2f}" height="{s * 0.976:.2f}" '
        f'rx="{r * 0.97:.2f}" fill="none" stroke="#fff" stroke-opacity=".14" stroke-width="{s * 0.008:.2f}"/>')
    return (defs + f'<rect width="{s:g}" height="{s:g}" rx="{r:.2f}" fill="{bg}"/>' + rim
            + (p(s2, STONE_50) if plain else p(h2, STONE_50) if knock else p(s2, STONE_50) + p(t2, LAMP)))


def build_icons():
    write("brand/icons/favicon.svg", svg(64, 64, tile(64, 0.22, 0.80, flat=True, knock=True), "Ezhuthu"))
    write("brand/icons/icon.svg", svg(512, 512, tile(512, 0.22, 0.66), "Ezhuthu"))
    write("brand/icons/icon-maskable.svg", svg(512, 512, tile(512, 0, 0.50, full_bleed=True), "Ezhuthu"))
    write("brand/icons/apple-touch-icon.svg", svg(180, 180, tile(180, 0, 0.62, full_bleed=True), "Ezhuthu"))
    # small sizes are flat and larger-glyph for legibility
    write("brand/icons/favicon-16.svg", svg(16, 16, tile(16, 0.2, 0.9, flat=True, plain=True), "Ezhuthu"))


def build_clearspace():
    """Construction sheet: clear space (b = bowl height) and minimum sizes."""
    hole, solid, t, rest = tamil_word()
    x0, y0, x1, y1 = bounds(solid)
    bx0, by0, bw, bh = boxed([solid, rest], 0)
    b = 34.4 * 0.8  # bowl height of the 800-weight letter at size 100
    W, H = 900, 380
    (mh, ms, mt), _ = place([hole, solid, t], 0, 0, 120, ref=solid, cx=150, cy=170)
    mb = bounds(ms)
    unit = (mb[3] - mb[1]) * 0.6
    guides = []

    def rect(x, y, w, h, dash=True):
        da = ' stroke-dasharray="4 4"' if dash else ""
        return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="none" stroke="{LAMP}" '
                f'stroke-width="1.2"{da}/>')

    guides.append(rect(mb[0] - unit, mb[1] - unit, mb[2] - mb[0] + 2 * unit, mb[3] - mb[1] + 2 * unit))
    guides.append(rect(mb[0], mb[1], mb[2] - mb[0], mb[3] - mb[1], dash=False))
    # b marker
    guides.append(f'<path d="M{mb[0] - unit:.1f} {mb[3] + 26:.1f}h{unit:.1f}" stroke="{LATERITE}" stroke-width="2"/>')
    lab = text("b", FRAUNCES, 20, mb[0] - unit / 2, mb[3] + 50, {"wght": 500, "opsz": 24}, anchor="middle")
    notes = [
        (150, 330, "Mark · min 16 px"),
        (600, 330, "Tamil wordmark · min 96 px wide"),
        (450, 40, "Clear space on every side = b, the height of the bowl of எ"),
    ]
    lab += "".join(text(s_, "InstrumentSans.ttf", 19, x_, y_, {"wght": 500}, anchor="middle") for x_, y_, s_ in notes)
    # wordmark with clear space
    wb0 = boxed([solid, rest], 0)
    k = 430 / wb0[2]
    dx, dy = 600 - k * (wb0[0] + wb0[2] / 2), 170 - k * (wb0[1] + wb0[3] / 2)
    wh, ws, wt, wr = (transform(d, k, k, dx, dy) for d in (hole, solid, t, rest))
    wb = boxed([ws, wr], 0)
    u2 = unit * 0.9
    guides.append(rect(wb[0] - u2, wb[1] - u2, wb[2] + 2 * u2, wb[3] + 2 * u2))
    body = (f'<rect width="{W}" height="{H}" fill="{c("stone", "50")}"/>'
            + "".join(guides) + p(ms, LATERITE) + p(mt, LAMP) + p(lab, LATERITE)
            + p(ws, INK) + p(wt, LAMP) + p(wr, INK))
    write("brand/logo/construction.svg", svg(W, H, body, "Clear space", "Clear space equals b, the bowl height."))
    _ = (x0, y0, x1, y1, bx0, by0, bw, bh, b, GRANITE)


if __name__ == "__main__":
    build_mark()
    build_wordmark_ta()
    build_wordmark_en()
    build_lockups()
    build_icons()
    build_clearspace()
    print("logos + icons built")
