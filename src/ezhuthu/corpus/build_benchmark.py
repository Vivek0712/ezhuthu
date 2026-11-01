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
  ``text_iso`` / ``text_tamil`` inline the expert fills (they ARE the answers for val/test items);
  ``text_iso_masked`` / ``text_tamil_masked`` show every fill as ``[?N]``. See "Leakage" in the data
  card.
* ``stats.json`` and ``DATA_CARD.md``: counts from this run.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process

from ezhuthu.corpus.epidoc import Inscription, Line, Span, parse_file
from ezhuthu.corpus.fetch import LOCK_PATH, RAW_DIR, ROOT, edition_files, load_lock
from ezhuthu.corpus.script import GAP_MARKER_RE, count_aksharas, iso_to_tamil_display

OUT_DIR = ROOT / "benchmark"
SEED = 13
SPLIT_FRACTIONS = {"val": 0.1, "test": 0.1}
AGE_SET_COLLECTIONS = frozenset({"tfa-pallava-epigraphy", "tfa-uttiramerur-epigraphy"})
BLANK_REASONS = frozenset({"lost", "illegible", "undefined"})
SHORT_CONTEXT = 40  # chars; below this the previous / next line is added to the context
HARD_WINDOW = 15  # chars of context on each side of the target used for the parallel search
HARD_THRESHOLD = 90  # rapidfuzz partial_ratio
HARD_SLACK = 3  # extra chars on each side of a train window, so partial_ratio can re-align
DUP_RATIO = 95  # rapidfuzz ratio of normalised whole texts at or above which two editions are one stone
DUP_MIN_CHARS = 40  # texts shorter than this (normalised) are never grouped on text alone
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


def _norm_whole_text(ins: Inscription) -> str:
    return "".join(norm_for_match(ln.text) for ln in ins.lines)


def _site_ruler_year(ins: Inscription) -> tuple[str, str, int] | None:
    """(site, ruler, regnal year) from the title, ASCII-folded; None unless all three are known.

    DHARMA titles read ``"<site>, <monument>, time of <ruler>, year <n>"``.
    """
    if not (ins.title and ins.ruler and ins.regnal_year is not None):
        return None

    def fold(x: str) -> str:
        x = unicodedata.normalize("NFD", x)
        return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in x if not unicodedata.combining(c)).lower()).strip()

    site = fold(ins.title.split(",")[0])
    ruler = fold(ins.ruler)
    if not site or not ruler:
        return None
    return site, ruler, int(ins.regnal_year)


