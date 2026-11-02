"""Contact sheet: tile frames (one every STEP seconds) with burned-in timestamps.

Usage: python3 sheet.py FRAMES_DIR STEP COLS FONT OUT.png
Frames are f0001.png ... in time order (frame k is at (k-1)*STEP s).
"""
import pathlib
import sys

from PIL import Image, ImageDraw, ImageFont


def main(frames_dir, step, cols, font_path, out):
    step, cols = float(step), int(cols)
    frames = sorted(pathlib.Path(frames_dir).glob("f*.png"))
    tw, th, pad, lab = 384, 216, 8, 26
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lab + pad) + pad), (19, 16, 13))
    font = ImageFont.truetype(font_path, 20)
    d = ImageDraw.Draw(sheet)
    for k, f in enumerate(frames):
        t = k * step
        im = Image.open(f).convert("RGB").resize((tw, th), Image.LANCZOS)
        x = pad + (k % cols) * (tw + pad)
        y = pad + (k // cols) * (th + lab + pad)
        sheet.paste(im, (x, y + lab))
        d.text((x, y + 2), f"{int(t // 60)}:{t % 60:06.3f}  ({t:.0f} s)", font=font, fill=(245, 196, 104))
    sheet.save(out)
    print(f"sheet {len(frames)} frames -> {out} {sheet.size}")


if __name__ == "__main__":
    main(*sys.argv[1:])
