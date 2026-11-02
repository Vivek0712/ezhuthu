"""Build the home-hero assets from the real photograph and the real Reader/Restorer runs (no model calls).

Inputs (all committed):
  design/hero/thanjavur-crop.jpg   the 4-line crop of Richard Mortel's photograph (CC BY 2.0), 1568 px wide
  design/hero/boxes.json           hand-annotated carved-letter boxes in that image's pixel coordinates
  app/web/src/hero/runs/read.json           POST /api/read response (scripts/hero_read.py read --reread)
  app/web/src/hero/runs/glyphs.json         letter-by-letter reading of the boxes (scripts/hero_read.py glyphs)
  app/web/src/hero/runs/restore.json        POST /api/restore on that reading (hero_read.py restore --from-glyphs)
  app/web/src/hero/runs/restore-lines.json  POST /api/restore on the line reading (kept for the record)

Outputs:
  app/web/public/hero/thanjavur-{480,800,1568}.{avif,webp,jpg}   responsive variants
  app/web/src/hero/hero-reading.json                                   the full record (runs, models, notes, provenance)
  app/web/src/hero/hero-view.json                                      the trimmed subset StoneHero.tsx ships and animates
  design/hero/boxes-overlay.jpg                                        the boxes drawn on the photo, for checking

Run: .venv/bin/python scripts/hero_build.py  (Pillow with AVIF support, i.e. the project venv).
"""

from __future__ import annotations

import json
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "design" / "hero" / "thanjavur-crop.jpg"
BOXES = ROOT / "design" / "hero" / "boxes.json"
OVERLAY = ROOT / "design" / "hero" / "boxes-overlay.jpg"
RUNS = ROOT / "app" / "web" / "src" / "hero" / "runs"
OUT_JSON = ROOT / "app" / "web" / "src" / "hero" / "hero-reading.json"
OUT_VIEW = ROOT / "app" / "web" / "src" / "hero" / "hero-view.json"
PUBLIC = ROOT / "app" / "web" / "public" / "hero"
WIDTHS = (480, 800, 1568)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hero_read import GAP_BELOW, glyph_is_gap, glyph_text

ABSTAIN_BELOW = 0.5  # config/models.yaml routing.abstain_if_confidence_below (no calibration for the self-report path)

PHOTO = {
    "title": "Brihadishwara Temple, Dedicated to Shiva, built by Rajaraja I, completed in 1010, Thanjavur (38)",
    "author": "Richard Mortel",
    "author_url": "https://www.flickr.com/people/43714545@N06",
    "licence": "CC BY 2.0",
    "licence_url": "https://creativecommons.org/licenses/by/2.0/",
    "commons_url": "https://commons.wikimedia.org/wiki/File:1010_CE_Brihadishwara_Shiva_Temple,_inscription,"
                   "_built_by_Rajaraja_I,_Thanjavur_Tamil_Nadu_India.jpg",
    "flickr_url": "https://www.flickr.com/photos/prof_richard/36826608993/",
    "taken": "2017-09-01",
    "modifications": "cropped to four lines of the inscription, resized and re-encoded (AVIF, WebP, JPEG)",
    "place_en": "Brihadisvara temple, Thanjavur",
    "place_ta": "பெருவுடையார் கோயில், தஞ்சாவூர்",
    "era_en": "Chola period (the temple was completed in 1010 CE under Rajaraja I)",
    "era_ta": "சோழர் காலம் (கோயில் கி.பி. 1010-இல் முதலாம் இராசராசன் காலத்தில் நிறைவுற்றது)",
}

def build_images() -> dict:
    im = Image.open(SRC).convert("RGB")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    sizes = {}
    for w in WIDTHS:
        h = round(im.height * w / im.width)
        r = im if w == im.width else im.resize((w, h), Image.LANCZOS)
        stem = PUBLIC / f"thanjavur-{w}"
        hi = w > 1000  # the 2x variant: lower quality, the extra pixels hide it
        r.save(stem.with_suffix(".avif"), quality=44 if hi else 52, speed=4)
        # WebP is only the fallback for browsers without AVIF; at 1568 px it must not outweigh the JPEG.
        r.save(stem.with_suffix(".webp"), quality=46 if hi else 72, method=6)
        r.save(stem.with_suffix(".jpg"), quality=64 if hi else 76, optimize=True, progressive=True)
        sizes[w] = {ext: stem.with_suffix(f".{ext}").stat().st_size for ext in ("avif", "webp", "jpg")}
    return sizes


