"""Build expert-validation packets: seeded sample, AI proposals, blinded rating and reading-study sheets.

Three steps (see docs/expert-validation/PROTOCOL.md):

1. :func:`sample_items` picks, with a fixed seed, *blank* passages from ``benchmark/blank.jsonl`` (no expert
   fill exists), *masked* restorations from ``benchmark/items.test.jsonl`` (the edition's fill is known) and a
   disjoint set of masked restorations for the with/without-AI reading study.
2. :func:`propose` runs the restorer on each sampled passage and records its ranked proposals
   (``proposals.jsonl``). Retrieval uses the train-only corpus and the ontology is OFF (the ontology build
   reads val/test text). The LLM is used only with ``EZHUTHU_LIVE=1``; otherwise proposals come from
   retrieval and the character n-gram model only, and the packet says so.
3. :func:`build_packet` mixes, for every rating item, the same number of options (masked: the edition's fill
   plus AI proposals; blank: AI proposals only), puts them in a seeded random order under the labels
   A, B, C, ... and writes the sheets. Which option came from where is only in ``key.json``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..corpus.script import iso_to_tamil_display, strip_editorial_marks
from ..corpus.script import normalise_for_scoring as letters

KIT_VERSION = "1"
LABELS = "ABCDEFGH"
SCALE = (1, 2, 3, 4)
GAP_MARKER_RE = re.compile(r"\[\?\d*\]")

# Columns of the sheets that raters fill in. Order matters for the CSV.
RATING_COLUMNS = ["rater_id", "item_code", "option", "gap_letters", "context_tamil", "context_iso",
                  "proposal_tamil", "proposal_iso", "line_with_proposal_tamil", "source_url",
                  "rating_1_to_4", "cannot_judge_y", "consulted_edition_before_rating_y", "knew_this_text_y",
                  "comment"]
READING_COLUMNS = ["rater_id", "form", "block", "item_code", "condition", "gap_letters", "context_tamil",
                   "context_iso", "ai_suggestions_tamil", "ai_suggestions_iso", "source_url",
                   "your_restoration", "your_confidence_1_to_4", "seconds_taken",
                   "consulted_edition_before_answering_y", "knew_this_text_y", "comment"]
# Values that must never appear in a sheet raters see (tests check this).
HIDDEN_FIELDS = ("origin", "sources", "confidence", "kind", "id", "inscription_id", "target")


# ------------------------------------------------------------------------------------------------ io --------
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in Path(path).read_text(encoding="utf-8").splitlines() if ln.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as fh:
        fh.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def sha12(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


# -------------------------------------------------------------------------------------------- display -------
def display_iso(text: str) -> str:
    """One spelling for every option, so the edition's typography (hyphens, ``=``, capitalised vowels)
    does not tell the edition's fill apart from a machine proposal. Apostrophes (elided vowels) stay."""
    t = strip_editorial_marks(text or "").replace("-", "").replace("·", "")
    return re.sub(r"\s+", " ", t).strip().lower()


def context_iso(left: str, right: str, gap_letters: int) -> str:
    return f"{left.rstrip()} ⟦… {gap_letters} …⟧ {right.lstrip()}".strip()


def context_tamil(left: str, right: str, gap_letters: int) -> str:
    return f"{iso_to_tamil_display(left).rstrip()} ⟦… {gap_letters} …⟧ {iso_to_tamil_display(right).lstrip()}".strip()


def filled_tamil(left: str, fill: str, right: str) -> str:
    return (f"{iso_to_tamil_display(left).rstrip()} ⟦{iso_to_tamil_display(fill)}⟧ "
            f"{iso_to_tamil_display(right).lstrip()}").strip()


def context_letters(text: str) -> int:
    return len(letters(GAP_MARKER_RE.sub(" ", text)))


# --------------------------------------------------------------------------------------------- sample -------
@dataclass(frozen=True)
class SampleSpec:
    seed: int = 2026
    n_blank: int = 14
    n_masked: int = 14
    n_reading: int = 12
    min_gap: int = 2
    max_gap: int = 12
    min_context_letters: int = 15
    max_context_gaps: int = 3
    max_per_inscription: int = 2
    blank_splits: tuple[str, ...] = ("test", "val")
    age_share: float = 0.3  # share of masked/reading items drawn from the age set (Pallava + Uttiramerur)
    spares: int = 3  # extra rating items per role, used in order when an item has too few distinct proposals


def _eligible(rec: dict[str, Any], spec: SampleSpec) -> bool:
    g = int(rec.get("gap_chars") or 0)
    if not spec.min_gap <= g <= spec.max_gap:
        return False
    ctx = f"{rec.get('left', '')} {rec.get('right', '')}"
    if context_letters(ctx) < spec.min_context_letters:
        return False
    return len(GAP_MARKER_RE.findall(ctx)) <= spec.max_context_gaps


