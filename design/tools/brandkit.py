"""Shared brand geometry: the Ezhuthu mark, wordmarks, colours and SVG writing helpers."""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from geom import bounds, clean, difference, transform
from outline import path

DESIGN = Path(__file__).resolve().parents[1]
_TOK = json.loads((DESIGN / "tokens" / "tokens.json").read_text())


def c(fam: str, shade: str) -> str:
    return _TOK["color"][fam][shade]["$value"]


LATERITE = c("laterite", "600")
LATERITE_DEEP = c("laterite", "700")
LAMP = c("lamp", "500")
LAMP_LIGHT = c("lamp", "400")
INK = c("ink", "900")
STONE_50 = c("stone", "50")
STONE_100 = c("stone", "100")
STONE_200 = c("stone", "200")
STONE_300 = c("stone", "300")
STONE_600 = c("stone", "600")
STONE_700 = c("stone", "700")
GRANITE = c("granite", "950")
GRANITE_900 = c("granite", "900")
GRANITE_800 = c("granite", "800")
PALM_100 = c("palm", "100")
PALM_300 = c("palm", "300")
PALM_500 = c("palm", "500")
NEELAM = c("neelam", "700")
NEEM = c("neem", "700")

TA_SERIF = "NotoSerifTamil.ttf"
TA_SANS = "NotoSansTamil.ttf"
BRAHMI = "NotoSansBrahmi-Regular.ttf"
GRANTHA = "NotoSansGrantha-Regular.ttf"
FRAUNCES = "Fraunces.ttf"
FRAUNCES_I = "Fraunces-Italic.ttf"
SANS = "InstrumentSans.ttf"

FRAUNCES_DISPLAY = {"wght": 560, "opsz": 144, "SOFT": 100, "WONK": 0}


def tri(cx: float, cy: float, w: float, h: float) -> str:
    """Triangle whose centroid is (cx, cy): Brahmi e (U+1100F) in its simplest form."""
    top, base = cy - 2 * h / 3, cy + h / 3
    return f"M{cx:.2f} {top:.2f}L{cx + w / 2:.2f} {base:.2f}L{cx - w / 2:.2f} {base:.2f}Z"


@cache
def mark_e(weight: int = 900, size: float = 100.0):
    """The Ezhuthu mark in font space (baseline y=0): modern Tamil e whose bowl holds Brahmi e.

    Returns (letter_with_triangle_hole, letter_solid, triangle). The bowl counter of the Noto Serif
    Tamil glyph is closed and replaced by a triangle centred on the bowl (optical centre, measured
    and tuned by eye at 16px to 512px; see design/brand/BRAND.md "Logo construction").
    """
    d, _ = path("எ", TA_SERIF, size, 0, 0, {"wght": weight, "wdth": 100})
    d = clean(d)
    subs = ["M" + s for s in d.split("M") if s]
    subs.sort(key=lambda s: (bounds(s)[2] - bounds(s)[0]), reverse=True)
    outer, counter = subs[0], subs[1]
    x0, y0, x1, y1 = bounds(counter)
    k = size / 100
    cx = (x0 + x1) / 2 - 0.6 * k
    cy = (y0 + y1) / 2 - 0.9 * k
    w = (x1 - x0) * 1.36
    t = tri(cx, cy, w, w * 0.88)
    solid = clean(outer)
    return difference(solid, t), solid, t


def place(ds: list[str], box_x: float, box_y: float, box_w: float, ref: str | None = None,
          cx: float | None = None, cy: float | None = None, h: float | None = None):
    """Uniformly scale a group of paths (bounds of `ref` or the first path) to width box_w,
    or height h, top-left at (box_x, box_y), or centred at (cx, cy)."""
    x0, y0, x1, y1 = bounds(ref or ds[0])
    s = (h / (y1 - y0)) if h else (box_w / (x1 - x0))
    if cx is not None:
        tx, ty = cx - s * (x0 + x1) / 2, cy - s * (y0 + y1) / 2
    else:
        tx, ty = box_x - s * x0, box_y - s * y0
    return [transform(d, s, s, tx, ty) for d in ds], s


def text(s: str, font: str, size: float, x: float, y: float, axes: dict | None = None,
         anchor: str = "start", tracking: float = 0.0) -> str:
    from outline import rich_path

    d, _ = rich_path(s, font, size, x, y, axes, anchor, tracking)
    return d


def text_w(s: str, font: str, size: float, axes: dict | None = None, tracking: float = 0.0) -> float:
    from outline import rich_path

    return rich_path(s, font, size, 0, 0, axes, "start", tracking)[1]


def svg(w: float, h: float, body: str, title: str, desc: str = "", vb: str | None = None,
        extra_attrs: str = "") -> str:
    vb = vb or f"0 0 {w:g} {h:g}"
    d = f"<desc>{desc}</desc>" if desc else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w:g}" height="{h:g}" '
            f'role="img" aria-labelledby="t"{extra_attrs}><title id="t">{title}</title>{d}{body}</svg>\n')


def write(rel: str, content: str) -> Path:
    p = DESIGN / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return p


def p(d: str, fill: str, extra: str = "") -> str:
    return f'<path d="{d}" fill="{fill}"{extra}/>'