def edition_groups(inscriptions: list[Inscription], ratio: int = DUP_RATIO) -> list[list[str]]:
    """Groups (size >= 2) of editions that are the same inscription published in different collections.

    Two editions are linked when their normalised whole texts score rapidfuzz ``ratio >= ratio``
    (texts of at least ``DUP_MIN_CHARS`` letters), or when site, ruler and regnal year in the title
    all match. Links are closed transitively. Each group is sorted; groups are sorted by first id.
    """
    ids = [i.id for i in inscriptions]
    texts = [_norm_whole_text(i) for i in inscriptions]
    parent = list(range(len(ids)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    long_idx = [k for k, t in enumerate(texts) if len(t) >= DUP_MIN_CHARS]
    if len(long_idx) > 1:
        long_texts = [texts[k] for k in long_idx]
        scores = process.cdist(long_texts, long_texts, scorer=fuzz.ratio, score_cutoff=ratio,
                               dtype="uint8", workers=-1)
        for a, b in zip(*scores.nonzero(), strict=True):
            if a < b:
                union(long_idx[a], long_idx[b])
    by_key: dict[tuple, int] = {}
    for k, ins in enumerate(inscriptions):
        key = _site_ruler_year(ins)
        if key is None:
            continue
        if key in by_key:
            union(by_key[key], k)
        else:
            by_key[key] = k
    members: dict[int, list[str]] = collections.defaultdict(list)
    for k, iid in enumerate(ids):
        members[find(k)].append(iid)
    return sorted((sorted(m) for m in members.values() if len(m) > 1), key=lambda g: g[0])


def assign_splits(inscriptions: list[Inscription], seed: int = SEED,
                  groups: list[list[str]] | None = None) -> dict[str, str]:
    """80/10/10 by inscription, stratified by collection, deterministic for a given seed.

    Editions in one of ``groups`` (see :func:`edition_groups`) all take the split drawn for the
    group's first id, so two editions of one stone never end up in different splits.
    """
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
    for g in groups or []:
        for iid in g[1:]:
            split[iid] = split[g[0]]
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
              window: int = HARD_WINDOW, threshold: int = HARD_THRESHOLD,
              same_stone: dict[str, set[str]] | None = None) -> None:
    """Set ``hard`` on every item.

    ``train_texts`` is ``(inscription_id, norm_for_match(full text))`` for the TRAIN inscriptions; a
    whole inscription is one string so that parallels running across line breaks are found.

    An item is *not* hard when some train inscription other than its own contains the target and the
    item's query (``window`` chars of left context, target, ``window`` chars of right context) scores
    rapidfuzz ``partial_ratio >= threshold`` against the text around that occurrence (the same window
    plus ``HARD_SLACK`` chars each side, so the alignment stays on the target). Other editions of
    the item's own stone (``same_stone``: id -> all ids in its edition group) do not count as parallels.
    """
    same_stone = same_stone or {}
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
        own = same_stone.get(it["inscription_id"], {it["inscription_id"]})
        it["hard"] = not any(owners[idx] - own for _, _, idx in hits)


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


def masked_text(ins: Inscription) -> str:
    """``ins.text`` with every expert fill (``supplied`` lost/undefined) shown as ``[?N]``."""
    return "\n".join(("-" if ln.joined else "") + ln.masked() for ln in ins.lines)


def inscription_record(ins: Inscription, split: str, source: Source,
                       same_stone: list[str] | None = None) -> dict:
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
        "same_stone_as": same_stone or [],
        "text_iso": ins.text,
        "text_iso_masked": masked_text(ins),
        "text_tamil": iso_to_tamil_display(ins.text) if tamil else None,
        "text_tamil_masked": iso_to_tamil_display(masked_text(ins)) if tamil else None,
    }