def _take(pool: list[dict[str, Any]], n: int, used: Counter, spec: SampleSpec, taken_ids: set[str]) -> list[dict]:
    out: list[dict[str, Any]] = []
    for r in pool:
        if len(out) >= n:
            break
        if r["id"] in taken_ids or used[r["inscription_id"]] >= spec.max_per_inscription:
            continue
        out.append(r)
        used[r["inscription_id"]] += 1
        taken_ids.add(r["id"])
    return out


def sample_items(benchmark_dir: Path, spec: SampleSpec) -> list[dict[str, Any]]:
    """Seeded sample. Every record gets ``role``: ``rating-blank`` | ``rating-masked`` | ``reading``."""
    rng = random.Random(spec.seed)
    blank = [r for r in read_jsonl(benchmark_dir / "blank.jsonl")
             if r.get("kind") == "blank" and r.get("split") in spec.blank_splits and _eligible(r, spec)]
    masked = [r for r in read_jsonl(benchmark_dir / "items.test.jsonl")
              if r.get("kind", "supplied") != "blank" and letters(r.get("target", "")) and _eligible(r, spec)]
    blank.sort(key=lambda r: r["id"])
    masked.sort(key=lambda r: r["id"])
    rng.shuffle(blank)
    rng.shuffle(masked)
    age = [r for r in masked if r.get("age_set")]
    rest = [r for r in masked if not r.get("age_set")]
    used: Counter = Counter()
    taken: set[str] = set()
    out: list[dict[str, Any]] = []
    for i, r in enumerate(_take(blank, spec.n_blank + spec.spares, used, spec, taken)):
        out.append({**r, "role": "rating-blank", "spare": i >= spec.n_blank})
    for role, n, extra in (("rating-masked", spec.n_masked, spec.spares), ("reading", spec.n_reading, 0)):
        n_age = round(n * spec.age_share)
        got = _take(age, n_age, used, spec, taken)
        got += _take(rest, n - len(got), used, spec, taken)
        if len(got) < n:  # not enough non-age items: top up from the age set
            got += _take(age, n - len(got), used, spec, taken)
        got += _take(rest + age, extra, used, spec, taken)
        out.extend({**r, "role": role, "spare": i >= n} for i, r in enumerate(got))
    short = {role: n - sum(1 for r in out if r["role"] == role and not r["spare"])
             for role, n in (("rating-blank", spec.n_blank), ("rating-masked", spec.n_masked),
                             ("reading", spec.n_reading))}
    if any(v > 0 for v in short.values()):
        raise ValueError(f"not enough eligible items: short by {short}")
    return out


