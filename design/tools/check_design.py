"""Validate the design deliverables. Stdlib only, so it runs anywhere (python3 design/tools/check_design.py).

Checks: every SVG is well-formed XML with a viewBox; no outlined text or artwork in a banner leaves its safe
area, stroke included (140 px side margins on video cards, 4 % elsewhere; only the #fieldmask full-bleed
background texture is exempt, and text or other unmeasurable elements are reported); every PNG in renders.json exists with the expected
pixel size; generated token files are up to date and every contrast pair passes; banned brand phrases are absent;
relative links in README.md and design/**/*.md resolve.
"""
from __future__ import annotations

import json
import re
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

DESIGN = Path(__file__).resolve().parents[1]
REPO = DESIGN.parent
BANNED = ["Strands AI", "AWS AI", "Amazon AI"]


_TOK = re.compile(r"[MLHVQCSTZmlhvqcstz]|-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?")


def path_bounds(d: str):
    """Conservative bounds (control points included) of an absolute-command path, as written by our build tools."""
    xs: list[float] = []
    ys: list[float] = []
    cmd, nums, cx, cy = "", [], 0.0, 0.0

    def flush():
        nonlocal cx, cy
        if cmd in "MLQCST":
            for i in range(0, len(nums) - 1, 2):
                xs.append(nums[i]), ys.append(nums[i + 1])
            if len(nums) >= 2:
                cx, cy = nums[-2], nums[-1]
        elif cmd == "H":
            for v in nums:
                xs.append(v), ys.append(cy)
                cx = v
        elif cmd == "V":
            for v in nums:
                ys.append(v), xs.append(cx)
                cy = v
        elif cmd == "h":
            for v in nums:
                cx += v
                xs.append(cx), ys.append(cy)
        elif cmd == "v":
            for v in nums:
                cy += v
                xs.append(cx), ys.append(cy)
        elif cmd in "ml":
            for i in range(0, len(nums) - 1, 2):
                cx, cy = cx + nums[i], cy + nums[i + 1]
                xs.append(cx), ys.append(cy)
        elif cmd and cmd.islower() and cmd not in "z":
            raise ValueError("relative path command " + cmd)

    for tok in _TOK.findall(d):
        if tok.isalpha():
            flush()
            cmd, nums = tok, []
        else:
            nums.append(float(tok))
    flush()
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


VIDEO_SAFE_X = 140  # video cards: text and artwork stay inside the 140 px side margins (build_banners.py, x = 140)
SAFE_FRAC = 0.04    # every other banner: inside a 4 % safe area on each side
TEXTURE_MASK = "url(#fieldmask)"  # the one full-bleed background texture mask our banner builder emits

NS = "{http://www.w3.org/2000/svg}"
# Shapes we can measure. Anything else that paints (text, use, foreignObject, ...) is reported, not skipped.
MEASURED = {"path", "rect", "circle", "ellipse", "line", "polygon", "polyline", "image"}
DRAWABLE = MEASURED | {"text", "tspan", "textPath", "use", "foreignObject", "switch", "a"}
NON_RENDERED = {"defs", "mask", "clipPath", "symbol", "pattern", "marker", "linearGradient", "radialGradient",
                "filter", "title", "desc", "metadata", "style", "script"}


def design_parts(svg: Path) -> tuple[str, ...]:
    """Path parts relative to design/, so a clone under some other 'video' or 'banners' directory is not misread.
    A file outside design/ (a test fixture) is classified by its own directory name only."""
    try:
        return svg.resolve().relative_to(DESIGN).parts
    except ValueError:
        return (svg.parent.name, svg.name)


def safe_margins(svg: Path, w: float, h: float) -> tuple[float, float]:
    if "video" in design_parts(svg)[:-1]:
        return VIDEO_SAFE_X, round(SAFE_FRAC * h)
    return round(SAFE_FRAC * w), round(SAFE_FRAC * h)


def _len(v, ref: float) -> float:
    """An SVG length in user units; a percentage resolves against the viewBox dimension `ref`."""
    v = str(v).strip()
    if v.endswith("%"):
        return float(v[:-1]) / 100 * ref
    v = v.removesuffix("px")
    return float(v)


def _points(s: str) -> list[float]:
    return [float(t) for t in re.findall(r"-?(?:\d+\.?\d*|\.\d+)(?:e-?\d+)?", s)]


