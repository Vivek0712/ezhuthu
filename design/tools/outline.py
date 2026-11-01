"""Shape text with HarfBuzz and return SVG outline paths (no font needed at render time).

Used by build_brand.py so every logo, wordmark and glyph card ships as pure vector paths.
Fonts are the OFL Google Fonts files listed in design/brand/FONTS.md; fetch them with
`python design/tools/fetch_fonts.py` (they are cached outside the repo and never committed).
"""
from __future__ import annotations

import os
from functools import cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

FONT_DIR = Path(os.environ.get("EZ_FONT_DIR", Path.home() / ".cache" / "ezhuthu-design-fonts"))


@cache
def _load(name: str):
    path = FONT_DIR / name
    blob = hb.Blob.from_file_path(str(path))
    face = hb.Face(blob)
    return face, TTFont(str(path))


@cache
def _instance(name: str, axes: tuple):
    from fontTools.varLib.instancer import instantiateVariableFont

    _, tt = _load(name)
    if "fvar" not in tt or not axes:
        return tt
    return instantiateVariableFont(TTFont(str(FONT_DIR / name)), dict(axes))


def shape(text: str, font: str, size: float, axes: dict | None = None, features: dict | None = None,
          tracking: float = 0.0):
    """Return (glyph records, advance width in px). tracking is in em units."""
    face, _ = _load(font)
    f = hb.Font(face)
    if axes:
        f.set_variations(axes)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(f, buf, features or {"kern": True, "liga": True})
    upem = face.upem
    scale = size / upem
    x = 0.0
    recs = []
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        recs.append((info.codepoint, x + pos.x_offset * scale, pos.y_offset * scale))
        x += pos.x_advance * scale + tracking * size
    if recs:
        x -= tracking * size
    return recs, x, scale


def path(text: str, font: str, size: float, x: float = 0, y: float = 0, axes: dict | None = None,
         anchor: str = "start", tracking: float = 0.0, features: dict | None = None) -> tuple[str, float]:
    """SVG path data for `text` with baseline at (x, y). Returns (d, width)."""
    recs, width, scale = shape(text, font, size, axes, features, tracking)
    tt = _instance(font, tuple(sorted((axes or {}).items())))
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    pen = SVGPathPen(gs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    for gid, gx, gy in recs:
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + gx, y - gy))
        gs[order[gid]].draw(tp)
    return pen.getCommands(), width


def bbox(text: str, font: str, size: float, axes: dict | None = None, tracking: float = 0.0):
    """Ink bounding box (xmin, ymin, xmax, ymax) in px, baseline at y=0, y down."""
    from fontTools.pens.boundsPen import BoundsPen

    recs, _, scale = shape(text, font, size, axes, None, tracking)
    tt = _instance(font, tuple(sorted((axes or {}).items())))
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    bp = BoundsPen(gs)
    for gid, gx, gy in recs:
        gs[order[gid]].draw(TransformPen(bp, (scale, 0, 0, -scale, gx, -gy)))
    return bp.bounds


FALLBACKS = {
    "InstrumentSans.ttf": ["NotoSansTamil.ttf", "Fraunces.ttf", "NotoSansBrahmi-Regular.ttf"],
    "Fraunces.ttf": ["NotoSerifTamil.ttf", "InstrumentSans.ttf"],
    "Fraunces-Italic.ttf": ["NotoSerifTamil.ttf", "InstrumentSans.ttf"],
    "NotoSansTamil.ttf": ["InstrumentSans.ttf", "Fraunces.ttf"],
    "NotoSerifTamil.ttf": ["Fraunces.ttf", "InstrumentSans.ttf"],
}


@cache
def _cmap(font: str):
    return _load(font)[1].getBestCmap()


def runs(text: str, font: str):
    """Split text into (substring, font) runs using cmap coverage and the FALLBACKS chain.
    Combining marks and joiners stay with the preceding run."""
    import unicodedata

    chain = [font] + FALLBACKS.get(font, [])
    out: list[list] = []
    for ch in text:
        if out and (unicodedata.category(ch).startswith("M") or ch in "‌‍"):
            out[-1][0] += ch
            continue
        pick = next((f for f in chain if ord(ch) in _cmap(f)), font)
        if ch == " " and out:
            pick = out[-1][1]
        if out and out[-1][1] == pick:
            out[-1][0] += ch
        else:
            out.append([ch, pick])
    return [(s, f) for s, f in out]


def rich_path(text: str, font: str, size: float, x: float = 0, y: float = 0, axes: dict | None = None,
              anchor: str = "start", tracking: float = 0.0) -> tuple[str, float]:
    """Like path(), with per-character font fallback. Axes are applied only where the font has them."""
    parts = runs(text, font)

    def ax_for(f):
        if not axes:
            return None
        tt = _load(f)[1]
        if "fvar" not in tt:
            return None
        names = {a.axisTag for a in tt["fvar"].axes}
        return {k: v for k, v in axes.items() if k in names} or None

    widths = [shape(s, f, size, ax_for(f), None, tracking)[1] for s, f in parts]
    total = sum(widths) + tracking * size * (len(parts) - 1 if parts else 0)
    if anchor == "middle":
        x -= total / 2
    elif anchor == "end":
        x -= total
    ds = []
    for (s, f), w in zip(parts, widths):
        d, _ = path(s, f, size, x, y, ax_for(f), "start", tracking)
        ds.append(d)
        x += w + tracking * size
    return "".join(ds), total
