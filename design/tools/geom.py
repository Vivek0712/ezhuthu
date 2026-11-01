"""Small vector helpers for the brand build: boolean ops (skia-pathops), placement, triangles."""
from __future__ import annotations

import pathops
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path


def _fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def to_skia(d: str, transform=(1, 0, 0, 1, 0, 0)) -> pathops.Path:
    p = pathops.Path()
    parse_path(d, TransformPen(p.getPen(), transform))
    return p


def to_d(p: pathops.Path) -> str:
    pen = SVGPathPen(None, ntos=_fmt)
    p.draw(pen)
    return pen.getCommands()


def union(*ds: str) -> str:
    out = pathops.Path()
    for d in ds:
        out = pathops.op(out, to_skia(d), pathops.PathOp.UNION)
    return to_d(out)


def difference(a: str, *bs: str) -> str:
    out = to_skia(a)
    out = pathops.simplify(out)
    for b in bs:
        out = pathops.op(out, pathops.simplify(to_skia(b)), pathops.PathOp.DIFFERENCE)
    return to_d(out)


def clean(d: str) -> str:
    return to_d(pathops.simplify(to_skia(d)))


def bounds(d: str):
    bp = BoundsPen(None)
    parse_path(d, bp)
    return bp.bounds


def transform(d: str, sx: float = 1, sy: float | None = None, tx: float = 0, ty: float = 0) -> str:
    sy = sx if sy is None else sy
    pen = SVGPathPen(None, ntos=_fmt)
    parse_path(d, TransformPen(pen, (sx, 0, 0, sy, tx, ty)))
    return pen.getCommands()


def fit(d: str, cx: float, cy: float, w: float | None = None, h: float | None = None) -> str:
    """Scale d uniformly so its ink box has width w (or height h), centred on (cx, cy)."""
    x0, y0, x1, y1 = bounds(d)
    s = (w / (x1 - x0)) if w else (h / (y1 - y0))
    return transform(d, s, s, cx - s * (x0 + x1) / 2, cy - s * (y0 + y1) / 2)


def ring_triangle(cx: float, top: float, base: float, half_w: float, stroke: float) -> str:
    """An outlined triangle (Brahmi e) as a closed ring with even stroke on all sides."""
    import math

    ax, ay = cx, top
    bx, by = cx - half_w, base
    qx, qy = cx + half_w, base
    outer = f"M{_fmt(ax)} {_fmt(ay)}L{_fmt(qx)} {_fmt(qy)}L{_fmt(bx)} {_fmt(by)}Z"
    # inset: incentre-based scaling keeps all three sides the same thickness
    a = math.dist((bx, by), (qx, qy))
    b = math.dist((ax, ay), (qx, qy))
    c = math.dist((ax, ay), (bx, by))
    per = a + b + c
    ix = (a * ax + b * bx + c * qx) / per
    iy = (a * ay + b * by + c * qy) / per
    area = abs((qx - bx) * (ay - by)) / 2
    r = 2 * area / per
    k = (r - stroke) / r
    pts = [(ix + (x - ix) * k, iy + (y - iy) * k) for x, y in ((ax, ay), (qx, qy), (bx, by))]
    inner = "M" + "L".join(f"{_fmt(x)} {_fmt(y)}" for x, y in pts) + "Z"
    return difference(outer, inner)
