"""Build the Ezhuthu restoration benchmark from the pinned DHARMA checkout.

    python -m ezhuthu.corpus.fetch             # once: data/raw at the commits in config/dharma.lock.json
    python -m ezhuthu.corpus.build_benchmark   # writes benchmark/

Outputs (all JSONL is UTF-8, one record per line, sorted for stable diffs):

* ``items.{train,val,test}.jsonl``: restoration items (``contracts/benchmark-item.schema.json``), one per
  ``<supplied reason="lost|undefined">`` span in a Tamil-language line. Splits are by inscription.
* ``items.test-hard.jsonl``: test items with ``hard: true``.
* ``items.test-age.jsonl``: test items with ``age_set: true`` (Pallava + Uttiramerur collections).
* ``blank.jsonl``: ``kind: blank`` items, one per ``<gap>`` of a known number of characters that the
  editors did not fill (discovery set; no target to score).
* ``corpus_lines.jsonl``: every line of every TRAIN inscription (retrieval corpus).
* ``inscriptions.jsonl``: metadata and full text for every inscription (all splits), for the tutor.
* ``stats.json`` and ``DATA_CARD.md``: counts from this run.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

from ezhuthu.corpus.epidoc import Inscription, Line, Span, parse_file
from ezhuthu.corpus.fetch import LOCK_PATH, RAW_DIR, ROOT, edition_files, load_lock
from ezhuthu.corpus.script import GAP_MARKER_RE, count_aksharas, iso_to_tamil

OUT_DIR = ROOT / "benchmark"
SEED = 13
SPLIT_FRACTIONS = {"val": 0.1, "test": 0.1}
AGE_SET_COLLECTIONS = frozenset({"tfa-pallava-epigraphy", "tfa-uttiramerur-epigraphy"})
BLANK_REASONS = frozenset({"lost", "illegible", "undefined"})
SHORT_CONTEXT = 40  # chars; below this the previous / next line is added to the context
HARD_WINDOW = 15  # chars of context on each side of the target used for the parallel search
HARD_THRESHOLD = 90  # rapidfuzz partial_ratio
HARD_SLACK = 3  # extra chars on each side of a train window, so partial_ratio can re-align
GAP_BUCKETS = [(1, 1), (2, 2), (3, 3), (4, 4), (5, 5), (6, 10), (11, 20), (21, 10**9)]


@dataclass
class Source:
    repo: str
    commit: str
    relpath: str

    @property
    def url(self) -> str:
        return f"https://github.com/erc-dharma/{self.repo}/blob/{self.commit}/{self.relpath}"


def is_tamil(lang: str | None) -> bool:
    return bool(lang) and lang.startswith("tam")


# --------------------------------------------------------------------------------------------------
# loading and splitting


def load_corpus(lock: dict, raw_dir: Path,
                duplicates: list[str] | None = None) -> tuple[list[Inscription], dict[str, Source]]:
    """Parse every edition of every locked repo. A file whose id was already seen in an earlier repo
    (lock order) is skipped and its ``repo/path`` is appended to ``duplicates``."""
    inscriptions: list[Inscription] = []
    sources: dict[str, Source] = {}
    for entry in lock["repos"]:
        repo_dir = raw_dir / entry["repo"]
        if not repo_dir.exists():
            raise SystemExit(f"{repo_dir} missing: run `python -m ezhuthu.corpus.fetch` first")
        for path in edition_files(repo_dir):
            ins = parse_file(path, collection=entry["repo"])
            if ins is None:
                continue
            if ins.id in sources:
                if duplicates is not None:
                    duplicates.append(f"{entry['repo']}/{path.relative_to(repo_dir).as_posix()}")
                continue
            inscriptions.append(ins)
            sources[ins.id] = Source(entry["repo"], entry["commit"], path.relative_to(repo_dir).as_posix())
    inscriptions.sort(key=lambda i: i.id)
    return inscriptions, sources


def assign_splits(inscriptions: list[Inscription], seed: int = SEED) -> dict[str, str]:
    """80/10/10 by inscription, stratified by collection, deterministic for a given seed."""
    by_col: dict[str, list[str]] = collections.defaultdict(list)
    for ins in inscriptions:
        by_col[ins.collection or ""].append(ins.id)
    rng = random.Random(seed)
    split: dict[str, str] = {}
    for col in sorted(by_col):
        ids = sorted(by_col[col])
        rng.shuffle(ids)
        n_test = round(len(ids) * SPLIT_FRACTIONS["test"])
        n_val = round(len(ids) * SPLIT_FRACTIONS["val"])
        for k, iid in enumerate(ids):
            split[iid] = "test" if k < n_test else "val" if k < n_test + n_val else "train"
    return split


# --------------------------------------------------------------------------------------------------
# items


def _masked_range(line: Line, a: int, b: int) -> str:
    """line.text[a:b] with every supplied span inside it replaced by its gap marker."""
    out: list[str] = []
    pos = a
    for s in sorted(line.spans_of("supplied"), key=lambda s: s.start):
        if s.end <= a or s.start >= b:
            continue
        out.append(line.text[pos:s.start])
        out.append(f"[?{max(1, count_aksharas(line.text[s.start:s.end]))}]")
        pos = s.end
    out.append(line.text[pos:b])
    return "".join(out)


def contexts(lines: list[Line], idx: int, span: Span) -> tuple[str, str]:
    """Left/right context for a span: same line, plus the neighbouring line when short.

    Other restorations in the context are masked as ``[?N]``, exactly as a user would type them.
    """
    line = lines[idx]
    left = _masked_range(line, 0, span.start)
    right = _masked_range(line, span.end, len(line.text))
    if len(left.strip()) < SHORT_CONTEXT and idx > 0:
        prev = lines[idx - 1]
        sep = "" if line.joined else " "
        left = _masked_range(prev, 0, len(prev.text)) + sep + left
    if len(right.strip()) < SHORT_CONTEXT and idx + 1 < len(lines):
        nxt = lines[idx + 1]
        sep = "" if nxt.joined else " "
        right = right + sep + _masked_range(nxt, 0, len(nxt.text))
    return left, right


def make_items(ins: Inscription, split: str, source: Source,
               skipped: collections.Counter) -> tuple[list[dict], list[dict]]:
    items: list[dict] = []
    blanks: list[dict] = []
    for idx, line in enumerate(ins.lines):
        if not is_tamil(line.lang):
            continue
        k = 0
        for span in sorted(line.spans, key=lambda s: s.start):
            if span.kind == "supplied":
                target = line.text[span.start:span.end]
                if GAP_MARKER_RE.search(target):
                    skipped["supplied_contains_gap"] += 1
                    continue
                n_chars = count_aksharas(target)
                if n_chars < 1:
                    skipped["supplied_no_letters"] += 1
                    continue
                kind = "supplied"
            elif (span.kind == "gap" and span.reason in BLANK_REASONS and span.quantity
                  and span.unit == "character"):
                target, n_chars, kind = "", span.quantity, "blank"
            else:
                continue
            left, right = contexts(ins.lines, idx, span)
            rec = {
                "id": f"{ins.id}:{line.n}:{k}",
                "inscription_id": ins.id,
                "collection": ins.collection,
                "dynasty": ins.dynasty,
                "age_set": ins.collection in AGE_SET_COLLECTIONS,
                "split": split,
                "line_n": line.n,
                "left": left,
                "right": right,
                "target": target,
                "gap_chars": n_chars,
                "hard": False,
                "kind": kind,
                "reason": span.reason,
                "lang": line.lang,
                "source_url": source.url,
            }
            k += 1
            (items if kind == "supplied" else blanks).append(rec)
    return items, blanks


# --------------------------------------------------------------------------------------------------
# hard flag


_MATCH_STRIP = re.compile(r"[\s\-’'·]+")


def norm_for_match(text: str) -> str:
    """Lower-case, gap markers -> '#', drop spaces / hyphens / apostrophes / engraved-puḷḷi dots."""
    return _MATCH_STRIP.sub("", GAP_MARKER_RE.sub("#", text.lower()))


_PAD = "\x00"


def _target_windows(train_texts: list[tuple[str, str]], tgt: str, window: int) -> dict[str, set[str]]:
    """Every occurrence of ``tgt`` in the train texts as a window of ``window + HARD_SLACK`` chars on
    each side (padded at text edges) -> the inscriptions it occurs in."""
    out: dict[str, set[str]] = collections.defaultdict(set)
    w = window + HARD_SLACK
    pad = _PAD * w
    for owner, text in train_texts:
        padded = pad + text + pad
        start = padded.find(tgt, w)
        while start != -1 and start < w + len(text):
            out[padded[start - w:start + len(tgt) + w]].add(owner)
            start = padded.find(tgt, start + 1)
    return out


def mark_hard(items: list[dict], train_texts: list[tuple[str, str]],
              window: int = HARD_WINDOW, threshold: int = HARD_THRESHOLD) -> None:
    """Set ``hard`` on every item.

    ``train_texts`` is ``(inscription_id, norm_for_match(full text))`` for the TRAIN inscriptions; a
    whole inscription is one string so that parallels running across line breaks are found.

    An item is *not* hard when some train inscription other than its own contains the target and the
    item's query (``window`` chars of left context, target, ``window`` chars of right context) scores
    rapidfuzz ``partial_ratio >= threshold`` against the text around that occurrence (the same window
    plus ``HARD_SLACK`` chars each side, so the alignment stays on the target).
    """
    cache: dict[str, tuple[list[str], list[set[str]]]] = {}
    for it in items:
        tgt = norm_for_match(it["target"])
        if not tgt:
            it["hard"] = False
            continue
        if tgt not in cache:
            wins = _target_windows(train_texts, tgt, window)
            cache[tgt] = (list(wins), list(wins.values()))
        choices, owners = cache[tgt]
        # the query is not padded: an item with little context of its own is compared on what it has
        query = norm_for_match(it["left"])[-window:] + tgt + norm_for_match(it["right"])[:window]
        hits = process.extract(query, choices, scorer=fuzz.partial_ratio, score_cutoff=threshold, limit=None)
        own = it["inscription_id"]
        it["hard"] = not any(owners[idx] - {own} for _, _, idx in hits)


# --------------------------------------------------------------------------------------------------
# outputs


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def _bucket(n: int) -> str:
    for lo, hi in GAP_BUCKETS:
        if lo <= n <= hi:
            return str(lo) if lo == hi else (f"{lo}-{hi}" if hi < 10**9 else f"{lo}+")
    raise ValueError(n)


def _hist(items: list[dict]) -> dict[str, int]:
    c = collections.Counter(_bucket(it["gap_chars"]) for it in items)
    order = [_bucket(lo) for lo, _ in GAP_BUCKETS]
    return {b: c.get(b, 0) for b in order}


def inscription_record(ins: Inscription, split: str, source: Source) -> dict:
    tamil = is_tamil(ins.lang)
    n_sup = sum(len(ln.spans_of("supplied")) for ln in ins.lines)
    n_gap = sum(len(ln.spans_of("gap")) for ln in ins.lines)
    return {
        "id": ins.id,
        "title": ins.title,
        "collection": ins.collection,
        "split": split,
        "lang": ins.lang,
        "dynasty": ins.dynasty,
        "dynasty_source": ins.dynasty_source,
        "ruler": ins.ruler,
        "regnal_year": ins.regnal_year,
        "approx_date": ins.approx_date,
        "summary": ins.summary,
        "age_set": ins.collection in AGE_SET_COLLECTIONS,
        "licence": ins.licence,
        "licence_url": ins.licence_url,
        "n_lines": len(ins.lines),
        "n_supplied": n_sup,
        "n_gaps": n_gap,
        "source_url": source.url,
        "dharmalekha_url": f"https://dharmalekha.info/texts/{ins.id}",
        "commit": source.commit,
        "text_iso": ins.text,
        "text_tamil": iso_to_tamil(ins.text) if tamil else None,
    }


def build(lock: dict, raw_dir: Path, out_dir: Path, seed: int = SEED) -> dict:
    duplicates: list[str] = []
    inscriptions, sources = load_corpus(lock, raw_dir, duplicates)
    split = assign_splits(inscriptions, seed)
    skipped: collections.Counter = collections.Counter()
    items: list[dict] = []
    blanks: list[dict] = []
    for ins in inscriptions:
        it, bl = make_items(ins, split[ins.id], sources[ins.id], skipped)
        items += it
        blanks += bl

    train_ids = {i.id for i in inscriptions if split[i.id] == "train"}
    corpus_lines = []
    for ins in inscriptions:
        if ins.id not in train_ids:
            continue
        for ln in ins.lines:
            corpus_lines.append({
                "inscription_id": ins.id, "collection": ins.collection, "line_n": ln.n, "lang": ln.lang,
                "joined": ln.joined, "text": ln.text, "text_masked": ln.masked(),
                "source_url": sources[ins.id].url,
            })
    mark_hard(items, [(i.id, "".join(norm_for_match(ln.text) for ln in i.lines))
                      for i in inscriptions if i.id in train_ids])

    out_dir.mkdir(parents=True, exist_ok=True)
    by_split = {s: [it for it in items if it["split"] == s] for s in ("train", "val", "test")}
    for s, rows in by_split.items():
        _write_jsonl(out_dir / f"items.{s}.jsonl", rows)
    _write_jsonl(out_dir / "items.test-hard.jsonl", [it for it in by_split["test"] if it["hard"]])
    _write_jsonl(out_dir / "items.test-age.jsonl", [it for it in by_split["test"] if it["age_set"]])
    _write_jsonl(out_dir / "blank.jsonl", blanks)
    _write_jsonl(out_dir / "corpus_lines.jsonl", corpus_lines)
    _write_jsonl(out_dir / "inscriptions.jsonl",
                 [inscription_record(i, split[i.id], sources[i.id]) for i in inscriptions])

    stats = compute_stats(lock, inscriptions, split, items, blanks, corpus_lines, skipped, seed)
    stats["duplicate_files_skipped"] = duplicates
    (out_dir / "stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    (out_dir / "DATA_CARD.md").write_text(render_data_card(stats))
    return stats


def compute_stats(lock, inscriptions, split, items, blanks, corpus_lines, skipped, seed) -> dict:
    split_counts = collections.Counter(split.values())
    per_col = collections.defaultdict(lambda: collections.Counter())
    for ins in inscriptions:
        per_col[ins.collection]["inscriptions"] += 1
        per_col[ins.collection]["lines"] += len(ins.lines)
    for it in items:
        per_col[it["collection"]]["items"] += 1
    for b in blanks:
        per_col[b["collection"]]["blank"] += 1
    per_split = {}
    for s in ("train", "val", "test"):
        rows = [it for it in items if it["split"] == s]
        hard = sum(it["hard"] for it in rows)
        per_split[s] = {
            "inscriptions": split_counts.get(s, 0),
            "items": len(rows),
            "hard": hard,
            "hard_share": round(hard / len(rows), 4) if rows else 0.0,
            "age_set": sum(it["age_set"] for it in rows),
            "blank": sum(b["split"] == s for b in blanks),
        }
    return {
        "seed": seed,
        "pinned_at": lock.get("pinned_at"),
        "repos": [{k: e.get(k) for k in ("repo", "commit", "commit_date", "license", "tei_files")}
                  for e in lock["repos"]],
        "inscriptions": len(inscriptions),
        "inscriptions_tamil": sum(is_tamil(i.lang) for i in inscriptions),
        "inscriptions_with_items": len({it["inscription_id"] for it in items}),
        "inscriptions_damaged": sum(any(ln.spans_of("supplied") or ln.spans_of("gap") for ln in i.lines)
                                    for i in inscriptions),
        "supplied_spans_all": dict(collections.Counter(
            s.reason for i in inscriptions for ln in i.lines for s in ln.spans if s.kind in ("supplied", "omitted"))),
        "lines": sum(len(i.lines) for i in inscriptions),
        "items": len(items),
        "items_by_reason": dict(collections.Counter(it["reason"] for it in items)),
        "per_split": per_split,
        "age_set_items": sum(it["age_set"] for it in items),
        "age_set_inscriptions": sum(i.collection in AGE_SET_COLLECTIONS for i in inscriptions),
        "blank_items": len(blanks),
        "corpus_lines": len(corpus_lines),
        "gap_chars_hist": _hist(items),
        "gap_chars_hist_blank": _hist(blanks),
        "per_collection": {c: dict(v) for c, v in sorted(per_col.items())},
        "licences": dict(collections.Counter(i.licence or "(none in header)" for i in inscriptions)),
        "langs": dict(collections.Counter(i.lang or "(none)" for i in inscriptions)),
        "dynasty_sources": dict(collections.Counter(i.dynasty_source or "(unknown)" for i in inscriptions)),
        "skipped": dict(skipped),
        "hard_rule": {"window_chars": HARD_WINDOW, "partial_ratio_min": HARD_THRESHOLD,
                      "slack_chars": HARD_SLACK},
    }


def render_data_card(st: dict) -> str:
    ps = st["per_split"]
    lines = [
        "# Ezhuthu restoration benchmark: data card",
        "",
        "Generated by `python -m ezhuthu.corpus.build_benchmark` from the DHARMA repositories pinned in",
        f"`config/dharma.lock.json` (pinned {st['pinned_at']}). Every number below is from that run",
        "(also in `benchmark/stats.json`). Do not edit by hand; re-run the build.",
        "",
        "## Source and licence",
        "",
        "Text: [DHARMA](https://dharmalekha.info) project (ERC grant 809994), TEI/EpiDoc editions in the",
        "`erc-dharma/tfa-*-epigraphy` repositories. Credit: *DHARMA, \"The Domestication of 'Hindu'",
        "Asceticism and the Religious Making of South and Southeast Asia\"*, and the named editors of each",
        "file (see `source_url`).",
        "",
        "Licence: the repositories' LICENCE files say CC BY 4.0, but the edition files themselves declare",
        "the licence below in `<availability>`. Because most files say **CC BY-SA 4.0**, this derived",
        "benchmark is shared under **CC BY-SA 4.0** with attribution to DHARMA.",
        "",
        "| Licence in file header | Inscriptions |",
        "| --- | ---: |",
    ]
    for lic, n in sorted(st["licences"].items(), key=lambda kv: -kv[1]):
        lines.append(f"| {lic} | {n} |")
    lines += ["", "### Pinned commits", "", "| Repository | Commit | Licence (GitHub) | TEI editions |",
              "| --- | --- | --- | ---: |"]
    for r in st["repos"]:
        lines.append(f"| {r['repo']} | `{r['commit'][:12]}` | {r['license'] or 'none'} | {r['tei_files']} |")
    lines += [
        "",
        "## What an item is",
        "",
        "One item per expert restoration: a `<supplied reason=\"lost\">` or `<supplied reason=\"undefined\">`",
        "span in a Tamil-language line (`xml:lang` starting with `tam`). `target` is the editors' text,",
        "`left`/`right` are the rest of the line (plus the neighbouring line when that side is shorter than",
        f"{SHORT_CONTEXT} characters). Other restorations in the context are masked as `[?N]`, and lost text",
        "the editors did not restore appears as `[?N]` or `[?]`, as in `contracts/restore-api.md`.",
        "Text is ISO-15919 in the editorial reading (`reg`/`corr`/`expan`; scribal omissions supplied).",
        "",
        "`gap_chars` counts Tamil letters (uyir, mey and uyirmey; the DHARMA \"character\" unit).",
        "Fields `kind`, `reason` and `lang` are additions to the contract (allowed: the schema is open).",
        "",
        "## Counts",
        "",
        (f"- Inscriptions parsed: **{st['inscriptions']}** ({st['inscriptions_tamil']} with Tamil as main"
        f" language; {st['inscriptions_with_items']} have at least one item); lines: {st['lines']}."),
        f"- Restoration items: **{st['items']}** (by reason: "
        + ", ".join(f"{k} {v}" for k, v in sorted(st["items_by_reason"].items())) + ").",
        (f"- Age set (Pallava + Uttiramerur collections, the only set described as over 1,100 years old):"
        f" **{st['age_set_items']}** items from {st['age_set_inscriptions']} inscriptions."),
        f"- Blank set (`kind: blank`, `<gap>` of a known size with no expert fill): **{st['blank_items']}**.",
        f"- Retrieval corpus (`corpus_lines.jsonl`, train inscriptions only): {st['corpus_lines']} lines.",
        "",
        "| Split | Inscriptions | Items | Hard | Hard share | Age-set items | Blank |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for s in ("train", "val", "test"):
        p = ps[s]
        lines.append(f"| {s} | {p['inscriptions']} | {p['items']} | {p['hard']} | {p['hard_share']:.1%} |"
                     f" {p['age_set']} | {p['blank']} |")
    lines += [
        "",
        f"Splits are by inscription (seed {st['seed']}, 80/10/10 within each collection), so no",
        "inscription appears in two splits. `items.test-hard.jsonl` and `items.test-age.jsonl` are the",
        "hard and age subsets of the test split.",
        "",
        "**Hard** = no train inscription other than the item's own contains the target with a similar",
        (f"context: the item's query ({st['hard_rule']['window_chars']} characters of context on each side"
         " of the target; spaces, hyphens and apostrophes ignored) scores rapidfuzz `partial_ratio` >="
         f" {st['hard_rule']['partial_ratio_min']} against the text around some occurrence of the target"
         f" in that inscription (same window plus {st['hard_rule']['slack_chars']} characters each side;"
         " line breaks are crossed). Blank items are never hard (no target)."),
        "",
        "### Gap length (gap_chars)",
        "",
        "| Letters | Restoration items | Blank items |",
        "| --- | ---: | ---: |",
    ]
    for b, n in st["gap_chars_hist"].items():
        lines.append(f"| {b} | {n} | {st['gap_chars_hist_blank'][b]} |")
    lines += ["", "### Per collection", "", "| Collection | Inscriptions | Lines | Items | Blank |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for c, v in st["per_collection"].items():
        lines.append(f"| {c} | {v.get('inscriptions', 0)} | {v.get('lines', 0)} | {v.get('items', 0)} |"
                     f" {v.get('blank', 0)} |")
    sup_all = st["supplied_spans_all"]
    lines += [
        "",
        "## Compared with the charter's planning numbers",
        "",
        "`docs/CHARTER.md` was written before this build. These are the measured values:",
        "",
        "| Charter says | This build |",
        "| --- | --- |",
        f"| about 1,200 DHARMA editions | {st['inscriptions']} TEI editions parsed |",
        (f"| about 87% have damaged passages | {st['inscriptions_damaged']} of {st['inscriptions']}"
         f" ({st['inscriptions_damaged'] / max(1, st['inscriptions']):.0%}) have a restoration or a gap |"),
        (f"| about 12,900 expert restorations | {st['items']} scorable restorations in Tamil lines;"
         f" all `<supplied>` spans in all languages: {sum(sup_all.values())} ("
         + ", ".join(f"{k} {v}" for k, v in sorted(sup_all.items())) + ") |"),
        (f"| about 3,800 in inscriptions over 1,100 years old | {st['age_set_items']} restoration items in"
         " the Pallava + Uttiramerur collections |"),
    ]
    lines += [
        "",
        "## Known limits",
        "",
        "- Restorations are what DHARMA editors supplied; a model that reproduces them \"matches expert",
        "  restorations\". It is not proof that the reading is correct.",
        ("- `dynasty` comes from the collection (Pallava, Pandya) or from ruler names in the title"
        f" ({st['dynasty_sources'].get('title', 0)} inscriptions); it is null for"
        f" {st['dynasty_sources'].get('(unknown)', 0)}."),
        ("- Edition-specific marks that are not letters (for example `⌈`, `‡`, `=` and literal brackets)"
        " are kept exactly as in the source text."),
        "- `approx_date` is the first CE date in the edition commentary, when there is one.",
        "- Items skipped: " + (", ".join(f"{k} {v}" for k, v in sorted(st["skipped"].items())) or "none") + ".",
        "- Files skipped because the same inscription id was already loaded from an earlier repository: "
        + (", ".join(f"`{d}`" for d in st.get("duplicate_files_skipped", [])) or "none") + ".",
        "- Sanskrit, Prakrit and Pali lines are kept in `inscriptions.jsonl` and `corpus_lines.jsonl` but",
        "  give no items.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lock", type=Path, default=LOCK_PATH)
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args(argv)
    stats = build(load_lock(args.lock), args.raw, args.out, args.seed)
    print(json.dumps({k: stats[k] for k in ("inscriptions", "items", "blank_items", "age_set_items",
                                            "corpus_lines", "per_split")}, indent=2), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