# -------------------------------------------------------------------------------------------- propose -------
def propose(sample: list[dict[str, Any]], *, router: str, max_llm_calls: int = 40,
            k: int = 8) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run the restorer (ontology OFF, train-only retrieval, decider refused so the ranking is the flagged
    fallback: LLM self-report, else retrieval heuristic). Returns ``(rows, meta)``."""
    from ..agent.config import live_enabled
    from ..eval.decider_bench import PROPOSE_MAX_TOKENS, FreezingRestorer

    llm = None
    if router != "none":
        if not live_enabled():
            raise RuntimeError(f"router {router!r} calls Bedrock: set EZHUTHU_LIVE=1 (or use --router none)")
        if len(sample) > max_llm_calls:
            raise RuntimeError(f"{len(sample)} passages would need up to {len(sample)} LLM calls; "
                               f"the cap is {max_llm_calls} (--max-llm-calls)")
        from ..agent.llm import BedrockLLM

        llm = BedrockLLM()
    restorer = FreezingRestorer(llm=llm, use_ontology=False)
    rows: list[dict[str, Any]] = []
    for rec in sample:
        row: dict[str, Any] = {"id": rec["id"], "role": rec["role"]}
        for attempt in range(3):
            try:
                g = restorer.restore_gap(rec["left"], rec["right"], int(rec["gap_chars"]), router=router,
                                         max_candidates=k, exclude_inscription=rec["inscription_id"],
                                         dynasty=rec.get("dynasty"))
                row["proposals"] = [{"text": c.text, "confidence": round(c.confidence, 4),
                                     "sources": sorted(c.sources)} for c in g.candidates]
                row["ranking"] = g.decider_model
                row["models_used"] = g.models_used
                row.pop("error", None)
                break
            except Exception as exc:  # noqa: BLE001 - throttling etc.: retry, then record
                row["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                row["proposals"] = []
        rows.append(row)
    meta = {"router": router, "use_ontology": False, "retrieval": "benchmark/corpus_lines.jsonl (train only)",
            "ranking": "decider refused on purpose: fallback (LLM self-report, else retrieval heuristic)",
            "propose_max_tokens": PROPOSE_MAX_TOKENS if llm else None,
            "llm": llm.config.model_id("default") if llm else None,
            "usage": llm.ledger.to_dict() if llm else None, "errors": sum(1 for r in rows if r.get("error"))}
    return rows, meta


# ---------------------------------------------------------------------------------------------- build -------
def _ai_options(proposals: list[dict[str, Any]], exclude: set[str], n: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen = set(exclude)
    for p in proposals:
        shown = display_iso(p.get("text", ""))
        key = letters(shown)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append({"text": shown, "origin": "ai", "sources": list(p.get("sources", [])),
                    "confidence": p.get("confidence"), "ai_rank": proposals.index(p) + 1})
        if len(out) == n:
            break
    return out


def build_packet(sample: list[dict[str, Any]], proposals: list[dict[str, Any]], *, seed: int,
                 options_per_item: int = 3, reading_suggestions: int = 3,
                 provenance: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return ``{"meta", "rating": [...], "reading": [...], "dropped": [...]}`` (this is ``key.json``).
    Every rating item has exactly ``options_per_item`` options whatever its kind."""
    if not 2 <= options_per_item <= len(LABELS):
        raise ValueError(f"options_per_item must be 2..{len(LABELS)}")
    by_id = {p["id"]: p for p in proposals}
    wanted = Counter(r["role"] for r in sample if not r.get("spare"))
    have: Counter = Counter()
    unused: list[str] = []
    rating: list[dict[str, Any]] = []
    reading: list[dict[str, Any]] = []
    dropped: list[dict[str, str]] = []
    for rec in sorted(sample, key=lambda r: bool(r.get("spare"))):  # stable: main items first, then spares
        if have[rec["role"]] >= wanted[rec["role"]]:
            unused.append(rec["id"])
            continue
        props = by_id.get(rec["id"], {}).get("proposals", [])
        base = {k: rec.get(k) for k in ("id", "inscription_id", "collection", "split", "line_n", "left", "right",
                                       "gap_chars", "hard", "age_set", "dynasty", "source_url")}
        if rec["role"] == "rating-masked":
            target = display_iso(rec["target"])
            ai_keys = {letters(display_iso(p.get("text", ""))) for p in props}
            expert = {"text": target, "origin": "expert", "sources": ["edition"], "confidence": None,
                      "also_proposed_by_ai": letters(target) in ai_keys}
            ai = _ai_options(props, {letters(target)}, options_per_item - 1)
            options = [expert, *ai]
            kind = "masked"
        elif rec["role"] == "rating-blank":
            options = _ai_options(props, set(), options_per_item)
            kind = "blank"
        elif rec["role"] == "reading":
            sugg = _ai_options(props, set(), reading_suggestions)
            reading.append({**base, "kind": "masked", "target": rec["target"], "suggestions": sugg})
            have["reading"] += 1
            continue
        else:
            raise ValueError(f"unknown role {rec['role']!r}")
        if len(options) < options_per_item:
            dropped.append({"id": rec["id"], "role": rec["role"],
                            "reason": f"only {len(options)} distinct options (need {options_per_item})"})
            continue
        rating.append({**base, "kind": kind, "target": rec.get("target") or None, "options": options})
        have[rec["role"]] += 1
    rng = random.Random(f"{seed}:codes")
    rng.shuffle(rating)
    for i, it in enumerate(rating, 1):
        it["code"] = f"P{i:02d}"
        rng_i = random.Random(f"{seed}:{it['code']}:order")
        rng_i.shuffle(it["options"])
        for lab, opt in zip(LABELS, it["options"], strict=False):
            opt["label"] = lab
    rng.shuffle(reading)
    half = len(reading) // 2
    for i, it in enumerate(reading, 1):
        it["code"] = f"S{i:02d}"
        it["half"] = "H1" if i <= half else "H2"
    meta = {"kit_version": KIT_VERSION, "seed": seed, "options_per_item": options_per_item,
            "reading_suggestions": reading_suggestions, "scale": list(SCALE),
            "n_rating": len(rating), "n_rating_masked": sum(1 for r in rating if r["kind"] == "masked"),
            "n_rating_blank": sum(1 for r in rating if r["kind"] == "blank"), "n_reading": len(reading),
            **(provenance or {})}
    meta["short"] = {r: wanted[r] - have[r] for r in wanted if have[r] < wanted[r]}
    return {"meta": meta, "rating": rating, "reading": reading, "dropped": dropped, "unused_spares": unused}


