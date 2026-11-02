"""Run Ezhuthu's own Reader and Restorer on the home-hero photograph and record what they really said.

The home hero (app/web/src/components/StoneHero.tsx) animates a real stone: it highlights letters, sends them
through the Reader -> Restorer -> Strands Decider pipeline, and shows the text that comes out. This script makes
that output real instead of invented:

  read     POST /api/read code path (``EzhuthuService.reader.read``, router "routed": Sonnet 4.6 first) on the
           hero crop; writes the raw response to app/web/src/hero/runs/read.json
  glyphs   letter by letter (``Reader.read_glyphs``, llm.escalate): for each row of design/hero/boxes.json, the
           line's crop and the same crop with the boxes numbered go to the model, which names the modern Tamil
           letter in each box with a probability; writes app/web/src/hero/runs/glyphs.json
  restore  POST /api/restore code path (``EzhuthuService.restore``) on the reading's gapped lines, if any (or, with
           --from-glyphs, on the letter-by-letter reading, worn letters as gaps); writes
           app/web/src/hero/runs/restore.json

Live Bedrock calls need EZHUTHU_LIVE=1 and are capped by --max-live-calls (cached replies under .cache/llm/ do not
count). Models come only from config/models.yaml. Assembling hero-reading.json (boxes, edition, CER) is
scripts/hero_build.py.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERO = ROOT / "app" / "web" / "src" / "hero"
RUNS = HERO / "runs"
SRC_IMAGE = ROOT / "design" / "hero" / "thanjavur-crop.jpg"
BOXES = ROOT / "design" / "hero" / "boxes.json"
GLYPH_PAD = 26  # px of stone kept above and below a row's boxes


def _service(max_live: int):
    from ezhuthu.agent.llm import BedrockLLM, BudgetedLLM
    from ezhuthu.api.service import EzhuthuService

    llm = BudgetedLLM(BedrockLLM(), max_live)
    return EzhuthuService(llm=llm, admin_token=None), llm  # type: ignore[arg-type]


def cmd_read(args: argparse.Namespace) -> None:
    svc, llm = _service(args.max_live_calls)
    b64 = base64.b64encode(Path(args.image).read_bytes()).decode()
    out = svc.reader.read(image_base64=b64, router=args.router)
    first = dict(out)
    if args.reread and out.get("reread_token"):
        # The app's "Read again with the larger model" button: the same photo, router "opus", the one-time token.
        out = svc.reader.read(image_base64=b64, router="opus", reread_token=out["reread_token"])
        out["reread_of"] = {k: first[k] for k in ("confidence", "models_used", "escalation_skipped", "text")
                            if k in first}
    out.pop("trace_id", None)
    out.pop("reread_token", None)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "read.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"lines": [ln["text"] for ln in out["lines"]], "confidence": out.get("confidence"),
                      "models": out.get("models_used"), "ledger": llm.ledger.to_dict()}, ensure_ascii=False,
                     indent=2))


def row_crops(image: Path, rows: list[list[list[int]]]):
    """(clean JPEG, numbered JPEG, band) per row: the band spans the row's boxes plus GLYPH_PAD above and below."""
    import io

    from PIL import Image, ImageDraw, ImageFont

    im = Image.open(image).convert("RGB")
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    out = []
    for row in rows:
        y0 = max(0, min(b[1] for b in row) - GLYPH_PAD)
        y1 = min(im.height, max(b[3] for b in row) + GLYPH_PAD)
        band = im.crop((0, y0, im.width, y1))
        marked = band.copy()
        d = ImageDraw.Draw(marked)
        for i, (bx0, by0, bx1, by1) in enumerate(row):
            r = (bx0, by0 - y0, bx1, by1 - y0)
            d.rectangle(r, outline=(255, 214, 0), width=2)
            label = str(i + 1)
            tx, ty = r[0] + 3, max(0, r[1] - 24)
            tb = d.textbbox((tx, ty), label, font=font)
            d.rectangle((tb[0] - 3, tb[1] - 2, tb[2] + 3, tb[3] + 2), fill=(0, 0, 0))
            d.text((tx, ty), label, fill=(255, 214, 0), font=font)
        enc = []
        for b in (band, marked):
            buf = io.BytesIO()
            b.save(buf, format="JPEG", quality=90)
            enc.append(buf.getvalue())
        out.append((enc[0], enc[1], [y0, y1]))
    return out


