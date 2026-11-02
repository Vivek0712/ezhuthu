"""Build the small ontology slice shown on /how-it-works ("The ontology").

Reads the shipped train-only ontology build (ontology/ezhuthu.ttl, the OWL export, plus ontology/lookups/*.json and
ontology/coverage.json) and writes app/web/src/components/how/ontology-slice.json: one ruler, the entities the OWL file
links to it directly (dynasty, royal-praise formulas) and a few entities named on the same stones (titles, a place,
a temple, an administrative unit, measures, a tax, a coin), each with the inscription ids that show the link.

Every inscription id in the slice must be a train-split edition (coverage.json -> splits.included_inscriptions, and
split == "train" in benchmark/inscriptions.jsonl); the script refuses to write otherwise, and
tests/test_how_ontology_slice.py checks the committed file the same way.

    .venv/bin/python scripts/build_how_ontology_slice.py            # write the JSON
    .venv/bin/python scripts/build_how_ontology_slice.py --check    # fail if the committed JSON is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from rdflib import OWL, RDF, Graph, Namespace, URIRef

ROOT = Path(__file__).resolve().parents[1]
ONTO = ROOT / "ontology"
OUT = ROOT / "app" / "web" / "src" / "components" / "how" / "ontology-slice.json"
EZ = Namespace("https://w3id.org/ezhuthu/")

CENTER = "ez:ruler/rajaraja-i"
# Chosen by hand from the entities most often named on the same train stones as the centre (counts are recomputed
# below from the data and the build fails if any of these is not actually linked). English-only DHARMA labels
# (e.g. "Br̥hadīśvara temple", whose Tamil form is a letter-by-letter transliteration of English) are left out.
NEIGHBOURS = [
    "ez:dynasty/chola",
    "ez:formula/tirumakal-pola",
    "ez:formula/kantalur-calai",
    "ez:title/rajakesarivarman",
    "ez:title/udaiyar",
    "ez:place/uttiramerur",
    "ez:temple/uttiramerur-sundaravaradaperumal",
    "ez:admin_unit/kaliyur-kottam",
    "ez:measure/kani",
    "ez:measure/kalanju",
    "ez:tax/irai",
    "ez:coin/pon",
]
EVIDENCE_PER_EDGE = 3
DIRECT = ("memberOfDynasty", "praiseOf", "locatedAt", "dedicatedTo", "fallsWithin")


def iri(cid: str) -> URIRef:
    return EZ[cid.removeprefix("ez:")]


def cid(u: URIRef) -> str:
    return "ez:" + str(u).removeprefix(str(EZ))


def records() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in sorted((ONTO / "lookups").glob("*.json")):
        for r in json.loads(p.read_text(encoding="utf-8")):
            out[r["id"]] = r
    return out


def train_ids() -> set[str]:
    cov = json.loads((ONTO / "coverage.json").read_text(encoding="utf-8"))
    if cov["splits"]["used"] != ["train"]:
        raise SystemExit(f"ontology build is not train-only: splits.used = {cov['splits']['used']}")
    ids = set(cov["splits"]["included_inscriptions"])
    bench = ROOT / "benchmark" / "inscriptions.jsonl"
    if bench.exists():
        split = {}
        for line in bench.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                split[row["id"]] = row["split"]
        ids = {i for i in ids if split.get(i) == "train"}
    return ids


def build() -> dict:
    g = Graph()
    g.parse(ONTO / "ezhuthu.ttl")
    recs = records()
    cov = json.loads((ONTO / "coverage.json").read_text(encoding="utf-8"))
    train = train_ids()

    def stones(c: str) -> set[str]:
        u = iri(c)
        s = {cid(i) for i in g.objects(u, EZ.attestedIn)} | {cid(i) for i in g.subjects(EZ.mentions, u)}
        return {x.removeprefix("ez:inscription/") for x in s}

    center_stones = stones(CENTER)
    ids = [CENTER, *NEIGHBOURS]
    edges: list[dict] = []
    # Direct OWL statements between any two slice nodes.
    for a in ids:
        for b in ids:
            for p in g.predicates(iri(a), iri(b)):
                name = str(p).removeprefix(str(EZ))
                if name in DIRECT:
                    edges.append({"from": a, "to": b, "rel": name})
    linked = {e["from"] for e in edges} | {e["to"] for e in edges}
    # Named on the same stone as the centre.
    # Named on the same stone as the centre: the count and a few inscription ids go on the direct edge when the OWL
    # file already links the two, else on a "sameStone" edge.
    for n in NEIGHBOURS:
        both = sorted(center_stones & stones(n))
        if not both:
            continue
        info = {"n": len(both), "evidence": both[:EVIDENCE_PER_EDGE]}
        direct = next((e for e in edges if {e["from"], e["to"]} == {CENTER, n}), None)
        if direct:
            direct.update(info)
        else:
            edges.append({"from": CENTER, "to": n, "rel": "sameStone", **info})
        linked.add(n)
    missing = [n for n in NEIGHBOURS if n not in linked]
    if missing:
        raise SystemExit(f"not linked to {CENTER} in the build: {missing}")

    nodes = []
    for c in ids:
        r = recs[c]
        nodes.append({
            "id": c,
            "kind": r["kind"],
            "label_iso": r["label_iso"],
            "label_ta": r.get("label_ta"),
            "label_en": r.get("label_en"),
            "era": r.get("era"),
            "wikidata": r.get("wikidata"),
            "inscriptions": r.get("inscription_count"),
        })

    evidence = sorted({i for e in edges for i in e.get("evidence", [])} | center_stones)
    leaked = [i for i in evidence if i not in train]
    if leaked:
        raise SystemExit(f"non-train inscriptions in the slice: {leaked}")

    individuals = set(g.subjects(RDF.type, OWL.NamedIndividual))
    owl = {
        "classes": sum(1 for s in g.subjects(RDF.type, OWL.Class) if str(s).startswith(str(EZ))),
        "object_properties": sum(1 for s in g.subjects(RDF.type, OWL.ObjectProperty) if str(s).startswith(str(EZ))),
        "named_individuals": len(individuals),
        "triples": len(g),
    }
    kinds = Counter(cov["entities_per_kind"])
    return {
        "meta": {
            "built_by": "scripts/build_how_ontology_slice.py",
            "source": "ontology/ezhuthu.ttl (OWL export) + ontology/lookups/*.json, train-only build (ontology/coverage.json splits.used = [train])",
            "credit": "Inscriptions: DHARMA project editions, CC BY-SA 4.0. Wikidata identifiers: Wikidata, CC0.",
        },
        "center": CENTER,
        "center_inscriptions": sorted(center_stones),
        "nodes": nodes,
        "edges": edges,
        "counts": {k: kinds[k] for k in cov["entities_per_kind"]},
        "wikidata": cov["wikidata"],
        "corpus": {"inscriptions": cov["corpus"]["inscriptions"], "lines": cov["corpus"]["lines"],
                   "collections": len(cov["corpus"]["collections"])},
        "owl": owl,
        "evidence_inscriptions": evidence,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if the committed JSON differs from a fresh build")
    args = ap.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is stale; rerun scripts/build_how_ontology_slice.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