def shape_bounds(tag: str, a: dict, vb: list[float]):
    """(x0, y0, x1, y1) of a measurable shape's geometry, None for a full-bleed background rect."""
    W, H = vb[2], vb[3]
    if tag == "path":
        return path_bounds(a.get("d", ""))
    if tag == "circle":
        cx, cy, r = _len(a.get("cx", 0), W), _len(a.get("cy", 0), H), _len(a.get("r", 0), W)
        return (cx - r, cy - r, cx + r, cy + r)
    if tag == "ellipse":
        cx, cy = _len(a.get("cx", 0), W), _len(a.get("cy", 0), H)
        rx, ry = _len(a.get("rx", 0), W), _len(a.get("ry", 0), H)
        return (cx - rx, cy - ry, cx + rx, cy + ry)
    if tag == "line":
        xs = [_len(a.get("x1", 0), W), _len(a.get("x2", 0), W)]
        ys = [_len(a.get("y1", 0), H), _len(a.get("y2", 0), H)]
        return (min(xs), min(ys), max(xs), max(ys))
    if tag in ("polygon", "polyline"):
        n = _points(a.get("points", ""))
        xs, ys = n[0::2], n[1::2]
        return (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None
    # rect, image
    x, y = _len(a.get("x", 0), W), _len(a.get("y", 0), H)
    w, h = _len(a.get("width", "100%" if tag == "image" else 0), W), _len(a.get("height", "100%" if tag == "image" else 0), H)
    if tag == "rect" and x <= vb[0] and y <= vb[1] and x + w >= vb[0] + W and y + h >= vb[1] + H:
        return None  # full-bleed background
    return (x, y, x + w, y + h)


def overflow(svg: Path, root) -> list[str]:
    """Banner artwork must sit inside the frame's safe area, stroke included. Only the builder's full-bleed
    background texture (a group masked with #fieldmask) and full-bleed background rects are exempt. Anything
    that paints but cannot be measured here (text, use, a transformed element, an unparseable length) is
    reported rather than skipped, so the check fails closed."""
    vb = [float(v) for v in root.attrib["viewBox"].replace(",", " ").split()]
    mx, my = safe_margins(svg, vb[2], vb[3])
    x0, y0, x1, y1 = vb[0] + mx, vb[1] + my, vb[0] + vb[2] - mx, vb[1] + vb[3] - my
    out: list[str] = []
    try:
        name = svg.relative_to(REPO)
    except ValueError:
        name = svg

    def walk(el, moved=False, stroke="none", sw="1"):
        tag = el.tag.removeprefix(NS)
        a = el.attrib
        if tag in NON_RENDERED or a.get("mask") == TEXTURE_MASK:
            return
        moved = moved or "transform" in a
        stroke, sw = a.get("stroke", stroke), a.get("stroke-width", sw)
        if tag in DRAWABLE:
            if tag not in MEASURED:
                out.append(f"{name}: <{tag}> cannot be bounds-checked; outline it to a path")
                return
            if moved:
                out.append(f"{name}: transformed {tag} cannot be bounds-checked; bake the transform in")
                return
            try:
                b = shape_bounds(tag, a, vb)
                half = _len(sw, vb[2]) / 2 if stroke != "none" and tag != "image" else 0.0
            except (ValueError, IndexError) as e:
                out.append(f"{name}: {tag} cannot be bounds-checked ({e})")
                return
            if b:
                b = (b[0] - half, b[1] - half, b[2] + half, b[3] + half)
                if b[0] < x0 - 0.5 or b[1] < y0 - 0.5 or b[2] > x1 + 0.5 or b[3] > y1 + 0.5:
                    out.append(f"{name}: artwork leaves the {vb[2]:g}x{vb[3]:g} frame's safe area "
                               f"({mx:g}/{my:g} px margins; bounds {b[0]:.0f},{b[1]:.0f} to {b[2]:.0f},{b[3]:.0f})")
        for ch in el:
            walk(ch, moved, stroke, sw)

    walk(root)
    return out


def png_size(p: Path):
    with p.open("rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{p} is not a PNG"
    return struct.unpack(">II", head[16:24])


def main() -> int:
    errors: list[str] = []
    svgs = sorted(DESIGN.rglob("*.svg"))
    svgs = [s for s in svgs if "node_modules" not in s.parts]
    for s in svgs:
        try:
            root = ET.parse(s).getroot()
            if "viewBox" not in root.attrib:
                errors.append(f"{s.relative_to(REPO)}: no viewBox")
            elif "banners" in design_parts(s)[:-1]:
                errors.extend(overflow(s, root))
        except ET.ParseError as e:
            errors.append(f"{s.relative_to(REPO)}: invalid XML ({e})")
    jobs = json.loads((DESIGN / "tools" / "renders.json").read_text())
    for j in jobs:
        out = DESIGN / j["out"]
        if not out.exists():
            errors.append(f"missing render {j['out']}")
            continue
        w, h = png_size(out)
        sc = j.get("scale", 1)
        if not j.get("full") and (w, h) != (round(j["w"] * sc), round(j["h"] * sc)):
            errors.append(f"{j['out']}: {w}x{h}, expected {j['w'] * sc}x{j['h'] * sc}")
    r = subprocess.run([sys.executable, str(DESIGN / "tools" / "build_tokens.py"), "--check"],
                       check=False, capture_output=True, text=True)
    if r.returncode:
        errors.append("tokens: " + r.stdout.strip())
    docs = [d for d in [REPO / "README.md", *DESIGN.rglob("*.md")] if "node_modules" not in d.parts]
    for d in docs:
        text = d.read_text()
        for b in BANNED:
            for m in re.finditer(re.escape(b), text):
                line = text[max(0, text.rfind("\n", 0, m.start())):text.find("\n", m.end())]
                if "never" not in line.lower():  # rule statements ("never write X") are allowed
                    errors.append(f"{d.relative_to(REPO)}: banned phrase '{b}'")
        for link in re.findall(r"\]\(([^)\s]+)\)|src=\"([^\"]+)\"|srcset=\"([^\"]+)\"", text):
            target = next(x for x in link if x)
            if re.match(r"^(https?:|mailto:|#)", target):
                continue
            target = target.split("#")[0]
            if not target:
                continue
            path = (d.parent / target).resolve()
            optional = target.startswith(("app/", "benchmark/", "eval/", "src/")) or "/app/web/" in str(path) \
                or "/benchmark/" in str(path) or "/eval/" in str(path)
            if not path.exists() and not optional:
                errors.append(f"{d.relative_to(REPO)}: broken link {target}")
    for e in errors:
        print("FAIL", e)
    n_png = len(jobs)
    print(f"checked {len(svgs)} SVGs, {n_png} PNG renders, tokens, {len(docs)} docs: "
          f"{'OK' if not errors else str(len(errors)) + ' problem(s)'}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
