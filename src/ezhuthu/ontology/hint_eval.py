"""Measure ``hints_for_gap`` against expert restorations.

    python -m ezhuthu.ontology.hint_eval --dharma data/raw/dharma \
        --items benchmark/items.val.jsonl --items benchmark/items.test.jsonl

Two numbers, kept apart on purpose:

* ``held_out``: for each benchmark item (``left``, ``right``, ``target``, ``gap_chars``) call
  ``hints_for_gap(left, right, gap_chars)`` and count a hit when one of the top-k hints' ``fill`` (or
  ``alt_fills``) equals the folded target. The shipped ontology is built from the train split only
  (``coverage.json`` -> ``splits``), so on val/test items this is a held-out score. It is refused
  when an item's inscription was used to build the ontology.
* ``in_corpus``: the same check on every ``<supplied reason="lost">`` span of the editions the
  ontology was built from. The variants come from those editions (including supplied text), so this
  is coverage of the restoration need, an upper bound, NOT a generalisation score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from ezhuthu.ontology.letters import letter_count
from ezhuthu.ontology.lookup import Ontology, load
from ezhuthu.ontology.normalize import key
from ezhuthu.ontology.tei import iter_corpus

REPO = Path(__file__).resolve().parents[3]


def _hit(onto: Ontology, left: str, right: str, target: str, gap: int | None, k: int) -> tuple[bool, bool]:
    hints = onto.hints_for_gap(left, right, gap_chars=gap if gap and gap > 0 else None, limit=k)
    t = key(target)
    return any(t == h["fill"] or t in h.get("alt_fills", ()) for h in hints), bool(hints)


def built_from(onto: Ontology) -> set[str] | None:
    """Inscription ids the ontology artefacts were built from (None = all editions, no split filter)."""
    cov = json.loads((onto.root / "coverage.json").read_text(encoding="utf-8"))
    ids = (cov.get("splits") or {}).get("included_inscriptions")
    return set(ids) if ids is not None else None


def evaluate_items(items_path: Path, k: int = 5, onto: Ontology | None = None) -> dict:
    """Held-out hit@k on benchmark items (``items.val.jsonl`` / ``items.test.jsonl``)."""
    onto = onto or load()
    used = built_from(onto)
    rows = [json.loads(line) for line in Path(items_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    leaked = sorted({r["inscription_id"] for r in rows} & used) if used is not None else ["<all editions>"]
    if leaked:
        raise ValueError(f"{items_path}: ontology was built from {len(leaked)} of these items' inscriptions "
                         f"(e.g. {leaked[:3]}); rebuild with --splits train before scoring")
    n = hits = with_hint = 0
    for r in rows:
        if len(key(r["target"])) < 2:
            continue
        hit, any_hint = _hit(onto, r["left"], r["right"], r["target"], r.get("gap_chars"), k)
        n += 1
        hits += hit
        with_hint += any_hint
    return {"items": Path(items_path).name, "sha256": hashlib.sha256(Path(items_path).read_bytes()).hexdigest(), "k": k, "scored": n, "skipped_short_target": len(rows) - n,
            "hits": hits, "hit_at_k": round(hits / n, 4) if n else 0.0, "items_with_any_hint": with_hint}


def evaluate(dharma: Path, k: int = 5, onto: Ontology | None = None) -> dict:
    """In-corpus coverage over the editions the ontology was built from (not held-out)."""
    onto = onto or load()
    used = built_from(onto)
    n = hits = n_ent = hits_ent = with_hint = 0
    for ins in iter_corpus(dharma):
        if used is not None and ins.id not in used:
            continue
        for line in ins.lines:
            if not line.supplied:
                continue
            mentions = onto.find_entities(line.text)
            for a, b in line.supplied:
                target = line.text[a:b]
                if len(key(target)) < 2:
                    continue
                hit, any_hint = _hit(onto, line.text[:a], line.text[b:], target, letter_count(target), k)
                in_entity = any(m["start"] < b and a < m["end"] for m in mentions)
                n += 1
                hits += hit
                with_hint += any_hint
                if in_entity:
                    n_ent += 1
                    hits_ent += hit
    return {
        "k": k,
        "gaps": n,
        "gaps_with_any_hint": with_hint,
        "hit_at_k": round(hits / n, 4) if n else 0.0,
        "hits": hits,
        "gaps_inside_entity_mention": n_ent,
        "hit_at_k_inside_entity_mention": round(hits_ent / n_ent, 4) if n_ent else 0.0,
        "note": "in-corpus (not held-out): editions the ontology was built from; an upper bound",
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dharma", type=Path, default=REPO / "data" / "raw" / "dharma")
    ap.add_argument("--items", type=Path, action="append", help="benchmark items file (repeatable)")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", type=Path, default=REPO / "ontology" / "hint_eval.json")
    args = ap.parse_args(argv)
    res = {"in_corpus": evaluate(args.dharma, args.k),
           "held_out": [evaluate_items(p, args.k) for p in (args.items or [])]}
    args.out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
