"""Tile hero frames (app/web/scripts/hero-frames.mjs) into one labelled contact sheet for review.

Run: .venv/bin/python scripts/hero_contact_sheet.py FRAMES_DIR OUT.png [--step-ms 1000] [--cols 4] [--width 560]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("frames", type=Path)
    p.add_argument("out", type=Path)
    p.add_argument("--step-ms", type=int, default=1000)
    p.add_argument("--cols", type=int, default=4)
    p.add_argument("--width", type=int, default=560)
    a = p.parse_args(argv)
    files = sorted(a.frames.glob("f*.png"))
    if not files:
        raise SystemExit(f"no frames in {a.frames}")
    first = Image.open(files[0])
    w = a.width
    h = round(first.height * w / first.width)
    pad = 8
    rows = -(-len(files) // a.cols)
    sheet = Image.new("RGB", (a.cols * (w + pad) + pad, rows * (h + pad) + pad), (255, 255, 255))
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for k, f in enumerate(files):
        im = Image.open(f).convert("RGB").resize((w, h), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        label = f"{k * a.step_ms / 1000:.1f} s"
        tb = d.textbbox((8, 6), label, font=font)
        d.rectangle((tb[0] - 4, tb[1] - 3, tb[2] + 4, tb[3] + 3), fill=(0, 0, 0))
        d.text((8, 6), label, fill=(255, 255, 255), font=font)
        sheet.paste(im, (pad + (k % a.cols) * (w + pad), pad + (k // a.cols) * (h + pad)))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(a.out, optimize=True)
    print(f"wrote {a.out} ({len(files)} frames)")


if __name__ == "__main__":
    main()