def build_overlay(boxes: dict) -> None:
    im = Image.open(SRC).convert("RGB")
    d = ImageDraw.Draw(im)
    cols = [(255, 230, 0), (0, 255, 255), (255, 80, 200), (120, 255, 80)]
    for r, row in enumerate(boxes["rows"]):
        for i, (x0, y0, x1, y1) in enumerate(row):
            d.rectangle([x0, y0, x1, y1], outline=cols[r % 4], width=3)
            d.text((x0 + 3, y0 + 2), f"{r + 1}.{i + 1}", fill=cols[r % 4])
    im.save(OVERLAY, quality=82, optimize=True, progressive=True)


def _mean(xs: list[float]) -> float:
    return round(sum(xs) / len(xs), 2) if xs else 0.0


def _fill_ta(c: dict) -> str:
    """A restorer fill for display: DHARMA's word-join hyphens dropped (the stone has none)."""
    return c["text_tamil"].replace("-", "")


def build_glyph_rows(boxes: dict, glyphs: dict, restore: dict) -> tuple[list[dict], list[dict]]:
    """Per box: the Reader's modern letter and probability; letters under GAP_BELOW (or unnamed) are the gaps the
    Restorer was run on (scripts/hero_read.py restore --from-glyphs), each with the Restorer's best fill and the
    Decider's decision."""
    gaps_resp = restore["response"]["gaps"]
    assert restore["input"] == glyph_text(glyphs), "restore.json must be the run on the letter-by-letter reading"
    rows, gaps, gi = [], [], 0
    for r, row in enumerate(glyphs["rows"]):
        assert row["n_boxes"] == len(boxes["rows"][r]), "one glyph answer per box"
        gl = []
        for g in row["glyphs"]:
            e = {"box": g["box"], "ta": g["ta"], "iso": unicodedata.normalize("NFC", g["iso"] or ""),
                 "confidence": g["confidence"], "note": g["note"]}
            if glyph_is_gap(g):
                resp = gaps_resp[gi]
                best = resp["candidates"][0] if resp["candidates"] else None
                e["gap"] = {"index": gi, "decision": resp["decision"],
                            "best": {"ta": _fill_ta(best), "iso": best["text"], "confidence": best["confidence"],
                                     "confidence_source": best.get("confidence_source"),
                                     "decider_model": best.get("decider_model")} if best else None,
                            "candidates": [{"ta": _fill_ta(c), "confidence": c["confidence"]}
                                           for c in resp["candidates"][:3]]}
                gaps.append({"row": r, "box": g["box"] - 1, **e["gap"]})
                gi += 1
            gl.append(e)
        rows.append({"row": r + 1, "model": row["model"], "glyphs": gl,
                     "mean_confidence": _mean([x["confidence"] or 0.0 for x in gl])})
    assert gi == len(gaps_resp), "every gap must have a restorer answer"
    return rows, gaps


