"""Validate the design deliverables. Stdlib only, so it runs anywhere (python3 design/tools/check_design.py).

Checks: every SVG is well-formed XML with a viewBox; every PNG in renders.json exists with the expected
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
