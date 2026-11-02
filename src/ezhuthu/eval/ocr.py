"""OCR evaluation for the Reader (``POST /api/read``): synthetic plates + openly licensed real images.

There is no public dataset of inscription photographs paired with edition text, so this measures two proxies:

(a) **synthetic**: lines from DHARMA **TEST-split** inscriptions (``benchmark/inscriptions.jsonl``,
    ``text_iso_masked``: editorial restorations shown as ``[?N]`` gaps, which are drawn as chipped stretches),
    rendered by Chromium with the app's Noto fonts (Tamil sans/serif, Tamil-Brahmi via the Unicode Brahmi block,
    Grantha) on procedural stone/paper textures at three degradation levels, then sensor noise + JPEG. Vatteluttu
    has no Unicode encoding or font, so it is **not** covered. Rendering Pallava- or Chola-era text in a modern Tamil
    font tests reading the letters, not reading the period's letter forms.
(b) **real**: a handful of openly licensed images from Wikimedia Commons / Tamil Wikisource whose published reading
    is available (``eval/ocr/real_images.json`` records URL, author, licence and the reference text's source).

    python -m ezhuthu.eval.ocr synth  --plates 24 --seed 7            # render into .cache/ocr/synth
    python -m ezhuthu.eval.ocr fetch-real                              # download the real set into .cache/ocr/real
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.ocr run --set synth --max-live-calls 120 --out <jsonl>
    EZHUTHU_LIVE=1 python -m ezhuthu.eval.ocr run --set real  --max-live-calls 30  --out <jsonl>
    python -m ezhuthu.eval.ocr report --synth <jsonl> --real <jsonl> --out eval/reports/2026-11-02-ocr-eval

Scoring: CER = Levenshtein(letters) / reference letters, on ``normalise_for_scoring`` (ISO letters only; spaces,
hyphens, gap markers and editorial marks dropped), micro-averaged (summed edits / summed reference letters). WER on
whitespace words in the same normal form. Gap markers are scored separately (count recall/precision per image).
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from rapidfuzz.distance import Levenshtein

from ..agent.config import repo_root
from ..agent.text import GAP_RE, tamil_to_iso

ROOT = repo_root() or Path.cwd()
CACHE = ROOT / ".cache" / "ocr"
REAL_MANIFEST = ROOT / "eval" / "ocr" / "real_images.json"
LEVELS = ("clean", "photo", "weathered")
NOISE = {"clean": 0.0, "photo": 7.0, "weathered": 16.0}
JPEG_Q = {"clean": 92, "photo": 70, "weathered": 45}
UA = {"User-Agent": "ezhuthu-ocr-eval/0.1 (research; https://github.com/Vivek0712/ezhuthu)"}


# ---------------------------------------------------------------------------------------------------------------
# scoring

def letters(text: str) -> str:
    from ..corpus.script import normalise_for_scoring

    return normalise_for_scoring(text)


def words(text: str) -> list[str]:
    from ..corpus.script import normalise_for_scoring

    return [w for w in (normalise_for_scoring(x) for x in GAP_RE.sub(" ", text).split()) if w]


def cer_counts(ref: str, hyp: str) -> tuple[int, int]:
    r, h = letters(ref), letters(hyp)
    return Levenshtein.distance(r, h), len(r)


def wer_counts(ref: str, hyp: str) -> tuple[int, int]:
    r, h = words(ref), words(hyp)
    return Levenshtein.distance(r, h), len(r)


def best_window(ref: str, hyp: str) -> str:
    """For a real image showing only part of a long edition: the edition substring (in letters) whose CER against
    the reading is lowest, searched over windows of the reading's length +-25%. Reported as such; it favours the
    model (best-case alignment) and is only used when the image's extent is not known."""
    r, h = letters(ref), letters(hyp)
    if not h or len(r) <= len(h):
        return r
    best, best_d = r[: len(h)], 10**9
    step = max(1, len(h) // 40)
    for size in {int(len(h) * f) for f in (0.75, 0.9, 1.0, 1.1, 1.25)}:
        for i in range(0, max(1, len(r) - size + 1), step):
            d = Levenshtein.distance(r[i:i + size], h)
            if d < best_d:
                best, best_d = r[i:i + size], d
    return best


# ---------------------------------------------------------------------------------------------------------------
# synthetic set

def _good_line(line: str) -> bool:
    n = len(letters(line))
    return 12 <= n <= 46 and len(GAP_RE.findall(line)) <= 2 and len(line) <= 72 and not re.search(r"\d", line)


def select_plates(n_plates: int, seed: int, lines_per_plate: int = 3) -> list[dict[str, Any]]:
    """One plate (consecutive lines) per TEST inscription, round-robin over dynasty groups."""
    ins = [json.loads(x) for x in (ROOT / "benchmark" / "inscriptions.jsonl").read_text(encoding="utf-8").splitlines()]
    rnd = random.Random(seed)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in ins:
        if d["split"] != "test" or d["lang"] != "tam-Latn":
            continue
        rows = [r.lstrip("-").strip() for r in (d.get("text_iso_masked") or "").split("\n")]
        runs = [rows[i:i + lines_per_plate] for i in range(len(rows) - lines_per_plate + 1)]
        runs = [r for r in runs if all(_good_line(x) for x in r)]
        if runs:
            groups[d["dynasty"] or "undated"].append({"inscription_id": d["id"], "dynasty": d["dynasty"] or "undated",
                                                      "source_url": d["source_url"], "lines": rnd.choice(runs)})
    for g in groups.values():
        rnd.shuffle(g)
    order = sorted(groups, key=lambda k: -len(groups[k]))
    plates: list[dict[str, Any]] = []
    while len(plates) < n_plates and any(groups.values()):
        for k in order:
            if groups[k] and len(plates) < n_plates:
                plates.append(groups[k].pop())
    return plates


def render_items(plates: list[dict[str, Any]], *, other_scripts: int) -> list[dict[str, Any]]:
    from ..corpus.script import (
        iso_to_grantha,
        iso_to_tamil_brahmi,
        iso_to_tamil_display,
        strip_editorial_marks,
    )

    items = []
    for i, p in enumerate(plates):
        tamil = [iso_to_tamil_display(x) for x in p["lines"]]
        for level in LEVELS:
            items.append({**p, "id": f"p{i:02d}-tamil-{level}", "plate": i, "level": level,
                          "font": "tamil-sans" if i % 2 == 0 else "tamil-serif", "rendered_script": "tamil",
                          "render_lines": tamil, "seed": 1000 + i * 7 + LEVELS.index(level)})
        if i < other_scripts:
            clean = [strip_editorial_marks(x).replace("-", "") for x in p["lines"]]
            items.append({**p, "id": f"p{i:02d}-brahmi-photo", "plate": i, "level": "photo", "font": "brahmi",
                          "rendered_script": "tamil-brahmi", "render_lines": [iso_to_tamil_brahmi(x) for x in clean],
                          "seed": 5000 + i})
            items.append({**p, "id": f"p{i:02d}-grantha-photo", "plate": i, "level": "photo", "font": "grantha",
                          "rendered_script": "grantha", "render_lines": [iso_to_grantha(x) for x in clean],
                          "seed": 7000 + i})
    return items


def degrade(png: Path, level: str, seed: int) -> bytes:
    import numpy as np
    from PIL import Image

    im = Image.open(png).convert("RGB")
    if NOISE[level]:
        a = np.asarray(im).astype(np.float32)
        a += np.random.default_rng(seed).normal(0, NOISE[level], a.shape)
        im = Image.fromarray(np.clip(a, 0, 255).astype("uint8"))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=JPEG_Q[level])
    return buf.getvalue()