# --------------------------------------------------------------------------------------------- sheets -------
def reading_forms(key: dict[str, Any]) -> dict[str, list[tuple[str, str, dict[str, Any]]]]:
    """Counterbalanced forms. Each form lists (block, condition, item). The unaided block always comes first,
    so AI suggestions cannot teach the rater anything before an unaided answer."""
    h1 = [it for it in key["reading"] if it["half"] == "H1"]
    h2 = [it for it in key["reading"] if it["half"] == "H2"]
    return {
        "A": [("1", "unaided", it) for it in h1] + [("2", "ai_assisted", it) for it in h2],
        "B": [("1", "unaided", it) for it in h2] + [("2", "ai_assisted", it) for it in h1],
    }


def form_for(rater_index: int) -> str:
    return "A" if rater_index % 2 == 0 else "B"


def rating_rows(key: dict[str, Any], rater: str) -> list[dict[str, str]]:
    seed = key["meta"]["seed"]
    items = list(key["rating"])
    random.Random(f"{seed}:{rater}:items").shuffle(items)
    rows: list[dict[str, str]] = []
    for it in items:
        g = int(it["gap_chars"])
        for opt in it["options"]:
            rows.append({
                "rater_id": rater, "item_code": it["code"], "option": opt["label"], "gap_letters": str(g),
                "context_tamil": context_tamil(it["left"], it["right"], g),
                "context_iso": context_iso(it["left"], it["right"], g),
                "proposal_tamil": iso_to_tamil_display(opt["text"]), "proposal_iso": opt["text"],
                "line_with_proposal_tamil": filled_tamil(it["left"], opt["text"], it["right"]),
                "source_url": it["source_url"], "rating_1_to_4": "", "cannot_judge_y": "",
                "consulted_edition_before_rating_y": "", "knew_this_text_y": "", "comment": "",
            })
    return rows


def _suggestion_text(sugg: list[dict[str, Any]], tamil: bool) -> str:
    parts = []
    for s in sugg:
        t = iso_to_tamil_display(s["text"]) if tamil else s["text"]
        conf = s.get("confidence")
        parts.append(f"{t} ({round(100 * conf)}%)" if isinstance(conf, (int, float)) else t)
    return " | ".join(parts)


def reading_rows(key: dict[str, Any], rater: str, form: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for block, cond, it in reading_forms(key)[form]:
        g = int(it["gap_chars"])
        aided = cond == "ai_assisted"
        rows.append({
            "rater_id": rater, "form": form, "block": block, "item_code": it["code"], "condition": cond,
            "gap_letters": str(g), "context_tamil": context_tamil(it["left"], it["right"], g),
            "context_iso": context_iso(it["left"], it["right"], g),
            "ai_suggestions_tamil": _suggestion_text(it["suggestions"], True) if aided else "",
            "ai_suggestions_iso": _suggestion_text(it["suggestions"], False) if aided else "",
            "source_url": it["source_url"], "your_restoration": "", "your_confidence_1_to_4": "",
            "seconds_taken": "", "consulted_edition_before_answering_y": "", "knew_this_text_y": "", "comment": "",
        })
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=columns, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    # UTF-8 with BOM so that Excel and LibreOffice open Tamil text correctly.
    path.write_text(buf.getvalue(), encoding="utf-8-sig")


def write_packet(key: dict[str, Any], raters: list[str], out: Path) -> dict[str, list[Path]]:
    """Write ``key.json`` (coordinator only), per-rater CSV and HTML sheets, and ``README.txt``."""
    from .render import rating_html, reading_html

    out.mkdir(parents=True, exist_ok=True)
    coord = out / "coordinator"
    coord.mkdir(exist_ok=True)
    (coord / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    written: dict[str, list[Path]] = defaultdict(list)
    assignments = []
    for i, rater in enumerate(raters):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", rater):
            raise ValueError(f"rater id {rater!r}: use 1-32 letters, digits, '-' or '_' (no names)")
        d = out / "raters" / rater
        rows = rating_rows(key, rater)
        write_csv(d / f"rating-{rater}.csv", RATING_COLUMNS, rows)
        (d / f"rating-{rater}.html").write_text(rating_html(key, rater, rows), encoding="utf-8")
        written["rating"] += [d / f"rating-{rater}.csv", d / f"rating-{rater}.html"]
        if key["reading"]:
            form = form_for(i)
            rrows = reading_rows(key, rater, form)
            write_csv(d / f"reading-{rater}.csv", READING_COLUMNS, rrows)
            (d / f"reading-{rater}.html").write_text(reading_html(key, rater, form, rrows), encoding="utf-8")
            written["reading"] += [d / f"reading-{rater}.csv", d / f"reading-{rater}.html"]
            assignments.append({"rater_id": rater, "reading_form": form})
        else:
            assignments.append({"rater_id": rater, "reading_form": None})
    (coord / "assignments.json").write_text(json.dumps(assignments, indent=1), encoding="utf-8")
    return dict(written)
