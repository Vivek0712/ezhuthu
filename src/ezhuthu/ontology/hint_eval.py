"""In-corpus check of ``hints_for_gap`` against DHARMA expert restorations.

    python -m ezhuthu.ontology.hint_eval --dharma data/raw/dharma

For every ``<supplied reason="lost">`` span in the editions, hide the span, call
``hints_for_gap(left, right, gap_chars=<Tamil letters in target>)`` and count a hit when one of the top-k hints'
``fill`` (or one of its ``alt_fills``) equals the folded target. This is NOT a held-out benchmark: the ontology's variants and
extracted entities come from the same editions (including supplied text), so it measures how much
of the restoration need the ontology covers, and is an upper bound for unseen text. The held-out
restoration benchmark is the data team's ``benchmark/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ezhuthu.ontology.letters import letter_count
from ezhuthu.ontology.lookup import load
from ezhuthu.ontology.normalize import key
from ezhuthu.ontology.tei import iter_corpus

REPO = Path(__file__).resolve().parents[3]


def evaluate(dharma: Path, k: int = 5) -> dict:
    onto = load()
    n = hits = n_ent = hits_ent = with_hint = 0
    for ins in iter_corpus(dharma):
        for line in ins.lines:
            if not line.supplied:
                continue
            mentions = onto.find_entities(line.text)
            for a, b in line.supplied:
                target = key(line.text[a:b])
                if len(target) < 2:
                    continue
                gap = letter_count(line.text[a:b])
                hints = onto.hints_for_gap(line.text[:a], line.text[b:], gap_chars=gap, limit=k)
                hit = any(target == h["fill"] or target in h.get("alt_fills", ()) for h in hints)
                in_entity = any(m["start"] < b and a < m["end"] for m in mentions)
                n += 1
                hits += hit
                with_hint += bool(hints)
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
        "note": "in-corpus (not held-out): ontology built from the same editions; see module docstring",
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dharma", type=Path, default=REPO / "data" / "raw" / "dharma")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--out", type=Path, default=REPO / "ontology" / "hint_eval.json")
    args = ap.parse_args(argv)
    res = evaluate(args.dharma, args.k)
    args.out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
