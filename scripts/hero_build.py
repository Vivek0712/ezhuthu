"""Build the home-hero assets from the real photograph and the real Reader/Restorer runs (no model calls).

Inputs (all committed):
  design/hero/thanjavur-crop.jpg   the 4-line crop of Richard Mortel's photograph (CC BY 2.0), 1568 px wide
  design/hero/boxes.json           hand-annotated carved-letter boxes in that image's pixel coordinates
  app/web/src/hero/runs/read.json      POST /api/read response (scripts/hero_read.py read --reread)
  app/web/src/hero/runs/restore.json   POST /api/restore response on that reading (scripts/hero_read.py restore)

Outputs:
  app/web/public/hero/thanjavur-{480,800,1568}.{avif,webp,jpg}   responsive variants
  app/web/src/hero/hero-reading.json                                   the full record (runs, models, notes, provenance)
  app/web/src/hero/hero-view.json                                      the trimmed subset StoneHero.tsx ships and animates
  design/hero/boxes-overlay.jpg                                        the boxes drawn on the photo, for checking

Run: .venv/bin/python scripts/hero_build.py  (Pillow with AVIF support, i.e. the project venv).
"""

from __future__ import annotations

import json
import re
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

# One akshara = an independent vowel, or a consonant (or a conjunct written with a visible virama) with its sign.
_AKSHARA = re.compile(r"[அ-ஔ]|[க-ஹ](?:்|[ா-ௌ]்?)?|\[\?\d*\]|\S")
_GAP = re.compile(r"\[\?(\d*)\]")


def aksharas(tamil_line: str) -> list[dict]:
    out = []
    for word in tamil_line.split():
        for m in _AKSHARA.finditer(word):
            g = m.group(0)
            gm = _GAP.fullmatch(g)
            if gm:
                out.append({"kind": "gap", "size": int(gm.group(1) or 1)})
            else:
                out.append({"kind": "letter", "ta": g})
        out.append({"kind": "space"})
    return out[:-1] if out else out


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


def build_json(boxes: dict, sizes: dict) -> dict:
    read = json.loads((RUNS / "read.json").read_text(encoding="utf-8"))
    restore = json.loads((RUNS / "restore.json").read_text(encoding="utf-8"))
    gaps_resp = restore["response"]["gaps"]
    gi = 0
    lines = []
    for ln in read["lines"]:
        aks = aksharas(ln["text_tamil"])
        for a in aks:
            if a["kind"] != "gap":
                continue
            g = gaps_resp[gi]
            best = g["candidates"][0] if g["candidates"] else None
            a.update({
                "gap_index": gi,
                "decision": g["decision"],
                "best": {"ta": best["text_tamil"], "iso": best["text"], "confidence": best["confidence"]} if best else None,
                "candidates": [{"ta": c["text_tamil"], "iso": c["text"], "confidence": c["confidence"]}
                               for c in g["candidates"][:3]],
                "confidence_source": best.get("confidence_source") if best else None,
            })
            gi += 1
        lines.append({"n": ln["n"], "iso": ln["text"], "ta": ln["text_tamil"], "confidence": ln["confidence"],
                      "aksharas": aks})
    assert gi == len(gaps_resp), "every gap in the reading must have a restorer answer"
    first = read.get("reread_of") or {}
    return {
        "$comment": "Generated by scripts/hero_build.py from real runs of Ezhuthu's Reader and Restorer "
                    "(scripts/hero_read.py). Do not edit by hand.",
        "photo": {**PHOTO, "width": boxes["size"][0], "height": boxes["size"][1],
                  "widths": list(WIDTHS), "bytes": {str(k): v for k, v in sizes.items()}},
        "boxes": boxes["rows"],
        "boxes_method": boxes["method"],
        "boxes_note": "Boxes mark carved letter groups. The Reader returns text line by line, not letter positions, so "
                      "a box is not matched to a particular output letter; rows are matched to reading lines.",
        "reading": {
            "endpoint": "POST /api/read",
            "first_pass": {"models": first.get("models_used"), "confidence": first.get("confidence"),
                           "escalation_skipped": first.get("escalation_skipped"), "text": first.get("text")},
            "final": {"models": read["models_used"], "router": "opus (the app's 'read again with the larger model')",
                      "confidence": read["confidence"], "script": read["script_guess"], "warnings": read["warnings"]},
            "lines": lines,
        },
        "restore": {
            "endpoint": "POST /api/restore",
            "abstain_below": ABSTAIN_BELOW,
            "models": restore["response"].get("models_used"),
            "decisions": [g["decision"] for g in gaps_resp],
            "note": "Candidate fills from the LLM (Opus 4.6) were ranked by the hosted Strands Decider "
                    "(restorer.strategy_llm: noul-topk, top 3: 'is this the expert's restoration?'). The cloud runtime "
                    "has no calibration for that decider, so it fills only at confidence >= 0.5; the best fills scored "
                    "0.38, 0.48 and 0.44, so each gap is left open and the reading goes to expert review.",
            "decider_models": sorted({c.get("decider_model") for g in gaps_resp for c in g["candidates"]} - {None}),
        },
        "edition": None,
        "cer": None,
        "edition_note": "We could not identify this stone in DHARMA or another published edition, so there is no "
                        "reference text and no character error rate. The reading is Ezhuthu's own, at low "
                        "confidence, and two Opus reads of overlapping crops disagree with each other: treat it as "
                        "unverified. No English gloss is given for the same reason.",
        "live_calls": {"reader": 4, "restorer": 6,
                       "note": "Bedrock calls. Reader: includes a Sonnet+Opus read of a 6-line crop of the same photo "
                               "that was not used. Restorer: a first run (3 calls) under the earlier self-report "
                               "config, superseded by this run under the current config (3 calls). Strands Decider "
                               "calls go to the hosted decider API, not Bedrock."},
        "run_date": "2026-11-02",
    }


def build_view(data: dict) -> dict:
    """The subset of hero-reading.json the page uses (the full record stays in the repo, out of the bundle)."""
    photo = data["photo"]
    lines = []
    for ln in data["reading"]["lines"]:
        aks = []
        for a in ln["aksharas"]:
            v = {"kind": a["kind"]}
            if "ta" in a:
                v["ta"] = a["ta"]
            if a["kind"] == "gap":
                best = a.get("best")
                v["best"] = {"ta": best["ta"], "confidence": best["confidence"]} if best else None
            aks.append(v)
        lines.append({"n": ln["n"], "iso": ln["iso"], "ta": ln["ta"], "confidence": ln["confidence"], "aksharas": aks})
    final = data["reading"]["final"]
    return {
        "$comment": "Generated by scripts/hero_build.py from hero-reading.json (the full record). Do not edit by hand.",
        "photo": {k: photo[k] for k in ("width", "height", "widths", "commons_url", "licence_url")},
        "boxes": data["boxes"],
        "reading": {"confidence": final["confidence"],
                    "script": {k: final["script"][k] for k in ("label_en", "label_ta")},
                    "lines": lines},
        "restore": {"abstain_below": data["restore"]["abstain_below"], "decisions": data["restore"]["decisions"]},
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
