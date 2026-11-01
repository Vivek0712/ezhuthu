"""Hand-drawn Vatteluttu teaching glyphs (no Unicode encoding exists for Vatteluttu).

Each glyph is a centre-line drawn on a 100x100 grid, rendered with a round 8-unit stroke.
Forms are simplified teaching shapes drawn after the published comparative charts cited in
design/glyphs/REFERENCES.md: they keep the Tamil-Brahmi skeleton and apply the two changes that
define Vatteluttu (corners become curves; strokes run on in one movement, leaning right).
Status: pending review by an epigrapher. Do not present them as facsimiles of a dated inscription.
"""

STROKE = 8

VATTELUTTU = {
    # Brahmi 𑀅 (stem with two arms) -> arms round into curls on the left of the stem
    "a": {
        "tamil": "அ",
        "brahmi": "\U00011005",
        "d": "M66 14C68 40 68 64 64 88M65 50C50 50 35 43 33 31C32 22 38 16 46 18"
             "M65 54C49 56 34 64 34 77C34 86 42 90 50 85",
    },
    # Brahmi 𑀓 (a plain cross) -> the cross-bar becomes a wave that loops through the stem
    "ka": {
        "tamil": "க",
        "brahmi": "\U00011013",
        "d": "M50 13V87M17 47C25 38 39 39 50 50C61 61 75 62 83 53",
    },
    # Brahmi 𑀫 (open cup over a bowl) -> cup and bowl drawn round and joined in one stroke
    "ma": {
        "tamil": "ம",
        "brahmi": "\U0001102B",
        "d": "M30 16C26 30 35 43 50 44C65 43 74 30 70 16M50 44C35 44 26 54 26 66C26 78 37 87 50 87"
             "C63 87 74 78 74 66C74 54 65 44 50 44",
    },
    # Brahmi 𑀏 (triangle) -> the same triangle drawn with rounded corners
    "e": {
        "tamil": "எ",
        "brahmi": "\U0001100F",
        "d": "M50 16C42 32 29 55 24 70C20 81 26 86 37 86H63C74 86 80 81 77 71C73 57 61 34 50 16Z",
    },
    # Brahmi 𑀵 (Tamil-only letter: hook on a stem with a foot) -> hook rounds into a loop, foot curls
    "lla": {
        "iso": "ḻa",
        "tamil": "ழ",
        "brahmi": "\U00011035",
        "d": "M58 42C58 27 51 18 40 18C30 18 24 25 25 33C26 42 36 46 45 42C53 38 58 34 58 42V72"
             "C58 83 50 88 41 87C33 86 28 81 27 75",
    },
    # Brahmi 𑀢 (inverted V with a foot) -> one rounded arch, the right leg running out to the right
    "ta": {
        "tamil": "த",
        "brahmi": "\U00011022",
        "d": "M20 85C26 58 38 20 51 20C62 20 68 46 72 69C74 82 81 87 90 80",
    },
    # Brahmi 𑀧 (U) -> a rounder, deeper U
    "pa": {
        "tamil": "ப",
        "brahmi": "\U00011027",
        "d": "M27 17V58C27 78 37 87 50 87C63 87 73 78 73 58V17",
    },
}


def iso(key: str) -> str:
    return VATTELUTTU[key].get("iso", key)


def svg_for(key: str, color: str = "currentColor", size: int = 100) -> str:
    g = VATTELUTTU[key]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="{size}" height="{size}" '
        f'role="img" aria-label="Vatteluttu {iso(key)} ({g["tamil"]})"><title>Vatteluttu {iso(key)}</title>'
        f'<path d="{g["d"]}" fill="none" stroke="{color}" stroke-width="{STROKE}" stroke-linecap="round" '
        f'stroke-linejoin="round"/></svg>\n'
    )
