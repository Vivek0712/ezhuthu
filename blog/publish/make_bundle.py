"""Regenerate the paste-ready Builder Center bundle from the Ezhuthu series articles.

    python3 blog/publish/make_bundle.py

Adapted from the Strands Decider series bundler. Bodies get a visible marker at every figure position instead of
markdown image syntax, because Builder Center only accepts uploads. The marker keeps spaces inside the angle
brackets so no markdown renderer treats it as a tag or autolink. A '< COVER IMAGE >' marker heads each body.

It also checks the Builder Center rules and the copy bans, and exits non-zero if any article breaks one:
title <= 255 chars, description <= 512, at most 5 tags, plain ASCII, no banned words, first person singular.
"""
import json
import struct
import pathlib
import re
import sys

BLOG = pathlib.Path(__file__).resolve().parent.parent
LIMIT = 2 * 1024 * 1024  # Builder Center upload limit per image


def spec(rel: str) -> str:
    """'1200x675 JPEG, 296 KB' for an image under blog/, read from the file header (PNG or JPEG)."""
    p = BLOG / rel
    if not p.exists():
        return "MISSING"
    data, kind, w, h = p.read_bytes(), "?", 0, 0
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        kind, (w, h) = "PNG", struct.unpack(">II", data[16:24])
    elif data[:2] == b"\xff\xd8":
        kind, i = "JPEG", 2
        while i < len(data):
            seg, ln = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
            if seg in (0xC0, 0xC1, 0xC2):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                break
            i += 2 + ln
    return f"{w}x{h} {kind}, {round(p.stat().st_size / 1024)} KB"

PARTS = [
    ("part-1", "ezhuthu-part-1-problem-and-product.md"),
    ("part-2", "ezhuthu-part-2-architecture.md"),
    ("part-3", "ezhuthu-part-3-evaluation.md"),
    ("project", "ezhuthu-project.md"),
]
BANNED = [
    r"\bexperimental\b", r"\bAivar\b", r"Strands AI", r"AWS AI(?! Hero)", r"\bcorrect(ly)?\b", r"\baccurate\b",
    r"\bdeciphers\b", r"\btapestry\b", r"\blandscape\b", r"\bparadigm\b", r"\bsynergy\b", r"\becosystem\b",
    r"\bframework\b", r"think of it as", r"\bwe\b", r"\bour\b", r"\bFalkorDB\b",
    r"clears? the backlog", r"replaces? epigraphists", r"validated by scholars",
    r"state of the art", r"world'?s first", r"beats? humans", r"better than epigraphists", r"\bCOA\b",
    r"\b91%", r"56\.7%", r"\bdeployed\b.{0,40}\bfine-tuned decider\b", r"fine-tuned .{0,40}\b(is|now) (live|deployed)\b",
    r"Context Ontology Accelerator", r"\bin production\b.{0,30}fine-tuned",
]

problems = []
for n, f in PARTS:
    text = (BLOG / f).read_text()
    fm, body = text.split("\n---\n", 1)
    def get(k: str, fm: str = fm) -> str:
        m = re.search(rf'^{k}: (.*)$', fm, re.M)
        return m.group(1).strip('"') if m else ""

    title, desc = get("title"), get("description")
    tags = json.loads(get("tags"))

    if len(title) > 255:
        problems.append(f"{f}: title is {len(title)} chars (max 255)")
    if len(desc) > 512:
        problems.append(f"{f}: description is {len(desc)} chars (max 512)")
    if len(tags) > 5:
        problems.append(f"{f}: {len(tags)} tags (max 5)")
    for i, line in enumerate(text.splitlines(), 1):
        bad = sorted({c for c in line if ord(c) > 127})
        if bad:
            problems.append(f"{f}:{i}: non-ASCII {bad}")
        for pat in BANNED:
            if re.search(pat, line, re.I if pat.islower() else 0):
                problems.append(f"{f}:{i}: banned pattern {pat!r}")
    for i, line in enumerate(text.splitlines(), 1):
        prose = re.sub(r"https?://\S+", "", line)
        if "1,100" in prose and "Pallava" not in prose:
            problems.append(f"{f}:{i}: 'over 1,100 years' outside a Pallava sentence")
        if not line.startswith(("title:", "description:", "|")) and re.search(r"\?(\s|$)", prose):
            problems.append(f"{f}:{i}: question mark in prose (no rhetorical questions)")
    if "By Vivek Raja, AWS AI Hero" not in body:
        problems.append(f"{f}: byline missing")

    imgs = re.findall(r'!\[[^\]]*\]\(img/([^)]+)\)', body)
    total, counter, placed = len(imgs), [0], []

    def marker(m: re.Match) -> str:
        counter[0] += 1
        heading = [h for h in re.findall(r'^#{2,3} (.*)$', body[:m.start()], re.M)] or ["(top)"]
        placed.append((counter[0], m.group(2), heading[-1]))
        return f"< FIGURE {counter[0]} of {total}: upload blog/img/{m.group(2)} here >\nAlt text: {m.group(1)}"

    body = re.sub(r'!\[([^\]]*)\]\(img/([^)]+)\)', marker, body)
    cover_alt = f"Alt text: {get('cover_alt')}\n" if get("cover_alt") else ""
    body = (f"< COVER IMAGE: upload blog/{get('cover')} in the cover field (1200x675, no text) >\n{cover_alt}\n"
            + body.lstrip("\n"))
    fields = (
        f"# {n}: form fields\n\n"
        f"Title ({len(title)} chars):\n{title}\n\n"
        f"Description ({len(desc)} chars):\n{desc}\n\n"
        f"Tags: {get('tags')}\n"
        + (f"Series: {get('series')}, part {get('part')}\n" if get("series") else "")
        + (f"GitHub or GitLab Repository: {get('repo')}\n" if get("repo") else "")
        + (f"Endpoint or live demo: {get('demo')}\n" if get("demo") else "")
        + f"Cover image: blog/{get('cover')} [{spec(get('cover'))}] (1200x675 png/jpg/webp, <= 2 MB, no text)\n"
        + (f"Cover alt text: {get('cover_alt')}\n" if get("cover_alt") else "") + "\n"
        "Figures, in body order. Each < FIGURE n of N > marker in the body is replaced by the upload; the\n"
        "Alt text line under it goes into the image's alt field; the italic line after it is the caption.\n"
        + "".join(f"  {i}. blog/img/{im}  [{spec('img/' + im)}]  (under \"{h}\")\n" for i, im, h in placed)
    )
    (BLOG / "publish" / f"{n}-fields.md").write_text(fields)
    (BLOG / "publish" / f"{n}-body.md").write_text(body)
    print(f"{n}: {len(imgs)} figure markers, {len(body.split())} words")

    for im in [get("cover")] + [f"img/{i}" for i in imgs]:
        p = BLOG / im
        if not p.exists():
            print(f"  missing image (draw it): blog/{im}")
        elif p.stat().st_size > LIMIT:
            problems.append(f"blog/{im}: over 2 MB")

if problems:
    print("\nRule check FAILED:")
    print("\n".join(f"  {p}" for p in problems))
    sys.exit(1)
print("\nRule check passed.")