def build_json(boxes: dict, sizes: dict) -> dict:
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    glyphs = json.loads((RUNS / "glyphs.json").read_text(encoding="utf-8"))
    restore = json.loads((RUNS / "restore.json").read_text(encoding="utf-8"))
    restore_lines = json.loads((RUNS / "restore-lines.json").read_text(encoding="utf-8"))
    rows, gaps = build_glyph_rows(boxes, glyphs, restore)
    letters = [g for row in rows for g in row["glyphs"]]
    first = read.get("reread_of") or {}
    return {
        "$comment": "Generated by scripts/hero_build.py from real runs of Ezhuthu's Reader and Restorer "
                    "(scripts/hero_read.py). Do not edit by hand.",
        "photo": {**PHOTO, "width": boxes["size"][0], "height": boxes["size"][1],
                  "widths": list(WIDTHS), "bytes": {str(k): v for k, v in sizes.items()}},
        "boxes": boxes["rows"],
        "boxes_method": boxes["method"],
        "glyphs": {
            "method": glyphs["method"],
            "role": glyphs["role"],
            "models": sorted({row["model"] for row in rows}),
            "script": read["script_guess"],
            "rows": rows,
            "letters": len(letters),
            "mean_confidence": _mean([g["confidence"] or 0.0 for g in letters]),
            "gap_below": GAP_BELOW,
            "note": "The hero shows this letter-by-letter reading: for each hand-drawn box, the modern Tamil letter "
                    "the Reader named and its own probability that the letter is right (self-reported, not "
                    "calibrated). Letters it named under 0.5 were treated as gaps and sent to the Restorer.",
        },
        "restore": {
            "endpoint": "POST /api/restore",
            "input": restore["input"],
            "abstain_below": ABSTAIN_BELOW,
            "models": restore["response"].get("models_used"),
            "decisions": [g["decision"] for g in restore["response"]["gaps"]],
            "gaps": gaps,
            "note": "Candidate fills from the LLM were ranked by the hosted Strands Decider (restorer.strategy_llm: "
                    "noul-topk, top 3). Without a calibration for that decider the Restorer fills only at "
                    "confidence >= 0.5; the best fill scored under that, so the gap is left open.",
        },
        "line_reading": {
            "endpoint": "POST /api/read",
            "note": "The app's own line-by-line reading of the same crop (Sonnet 4.6, then Opus 4.6 on 'read again'), "
                    "and the Restorer on its gaps. Kept for the record; the hero shows the letter-by-letter reading.",
            "first_pass": {"models": first.get("models_used"), "confidence": first.get("confidence"),
                           "text": first.get("text")},
            "final": {"models": read["models_used"], "confidence": read["confidence"],
                      "script": read["script_guess"], "lines": [[ln["text"], ln["confidence"]] for ln in read["lines"]]},
            "restore": {"input": restore_lines["input"],
                        "decisions": [g["decision"] for g in restore_lines["response"]["gaps"]],
                        "best": [[_fill_ta(g["candidates"][0]), g["candidates"][0]["confidence"]]
                                 for g in restore_lines["response"]["gaps"] if g["candidates"]]},
        },
        "edition": None,
        "match_rate": None,
        "edition_note": "This stone is not identified in DHARMA or another published edition we could find, so the "
                        "hero shows no edition text, no match rate and no translation. A search of Wikimedia Commons "
                        "for an openly licensed photo of an inscription in the DHARMA split found none whose text "
                        "could be matched to an edition (2026-11-02).",
        "live_calls": {"reader": 4, "glyphs": 4, "restorer": 7,
                       "note": "Bedrock calls. Reader: includes a Sonnet+Opus read of a 6-line crop of the same photo "
                               "that was not used. Glyphs: one Opus call per row. Restorer: 6 on the line reading "
                               "(two runs) and 1 on the letter-by-letter reading. Strands Decider calls go to the "
                               "hosted decider API, not Bedrock."},
        "run_date": "2026-11-02",
    }


FEATURED = 4  # letters shown one at a time in a full match card before the cascade


def build_view(data: dict) -> dict:
    """The subset of hero-reading.json the page uses (the full record stays in the repo, out of the bundle)."""
    photo = data["photo"]
    g = data["glyphs"]
    rows = []
    for row in g["rows"]:
        gl = []
        for x in row["glyphs"]:
            v = {"ta": x["ta"] or "", "c": x["confidence"]}
            if "gap" in x:
                best = x["gap"]["best"]
                v["gap"] = {"decision": x["gap"]["decision"],
                            "best": {"ta": best["ta"], "c": best["confidence"]} if best else None}
            gl.append(v)
        iso = "".join("[?]" if ("gap" in x and x["gap"]["decision"] == "abstain") else (x["iso"] or "[?]")
                      for x in row["glyphs"])
        rows.append({"iso": iso, "c": row["mean_confidence"],
                     "glyphs": gl})
    script = g["script"]
    return {
        "$comment": "Generated by scripts/hero_build.py from hero-reading.json (the full record). Do not edit by hand.",
        "photo": {k: photo[k] for k in ("width", "height", "widths", "commons_url", "licence_url")},
        "boxes": data["boxes"],
        "script": {k: script[k] for k in ("label_en", "label_ta")},
        "rows": rows,
        "featured": FEATURED,
        "letters": g["letters"],
        "mean": g["mean_confidence"],
        "abstain_below": data["restore"]["abstain_below"],
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    boxes = json.loads(BOXES.read_text(encoding="utf-8"))
    sizes = build_images()
    build_overlay(boxes)
    data = build_json(boxes, sizes)
    write_json(OUT_JSON, data)
    write_json(OUT_VIEW, build_view(data))
    for w, s in sizes.items():
        print(w, {k: f"{v / 1024:.0f} KB" for k, v in s.items()})


if __name__ == "__main__":
    main()