def build(lock: dict, raw_dir: Path, out_dir: Path, seed: int = SEED) -> dict:
    duplicates: list[str] = []
    inscriptions, sources = load_corpus(lock, raw_dir, duplicates)
    groups = edition_groups(inscriptions)
    same_stone = {iid: set(g) for g in groups for iid in g}
    split = assign_splits(inscriptions, seed, groups)
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
    mark_hard(items, [(i.id, _norm_whole_text(i)) for i in inscriptions if i.id in train_ids],
              same_stone=same_stone)

    out_dir.mkdir(parents=True, exist_ok=True)
    by_split = {s: [it for it in items if it["split"] == s] for s in ("train", "val", "test")}
    for s, rows in by_split.items():
        _write_jsonl(out_dir / f"items.{s}.jsonl", rows)
    _write_jsonl(out_dir / "items.test-hard.jsonl", [it for it in by_split["test"] if it["hard"]])
    _write_jsonl(out_dir / "items.test-age.jsonl", [it for it in by_split["test"] if it["age_set"]])
    _write_jsonl(out_dir / "blank.jsonl", blanks)
    _write_jsonl(out_dir / "corpus_lines.jsonl", corpus_lines)
    _write_jsonl(out_dir / "inscriptions.jsonl",
                 [inscription_record(i, split[i.id], sources[i.id],
                                     sorted(same_stone.get(i.id, set()) - {i.id})) for i in inscriptions])

    stats = compute_stats(lock, inscriptions, split, items, blanks, corpus_lines, skipped, seed)
    stats["duplicate_files_skipped"] = duplicates
    stats["edition_groups"] = [{"ids": g, "split": split[g[0]]} for g in groups]
    stats["dup_rule"] = {"text_ratio_min": DUP_RATIO, "min_chars": DUP_MIN_CHARS,
                         "or_same_site_ruler_year": True}
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
        "benchmark is shared under **CC BY-SA 4.0** with attribution to DHARMA (see `benchmark/LICENSE`;",
        "the repository's Apache-2.0 licence covers the code, not the files in `benchmark/`).",
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
    pt = ps["test"]
    n_groups = len(st["edition_groups"])
    n_grouped = sum(len(g["ids"]) for g in st["edition_groups"])
    lines += [
        "",
        "## Leakage (read before building retrieval, lookups, prompts or reports)",
        "",
        "### How the splits are made",
        "",
        (f"Splits are by **inscription**, never by item: seed {st['seed']}, 80/10/10 within each"
         f" collection ({ps['train']['inscriptions']} train, {ps['val']['inscriptions']} val,"
         f" {pt['inscriptions']} test inscriptions). Every item and blank of an inscription takes its"
         " split, so no line, context or target of a val/test inscription is in a train file. Before"
         f" splitting, {n_grouped} editions are put in {n_groups} groups, each one stone published"
         " more than once (or one king, year and site; see \"Same stone, several editions\"), and a"
         " group always shares one split. A DHARMA file whose inscription id was already loaded from an"
         " earlier repository is dropped, not split separately."),
        "",
        "### How the hard set is defined",
        "",
        (f"An item is **hard** when no *train* inscription other than its own stone contains its target in"
         " a similar context (rapidfuzz `partial_ratio` >="
         f" {st['hard_rule']['partial_ratio_min']} on {st['hard_rule']['window_chars']} letters of"
         " context each side; full rule under Counts). The search reads train inscriptions only, so the"
         " hard flag never looks at val or test text. `items.test-hard.jsonl` holds the"
         f" {pt['hard']} hard test items; the other {pt['items'] - pt['hard']} test items"
         f" ({(pt['items'] - pt['hard']) / max(1, pt['items']):.1%}) have a close parallel in another"
         " train inscription: that is the formulaic overlap, measured rather than hidden. Report test-hard next to test"
         " so that a copy-from-parallel system is not mistaken for a restorer."),
        "",
        "### What may read what",
        "",
        "`inscriptions.jsonl` covers **all** splits so that the tutor can show any inscription. Its",
        "`text_iso` and `text_tamil` inline every expert fill, so for val and test inscriptions they",
        "**contain the answers** to `items.val.jsonl` and `items.test.jsonl`. Therefore:",
        "",
        "1. The restorer's retrieval corpus, the n-gram baseline, the ontology's `attested_in`",
        "   references, few-shot examples and any other lookup the restorer can see are built from",
        "   **train only** (`corpus_lines.jsonl`, or `inscriptions.jsonl` rows with `split == \"train\"`).",
        "   If a lookup needs all splits (for the tutor), tag every reference with its `split` and filter",
        "   out val/test on the restoration and evaluation paths.",
        "2. Where text of a val/test inscription must be shown next to a restoration task, use",
        "   `text_iso_masked` / `text_tamil_masked`: every expert fill appears there as `[?N]`.",
        "3. `same_stone_as` lists other editions of the same stone. They are always in the same split,",
        "   and they must not be used as parallels for each other.",
        "4. Thresholds (abstain, escalation) and prompt changes are tuned on val, never on test. This is a",
        "   convention, not a test: a threshold sweep on test (as in a report) describes a fixed system and",
        "   must not be used to pick its threshold.",
        "",
        "Rules 1 to 3 are enforced by tests in `make check`:",
        "",
        "| Rule | Code | Test |",
        "| --- | --- | --- |",
        ("| Retrieval corpus is train only | `build()` in `src/ezhuthu/corpus/build_benchmark.py` writes"
         " `corpus_lines.jsonl` from train ids | `tests/test_corpus_benchmark.py::test_real_subsets_and_stats_agree` |"),
        ("| A corpus with a val/test inscription refuses to load | `_load_corpus` in `src/ezhuthu/agent/data.py`"
         " raises `CorpusLeak` | `tests/agent/test_qa_review_fixes.py::test_corpus_with_held_out_inscription_refuses_to_load` |"),
        ("| Splits are by inscription and disjoint | `assign_splits` | `tests/test_corpus_benchmark.py::test_real_items_validate_and_splits_disjoint`,"
         " `tests/test_corpus_benchmark.py::test_splits_are_by_inscription_and_deterministic` |"),
        ("| Editions of one stone share a split | `edition_groups`, `assign_splits` |"
         " `tests/test_corpus_benchmark.py::test_edition_groups_share_a_split` |"),
        ("| Every val/test fill is masked in `text_iso_masked` | `masked_text` |"
         " `tests/test_corpus_benchmark.py::test_real_masked_text_hides_held_out_fills` |"),
        ("| Hard flag reads train only and ignores the item's own stone | `mark_hard` |"
         " `tests/test_corpus_benchmark.py::test_mark_hard`,"
         " `tests/test_corpus_benchmark.py::test_mark_hard_ignores_other_editions_of_its_stone` |"),
        ("| Ontology is built from train editions only | `split_filter` in `src/ezhuthu/ontology/build.py`"
         " (`--splits train`, the default) | `tests/ontology/test_artefacts.py::test_shipped_build_is_train_split_only`,"
         " `tests/ontology/test_splits.py::test_train_only_build_drops_held_out_editions` |"),
        ("| Evaluation never retrieves the item's own inscription | `exclude_inscription` in `src/ezhuthu/eval/run.py` |"
         " `tests/agent/test_text_retrieval.py::test_parallel_index_ranks_formula_and_excludes_own_inscription` |"),
        ("| This card matches the build | `render_data_card` |"
         " `tests/test_corpus_benchmark.py::test_data_card_matches_stats` |"),
        "",
        "### Known residual risks",
        "",
        ("- **Formulaic duplicates across inscriptions.** Grants repeat formulae (imprecations, lamp"
         " endowments, regnal preambles) across stones that are *different* inscriptions, so they are"
         " not grouped and can sit in different splits. The hard flag handles this for scoring (a target"
         " with a train parallel is not hard), but the full test score includes these items. Two"
         " editions of one stone whose texts score below the duplicate threshold and whose titles do not"
         " give site, ruler and year would also be missed by the grouping."),
        ("- **Editors' restorations are expert judgement, not ground truth.** A `<supplied>` span is"
         " what a DHARMA editor proposed, sometimes from a parallel the editor knew. A model that"
         " reproduces it \"matches expert restorations\"; a different fill is not proven wrong."),
        ("- **Unmasked text is shipped for the tutor.** `inscriptions.jsonl` `text_iso` and"
         " `ezhuthu.agent.data.inscription_text` return val/test text with the fills inline; only the"
         " lesson path may use them, never restoration or evaluation."),
        ("- **The `CorpusLeak` guard knows only inscriptions that have val/test items.** A held-out"
         " inscription with no item would pass it; the artefact test above (corpus ids subset of train"
         " ids) is the stronger check."),
        ("- **Public sources.** DHARMA and the printed volumes it edits (for example *South Indian"
         " Inscriptions*) are public, so a hosted LLM may have seen val/test texts in pretraining. This"
         " cannot be ruled out here. The copy and n-gram baselines read only the train corpus, so a large"
         " gap between an LLM and them on test-hard is worth checking for memorisation."),
        "",
        "## Scoring",
        "",
        "Score restorations with `ezhuthu.corpus.script.normalise_for_scoring` applied to both the",
        "prediction and `target`, so that CER and top-1 exact match count **letters only**. It keeps",
        "ISO-15919 letters (lower-cased, `ṛ` spelled `r̥`) and drops spaces, hyphens, `·`, `’`, digits,",
        "punctuation, gap markers and editorial marks such as `=`, `‡`, `⌈`, `⌉`, `_` and quote marks,",
        "which DHARMA editions use and which some targets contain. `text_tamil` and `text_tamil_masked`",
        "are display forms (`iso_to_tamil_display`): editorial marks are removed, notes such as",
        "`[text not available]` become `[?]`, and stray Latin letters are folded or dropped.",
        "`text_iso` keeps the raw marks.",
        "",
        "## Same stone, several editions",
        "",
        (f"Some stones are edited in two collections. Before splitting, editions are grouped when their"
         f" normalised whole texts score rapidfuzz `ratio` >= {st['dup_rule']['text_ratio_min']} (texts of at"
         f" least {st['dup_rule']['min_chars']} letters) or when site, ruler and regnal year in the title all"
         " match; a group takes the split drawn for its first id. The second rule also groups distinct"
         " inscriptions of one king, year and site, which keeps their shared formulae in one split."
         f" **{len(st['edition_groups'])}** groups,"
         f" {sum(len(g['ids']) for g in st['edition_groups'])} inscriptions (all in `stats.json`"
         " `edition_groups`):"),
        "",
        "| Split | Editions grouped |",
        "| --- | --- |",
    ]
    for g in st["edition_groups"]:
        lines.append(f"| {g['split']} | " + ", ".join(f"`{i}`" for i in g["ids"]) + " |")
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
        (f"- Age set (Pallava + Uttiramerur collections): **{st['age_set_items']}** items from"
         f" {st['age_set_inscriptions']} inscriptions;"
         f" {st['per_collection'].get('tfa-pallava-epigraphy', {}).get('items', 0)} from the Pallava collection"
         f" and {st['per_collection'].get('tfa-uttiramerur-epigraphy', {}).get('items', 0)} from Uttiramerur."
         " Only the Pallava part may be described as over 1,100 years old (see Known limits)."),
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
        "inscription appears in two splits, and editions of one stone share a split (see above).",
        "`items.test-hard.jsonl` and `items.test-age.jsonl` are the",
        "hard and age subsets of the test split.",
        "",
        "**Hard** = no train inscription other than the item's own (or another edition of its stone)",
        "contains the target with a similar",
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
        "## Charter planning numbers (superseded)",
        "",
        "The first `docs/CHARTER.md` was written before this build. It now quotes the measured values, and",
        "`tests/test_doc_numbers.py` checks the numbers in the charter and the README against `stats.json`.",
        "",
        "| Charter planning number | This build |",
        "| --- | --- |",
        f"| about 1,200 DHARMA editions | {st['inscriptions']} TEI editions parsed |",
        (f"| about 87% have damaged passages | {st['inscriptions_damaged']} of {st['inscriptions']}"
         f" ({st['inscriptions_damaged'] / max(1, st['inscriptions']):.0%}) have a restoration or a gap |"),
        (f"| about 12,900 expert restorations | {st['items']} scorable restorations in Tamil lines;"
         f" all `<supplied>` spans in all languages: {sum(sup_all.values())} ("
         + ", ".join(f"{k} {v}" for k, v in sorted(sup_all.items())) + ") |"),
        (f"| about 3,800 in inscriptions over 1,100 years old | {st['age_set_items']} restoration items in"
         " the Pallava + Uttiramerur collections, of which"
         f" {st['per_collection'].get('tfa-pallava-epigraphy', {}).get('items', 0)} Pallava |"),
        (f"| DHARMA data under CC BY 4.0 | CC BY-SA 4.0 in {st['licences'].get('CC BY-SA 4.0', 0)} edition"
         f" headers ({st['licences'].get('(none in header)', 0)} declare none); benchmark shared under"
         " CC BY-SA 4.0 |"),
    ]
    lines += [
        "",
        "## Known limits",
        "",
        "- Restorations are what DHARMA editors supplied; a model that reproduces them \"matches expert",
        "  restorations\". It is not proof that the reading is correct.",
        ("- The age set is defined by collection, not by date. The Pallava collection is DHARMA's corpus of"
         " Pallava-period inscriptions (the dynasty ended about 900 CE); its titles name Pallava kings and"
         " some local rulers, and the build does not check each inscription's date. The Uttiramerur"
         " collection also holds"
         " inscriptions of later kings (for example Rājarāja I Cōḻa and Kṛṣṇadevarāya), so its"
         f" {st['per_collection'].get('tfa-uttiramerur-epigraphy', {}).get('items', 0)} items are not all"
         " over 1,100 years old; say \"over 1,100 years old\" only of the Pallava items."),
        ("- `dynasty` comes from the collection (Pallava, Pandya) or from ruler names in the title"
        f" ({st['dynasty_sources'].get('title', 0)} inscriptions); it is null for"
        f" {st['dynasty_sources'].get('(unknown)', 0)}."),
        ("- Edition-specific marks that are not letters (for example `⌈`, `‡`, `=` and literal brackets)"
        " are kept exactly as in the source text in `text_iso`, `left`, `right` and `target`; score with"
        " `normalise_for_scoring` (see Scoring)."),
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
