"""Validate the design deliverables. Stdlib only, so it runs anywhere (python3 design/tools/check_design.py).

Checks: every SVG is well-formed XML with a viewBox; no outlined text or artwork in a banner runs past its
frame (bounding-box overflow, ignoring the masked full-bleed background texture); every PNG in renders.json exists with the expected
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


def overflow(svg: Path, root) -> list[str]:
    ns = "{http://www.w3.org/2000/svg}"
    vb = [float(v) for v in root.attrib["viewBox"].split()]
    x0, y0, x1, y1 = vb[0], vb[1], vb[0] + vb[2], vb[1] + vb[3]
    out: list[str] = []

    def walk(el, masked):
        masked = masked or "mask" in el.attrib or el.tag in (ns + "defs", ns + "mask")
        if el.tag == ns + "path" and not masked and "transform" not in el.attrib:
            b = path_bounds(el.attrib.get("d", ""))
            if b and (b[0] < x0 - 0.5 or b[1] < y0 - 0.5 or b[2] > x1 + 0.5 or b[3] > y1 + 0.5):
                out.append(f"{svg.relative_to(REPO)}: artwork overflows the {vb[2]:g}x{vb[3]:g} frame "
                           f"(bounds {b[0]:.0f},{b[1]:.0f} to {b[2]:.0f},{b[3]:.0f})")
        for ch in el:
            walk(ch, masked)

    walk(root, False)
    return out


def png_size(p: Path):
    with p.open("rb") as f:
        head = f.read(24)
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{p} is not a PNG"
    return struct.unpack(">II", head[16:24])


def main() -> int:
    errors: list[str] = []
    svgs = sorted(DESIGN.rglob("*.svg"))
    for s in svgs:
        if "node_modules" in s.parts:
            continue
        try:
            root = ET.parse(s).getroot()
            if "viewBox" not in root.attrib:
                errors.append(f"{s.relative_to(REPO)}: no viewBox")
            elif "banners" in s.parts:
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
                       capture_output=True, text=True)
    if r.returncode:
        errors.append("tokens: " + r.stdout.strip())
    docs = [REPO / "README.md", *DESIGN.rglob("*.md")]
    for d in docs:
        if "node_modules" in d.parts:
            continue
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
