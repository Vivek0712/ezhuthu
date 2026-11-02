"""The ontology slice on /how-it-works (app/web/src/components/how/ontology-slice.json) is train-only and current."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SLICE = ROOT / "app" / "web" / "src" / "components" / "how" / "ontology-slice.json"
BENCH = ROOT / "benchmark" / "inscriptions.jsonl"


def _slice() -> dict:
    return json.loads(SLICE.read_text(encoding="utf-8"))


def _all_inscription_ids(d: dict) -> set[str]:
    ids = set(d["evidence_inscriptions"]) | set(d["center_inscriptions"])
    for e in d["edges"]:
        ids |= set(e.get("evidence", []))
    return ids


def test_slice_uses_only_train_inscriptions():
    d = _slice()
    ids = _all_inscription_ids(d)
    assert ids, "the slice should cite the inscriptions behind its links"
    cov = json.loads((ROOT / "ontology" / "coverage.json").read_text(encoding="utf-8"))
    assert cov["splits"]["used"] == ["train"]
    assert ids <= set(cov["splits"]["included_inscriptions"])
    if BENCH.exists():
        split = {}
        for line in BENCH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                split[row["id"]] = row["split"]
        assert {i: split.get(i) for i in ids if split.get(i) != "train"} == {}


def test_slice_entities_exist_in_the_build_and_edges_connect_them():
    d = _slice()
    recs = {r["id"]: r for p in (ROOT / "ontology" / "lookups").glob("*.json") for r in json.loads(p.read_text())}
    node_ids = {n["id"] for n in d["nodes"]}
    assert d["center"] in node_ids
    for n in d["nodes"]:
        assert n["id"] in recs and recs[n["id"]]["kind"] == n["kind"]
    for e in d["edges"]:
        assert e["from"] in node_ids and e["to"] in node_ids
    # Every neighbour is linked to the centre or to another node.
    linked = {e["from"] for e in d["edges"]} | {e["to"] for e in d["edges"]}
    assert node_ids == linked


def test_slice_counts_match_coverage():
    d = _slice()
    cov = json.loads((ROOT / "ontology" / "coverage.json").read_text(encoding="utf-8"))
    assert d["counts"] == cov["entities_per_kind"]
    assert d["corpus"]["inscriptions"] == cov["corpus"]["inscriptions"]


def test_slice_is_up_to_date():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_how_ontology_slice.py"), "--check"],
                       check=False, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
