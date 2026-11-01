"""Vatteluttu glyphs for tutor level L4.

Vatteluttu has no Unicode encoding, so the server sends SVG markup in ``glyph_svg``. The markup must not
carry the answer: no ISO value, no Tamil letter, no letter-specific id or label. It is the drawn shape only,
which is what the learner is asked to read.

The paths are the App team's stylised teaching drawings (``app/web/src/lib/vatteluttu.ts``), pending expert
review. Only letters with a drawing are taught or tested at L4; :func:`covered` says which.
"""

from __future__ import annotations

from .text import aksharas

# ISO-15919 akshara -> SVG path on a 100x100 grid (round stroke).
VATTELUTTU_PATHS: dict[str, str] = {
    "ka": "M50 12 V88 M18 50 C18 30 34 30 50 50 C66 70 82 70 82 50",
    "ta": "M22 30 C22 14 52 14 52 34 C52 54 22 56 26 76 C30 92 74 92 78 70",
    "pa": "M24 18 V62 C24 86 76 86 76 62 V18",
    "ma": "M20 70 C20 30 48 30 48 56 C48 30 80 30 80 56 C80 82 52 86 46 72",
    "ṉa": "M18 28 C40 12 40 52 30 62 C20 72 40 90 54 74 C68 58 82 74 82 88",
}

STROKE = "#2a1e14"


def covered(iso: str) -> bool:
    """True when every akshara of ``iso`` (spaces ignored) has a Vatteluttu drawing."""
    parts = aksharas(iso.replace(" ", ""))
    return bool(parts) and "".join(parts) == iso.replace(" ", "") and all(p in VATTELUTTU_PATHS for p in parts)


def vatteluttu_svg(iso: str, *, size: int = 120) -> str | None:
    """SVG markup for ``iso`` (one glyph per akshara, left to right), or None when a letter has no drawing.

    The accessible label is the generic "Vatteluttu" so a screen reader (or the payload) never reads out
    the answer.
    """
    if not covered(iso):
        return None
    parts = aksharas(iso.replace(" ", ""))
    width = 100 * len(parts)
    paths = "".join(
        f'<path transform="translate({100 * i} 0)" d="{VATTELUTTU_PATHS[p]}"/>' for i, p in enumerate(parts)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} 100" width="{size * len(parts)}" '
        f'height="{size}" role="img" aria-label="Vatteluttu">'
        f'<g fill="none" stroke="{STROKE}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">'
        f"{paths}</g></svg>"
    )
