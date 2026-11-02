"""Render SRT captions to PNG chips and print an ffmpeg overlay graph (this ffmpeg build has no libass/drawtext).

Usage: python3 captions.py SRT FONT OUT_DIR WIDTH HEIGHT FONT_PX BOTTOM_MARGIN_PX [FIRST_INPUT_INDEX=1] > graph.txt
The graph reads [vin] and writes [vcap]; inputs are listed in OUT_DIR/inputs.txt (input indexes start at FIRST_INPUT_INDEX).
"""
import pathlib
import re
import sys

from PIL import Image, ImageDraw, ImageFont


def parse_srt(text):
    out = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1])
        a = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3]) + int(m[4]) / 1000
        b = int(m[5]) * 3600 + int(m[6]) * 60 + int(m[7]) + int(m[8]) / 1000
        out.append((a, b, [ln.strip() for ln in lines[2:] if ln.strip()]))
    return out


def wrap(lines, font, max_w):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    words = " ".join(lines).split()
    if all(d.textlength(ln, font=font) <= max_w for ln in lines):
        return lines
    out, cur = [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if d.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            out.append(cur)
            cur = w
    return out + [cur]


def chip(lines, font, pad_x, pad_y, gap):
    d = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    sizes = [d.textbbox((0, 0), ln, font=font) for ln in lines]
    asc, desc = font.getmetrics()
    lh = asc + desc
    w = max(b[2] - b[0] for b in sizes) + 2 * pad_x
    h = len(lines) * lh + (len(lines) - 1) * gap + 2 * pad_y
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    dr = ImageDraw.Draw(im)
    dr.rounded_rectangle([0, 0, w - 1, h - 1], radius=int(lh * 0.28), fill=(19, 16, 13, 178))
    y = pad_y
    for ln, b in zip(lines, sizes):
        x = (w - (b[2] - b[0])) // 2 - b[0]
        dr.text((x + 2, y + 2), ln, font=font, fill=(0, 0, 0, 160))
        dr.text((x, y), ln, font=font, fill=(245, 240, 232, 255))
        y += lh + gap
    return im


def main(srt, font_path, out_dir, width, height, px, bottom, base=1):
    width, height, px, bottom, base = int(width), int(height), int(px), int(bottom), int(base)
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(font_path, px)
    try:
        font.set_variation_by_axes([600])
    except Exception:
        pass
    cues = parse_srt(open(srt, encoding="utf-8").read())
    graph, inputs, cur = [], [], "vin"
    for i, (a, b, lines) in enumerate(cues):
        lines = wrap(lines, font, width - 2 * int(px * 0.7) - 80)
        im = chip(lines, font, int(px * 0.7), int(px * 0.35), int(px * 0.12))
        p = out / f"cap{i:03d}.png"
        im.save(p)
        inputs.append(str(p))
        x = (width - im.width) // 2
        y = height - bottom - im.height
        nxt = f"c{i}" if i < len(cues) - 1 else "vcap"
        graph.append(f"[{cur}][{i + base}:v]overlay=x={x}:y={y}:enable='between(t,{a:.3f},{b:.3f})'[{nxt}]")
        cur = nxt
    (out / "inputs.txt").write_text("\n".join(inputs) + "\n")
    print(";\n".join(graph))


if __name__ == "__main__":
    main(*sys.argv[1:])