def cmd_synth(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plates = select_plates(args.plates, args.seed)
    items = render_items(plates, other_scripts=args.other_scripts)
    manifest = {"items": [{"id": it["id"], "lines": it["render_lines"], "font": it["font"], "level": it["level"],
                           "seed": it["seed"]} for it in items]}
    mpath = out / "render_manifest.json"
    mpath.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    subprocess.run(["node", str(Path(__file__).with_name("ocr_render.mjs")), str(mpath), str(out / "png")],
                   check=True)
    for it in items:
        (out / f"{it['id']}.jpg").write_bytes(degrade(out / "png" / f"{it['id']}.png", it["level"], it["seed"]))
        it["image"] = str((out / f"{it['id']}.jpg").relative_to(ROOT))
        it["truth"] = "\n".join(it["lines"])
        # What a perfect reader of the image could recover: the rendering transliterated back (Tamil script
        # does not mark e.g. ISO voicing distinctions, so this can differ from the edition).
        it["truth_visible"] = "\n".join(tamil_to_iso(x) for x in it["render_lines"]) \
            if it["rendered_script"] == "tamil" else it["truth"]
    (out / "items.jsonl").write_text("".join(json.dumps(it, ensure_ascii=False) + "\n" for it in items),
                                     encoding="utf-8")
    n_lines = len({(it["plate"], i) for it in items for i in range(len(it["lines"]))})
    print(f"{len(plates)} plates ({n_lines} TEST lines from {len({p['inscription_id'] for p in plates})} "
          f"inscriptions), {len(items)} images -> {out}")


# ---------------------------------------------------------------------------------------------------------------
# real set

def _get(url: str, params: dict[str, Any] | None = None) -> bytes:
    if params:
        url += "?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def _strip_html(s: str | None) -> str:
    import html

    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def wikisource_text(wikitext: str) -> str:
    """Body of a proofread Page: wikitext (header/footer <noinclude> dropped, templates and markup removed)."""
    t = re.sub(r"<noinclude>.*?</noinclude>", "", wikitext, flags=re.DOTALL)
    for _ in range(3):
        t = re.sub(r"\{\{[^{}]*\}\}", " ", t)
    t = re.sub(r"<ref.*?</ref>|<[^>]+>", " ", t, flags=re.DOTALL)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"'{2,}|^[:;#*]+|__\w+__", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*(\{\||\|\}|\|-).*$", "", t, flags=re.MULTILINE)  # wiki table markup
    t = re.sub(r"^\s*\|\s*|\s*\|\|\s*", " ", t, flags=re.MULTILINE)
    t = t.replace("\ufeff", "")
    return "\n".join(x.strip() for x in t.splitlines() if x.strip())


def cmd_fetch_real(args: argparse.Namespace) -> None:
    man = json.loads(REAL_MANIFEST.read_text(encoding="utf-8"))
    out = CACHE / "real"
    out.mkdir(parents=True, exist_ok=True)
    for it in man["images"]:
        if it["source"] == "commons":
            d = json.loads(_get("https://commons.wikimedia.org/w/api.php",
                                {"action": "query", "titles": it["file"], "prop": "imageinfo",
                                 "iiprop": "url|extmetadata", "iiurlwidth": 2000}))
            page = next(iter(d["query"]["pages"].values()))
        else:  # tawikisource proofread page: the scan page and its validated text
            d = json.loads(_get("https://ta.wikisource.org/w/api.php",
                                {"action": "query", "titles": it["file"], "prop": "imageinfo",
                                 "iiprop": "url|extmetadata", "iiurlwidth": 1600,
                                 "iiurlparam": f"page{it['page']}-1600px"}))
            page = next(iter(d["query"]["pages"].values()))
            wt = json.loads(_get("https://ta.wikisource.org/w/api.php",
                                 {"action": "query", "titles": it["wikisource_page"], "prop": "revisions",
                                  "rvprop": "content", "rvslots": "main"}))
            rev = next(iter(wt["query"]["pages"].values()))["revisions"][0]["slots"]["main"]["*"]
            it["reference_tamil"] = wikisource_text(rev)
            it["reference"] = tamil_to_iso(it["reference_tamil"])
        info = page["imageinfo"][0]
        meta = info.get("extmetadata", {})
        it["licence"] = _strip_html(meta.get("LicenseShortName", {}).get("value")) or it.get("licence")
        it["licence_url"] = meta.get("LicenseUrl", {}).get("value") or it.get("licence_url")
        it["author"] = _strip_html(meta.get("Artist", {}).get("value"))[:120] or it.get("author")
        it["page_url"] = info.get("descriptionurl")
        it["image_url"] = info.get("thumburl") or info["url"]
        dest = out / f"{it['id']}.jpg"
        if not dest.exists():
            dest.write_bytes(_get(it["image_url"]))
            time.sleep(1.0)
        it["image"] = str(dest.relative_to(ROOT))
        print(f"{it['id']}: {it['licence']} by {it['author']} -> {dest.name}")
    REAL_MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------
# run

def cmd_run(args: argparse.Namespace) -> None:
    from ..agent.llm import BedrockLLM, BudgetedLLM
    from ..agent.reader import Reader, prepare_image

    if args.set == "synth":
        items = [json.loads(x) for x in (Path(args.items)).read_text(encoding="utf-8").splitlines()]
    else:
        items = json.loads(Path(args.manifest).read_text(encoding="utf-8"))["images"]
    if args.limit:
        items = items[: args.limit]
    inner = BedrockLLM(rpm=args.rpm)
    llm = BudgetedLLM(inner, args.max_live_calls)
    reader = Reader(llm=llm)  # type: ignore[arg-type]

    def one(it: dict[str, Any]) -> dict[str, Any]:
        img = prepare_image((ROOT / it["image"]).read_bytes(), reader.settings)
        t0 = time.perf_counter()
        try:
            out = reader.read_image(img, router=args.router)
            err = None
        except Exception as exc:  # noqa: BLE001  (budget exhausted, Bedrock errors: recorded per image, never fatal)
            out, err = None, f"{type(exc).__name__}: {exc}"[:300]
        rec = {k: it.get(k) for k in ("id", "plate", "level", "font", "rendered_script", "dynasty", "inscription_id",
                                       "truth", "truth_visible", "reference", "reference_kind", "script", "kind",
                                       "source", "licence", "author", "page_url", "title")}
        rec["seconds"] = round(time.perf_counter() - t0, 2)
        rec["error"] = err
        if out:
            rec.update({"reading": out["text"], "lines": [ln["text"] for ln in out["lines"]],
                        "confidence": out["confidence"], "script_guess": out["script_guess"],
                        "models_used": out["models_used"], "model": out.get("model"),
                        "escalated": out["escalated"], "escalation_skipped": out.get("escalation_skipped"),
                        "warnings": out["warnings"], "note": out.get("note")})
        return rec

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        recs = list(ex.map(one, items))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")
    meta = {"set": args.set, "router": args.router, "n": len(recs), "errors": sum(1 for r in recs if r["error"]),
            "usage": inner.ledger.to_dict(), "budget": args.max_live_calls, "budget_refusals": llm.exhausted}
    Path(args.out + ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(meta, indent=2))


# ---------------------------------------------------------------------------------------------------------------
# report

def _agg(recs: list[dict[str, Any]], ref_key: str) -> dict[str, Any]:
    ce = cn = we = wn = 0
    for r in recs:
        if not r.get("reading") and r.get("error"):
            continue
        hyp = r.get("reading") or ""
        e, n = cer_counts(r[ref_key], hyp)
        ce, cn = ce + e, cn + n
        e, n = wer_counts(r[ref_key], hyp)
        we, wn = we + e, wn + n
    scored = [r for r in recs if not (not r.get("reading") and r.get("error"))]
    return {"n": len(scored), "cer": round(ce / cn, 3) if cn else None, "wer": round(we / wn, 3) if wn else None,
            "ref_letters": cn}


def _gap_stats(recs: list[dict[str, Any]]) -> dict[str, Any]:
    t = h = hit = 0
    for r in recs:
        if r.get("reading") is None:
            continue
        a, b = len(GAP_RE.findall(r["truth"])), len(GAP_RE.findall(r["reading"]))
        t, h, hit = t + a, h + b, hit + min(a, b)
    return {"truth_gaps": t, "read_gaps": h, "recall": round(hit / t, 3) if t else None,
            "precision": round(hit / h, 3) if h else None}


def _fmt(x: Any) -> str:
    return "n/a" if x is None else (f"{x:.3f}" if isinstance(x, float) else str(x))


def cmd_report(args: argparse.Namespace) -> None:
    synth = [json.loads(x) for x in Path(args.synth).read_text(encoding="utf-8").splitlines()] if args.synth else []
    real = [json.loads(x) for x in Path(args.real).read_text(encoding="utf-8").splitlines()] if args.real else []
    usage = {}
    for p in (args.synth, args.real):
        if p and Path(p + ".meta.json").exists():
            usage[Path(p).name] = json.loads(Path(p + ".meta.json").read_text())
    tam = [r for r in synth if r["rendered_script"] == "tamil"]
    out: dict[str, Any] = {"synthetic": {}, "real": {}, "usage": usage}
    s = out["synthetic"]
    s["all_tamil_vs_edition"] = _agg(tam, "truth")
    s["all_tamil_vs_visible"] = _agg(tam, "truth_visible")
    s["by_level"] = {lv: _agg([r for r in tam if r["level"] == lv], "truth") for lv in LEVELS}
    s["by_level_visible"] = {lv: _agg([r for r in tam if r["level"] == lv], "truth_visible") for lv in LEVELS}
    photo = [r for r in synth if r["level"] == "photo"]
    s["by_script_photo_level"] = {sc: _agg([r for r in photo if r["rendered_script"] == sc
                                            and r["plate"] in {x["plate"] for x in synth
                                                               if x["rendered_script"] != "tamil"}], "truth")
                                  for sc in ("tamil", "tamil-brahmi", "grantha")}
    s["by_dynasty"] = {d: _agg([r for r in tam if r["dynasty"] == d], "truth")
                       for d in sorted({r["dynasty"] for r in tam})}
    s["gaps_by_level"] = {lv: _gap_stats([r for r in tam if r["level"] == lv]) for lv in LEVELS}
    conf: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in synth:
        if r.get("script_guess"):
            conf[r["rendered_script"]][r["script_guess"]["script"]] += 1
    s["script_confusion"] = {k: dict(v) for k, v in conf.items()}
    s["escalated"] = sum(1 for r in synth if r.get("escalated"))
    s["escalation_skipped"] = sum(1 for r in synth if r.get("escalation_skipped"))
    s["errors"] = sum(1 for r in synth if r.get("error"))
    secs = sorted(r["seconds"] for r in synth if r.get("reading") is not None)
    s["seconds_p50_p90"] = [secs[len(secs) // 2], secs[int(len(secs) * 0.9)]] if secs else None
    # confidence vs CER (is the self-reported confidence useful for the escalation threshold?)
    lo = [r for r in tam if r.get("confidence") is not None and r["confidence"] < 0.6]
    hi = [r for r in tam if r.get("confidence") is not None and r["confidence"] >= 0.6]
    s["cer_by_confidence"] = {"below_0.6": _agg(lo, "truth"), "at_or_above_0.6": _agg(hi, "truth")}

    rows = []
    for r in real:
        ref = r["reference"]
        if r.get("reference_kind") == "partial-window" and r.get("reading"):
            ref = best_window(ref, r["reading"])
        e, n = cer_counts(ref, r.get("reading") or "") if r.get("reading") is not None else (None, None)
        rows.append({"id": r["id"], "script": r.get("script"), "kind": r.get("kind"), "licence": r.get("licence"),
                     "cer": round(e / n, 3) if n else None, "ref_letters": n, "model": r.get("model"),
                     "escalated": r.get("escalated"), "confidence": r.get("confidence"),
                     "script_guess": (r.get("script_guess") or {}).get("script"), "error": r.get("error"),
                     "reading": (r.get("reading") or "")[:160], "reference": letters(ref)[:160],
                     "seconds": r.get("seconds")})
    out["real"] = {"images": rows}
    ce = sum(round(x["cer"] * x["ref_letters"]) for x in rows if x["cer"] is not None)
    cn = sum(x["ref_letters"] for x in rows if x["cer"] is not None)
    ins = [x for x in rows if x["kind"] != "printed" and x["cer"] is not None]
    pr = [x for x in rows if x["kind"] == "printed" and x["cer"] is not None]
    out["real"]["micro_cer"] = round(ce / cn, 3) if cn else None
    out["real"]["inscriptions_mean_cer"] = round(sum(x["cer"] for x in ins) / len(ins), 3) if ins else None
    out["real"]["printed_mean_cer"] = round(sum(x["cer"] for x in pr) / len(pr), 3) if pr else None
    Path(args.out + ".json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "real"} | {"real": {k: v for k, v in out["real"].items()
                                                                               if k != "images"}}, indent=2,
                     ensure_ascii=False))


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ezhuthu.eval.ocr", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("synth")
    a.add_argument("--plates", type=int, default=24)
    a.add_argument("--other-scripts", type=int, default=6, help="plates also rendered in Tamil-Brahmi and Grantha")
    a.add_argument("--seed", type=int, default=7)
    a.add_argument("--out", default=str(CACHE / "synth"))
    a.set_defaults(fn=cmd_synth)
    a = sub.add_parser("fetch-real")
    a.set_defaults(fn=cmd_fetch_real)
    a = sub.add_parser("run")
    a.add_argument("--set", choices=("synth", "real"), required=True)
    a.add_argument("--items", default=str(CACHE / "synth" / "items.jsonl"))
    a.add_argument("--manifest", default=str(REAL_MANIFEST), help="real-image manifest (--set real)")
    a.add_argument("--router", choices=("routed", "sonnet", "opus"), default="routed")
    a.add_argument("--max-live-calls", type=int, required=True)
    a.add_argument("--rpm", type=float, default=20)
    a.add_argument("--workers", type=int, default=4)
    a.add_argument("--limit", type=int)
    a.add_argument("--out", required=True)
    a.set_defaults(fn=cmd_run)
    a = sub.add_parser("report")
    a.add_argument("--synth")
    a.add_argument("--real")
    a.add_argument("--out", required=True)
    a.set_defaults(fn=cmd_report)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main(sys.argv[1:])