def cmd_glyphs(args: argparse.Namespace) -> None:
    from ezhuthu.agent.reader import prepare_image

    svc, llm = _service(args.max_live_calls)
    boxes = json.loads(BOXES.read_text(encoding="utf-8"))
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    script = (read.get("script_guess") or {}).get("script")
    rows = []
    for r, (clean, marked, band) in enumerate(row_crops(Path(args.image), boxes["rows"])):
        n = len(boxes["rows"][r])
        res = svc.reader.read_glyphs(prepare_image(clean), prepare_image(marked), n, role=args.role, script=script)
        rows.append({"row": r + 1, "band_y": band, "n_boxes": n, **res})
        print(r + 1, " ".join(f"{g['ta'] or '?'}:{g['confidence']}" for g in res["glyphs"]))
    out = {"method": "Reader.read_glyphs: per row, the clean crop and the crop with numbered boxes "
                     "(design/hero/boxes.json) in one vision call; the model names the modern Tamil letter in each "
                     "box with its probability that the letter is right",
           "role": args.role, "script_hint": script, "rows": rows}
    (RUNS / "glyphs.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ledger": llm.ledger.to_dict()}, indent=2))


GAP_BELOW = 0.5  # config/models.yaml routing.abstain_if_confidence_below: a letter read under it is left to the Restorer
_AKSHARA = re.compile(r"[அ-ஔ]|[க-ஹ](?:்|[ா-ௌ]்?)?")


def glyph_is_gap(g: dict) -> bool:
    return not g["ta"] or (g["confidence"] or 0.0) < GAP_BELOW


def glyph_text(glyphs: dict) -> str:
    """The letter-by-letter reading as restorer input: one line per row, letters run together as carved (Chola
    inscriptions have no word spaces); a letter the Reader could not name, or named under GAP_BELOW, becomes a gap of
    as many letters as the box holds (at least one)."""
    from ezhuthu.agent.text import tamil_to_iso

    lines = []
    for row in glyphs["rows"]:
        parts = []
        for g in row["glyphs"]:
            if glyph_is_gap(g):
                parts.append(f"[?{max(1, len(_AKSHARA.findall(g['ta'] or '')))}]")
            else:
                parts.append(tamil_to_iso(g["ta"]))
        lines.append("".join(parts))
    return "\n".join(lines)


def cmd_restore(args: argparse.Namespace) -> None:
    svc, llm = _service(args.max_live_calls)
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    lines = [ln["text"] for ln in read["lines"]]
    if args.text:
        text = args.text
    elif args.from_glyphs:
        text = glyph_text(json.loads((RUNS / "glyphs.json").read_text(encoding="utf-8")))
    else:
        text = "\n".join(lines)
    if "[?" not in text:
        print("the reading has no gaps; nothing to restore (pass --text with an explicit gap to demonstrate)")
        sys.exit(2)
    out = svc.restore(text, script="iso15919", max_candidates=5)
    out.pop("trace_id", None)
    payload = {"input": text, "response": out}
    (RUNS / "restore.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"gaps": out.get("gaps"), "ledger": llm.ledger.to_dict()}, ensure_ascii=False, indent=2)[:4000])


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("read")
    r.add_argument("--image", default=str(SRC_IMAGE))
    r.add_argument("--router", default="routed", choices=("routed", "sonnet"))
    r.add_argument("--reread", action="store_true",
                   help="if escalation was skipped for time, read again with router opus and the reread token")
    r.add_argument("--max-live-calls", type=int, default=2)
    r.set_defaults(fn=cmd_read)
    g = sub.add_parser("glyphs")
    g.add_argument("--image", default=str(SRC_IMAGE))
    g.add_argument("--role", default="escalate", choices=("default", "escalate"))
    g.add_argument("--max-live-calls", type=int, default=4)
    g.set_defaults(fn=cmd_glyphs)
    s = sub.add_parser("restore")
    s.add_argument("--text", help="ISO-15919 text with [?N] gaps (default: the reading itself)")
    s.add_argument("--from-glyphs", action="store_true", help="restore the letter-by-letter reading (runs/glyphs.json)")
    s.add_argument("--max-live-calls", type=int, default=4)
    s.set_defaults(fn=cmd_restore)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
