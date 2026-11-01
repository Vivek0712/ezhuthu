"""Checks on the committed ontology artefacts (ontology/ezhuthu.ttl, ontology/lookups/*.json)."""

import json
import re
from pathlib import Path

import jsonschema
import pytest
from rdflib import OWL, RDF, RDFS, SKOS, Graph, URIRef

from ezhuthu.ontology.owl import CLASSES, CRM, CRMTEX, EPONT, EZ, OBJECT_PROPERTIES, WD

REPO = Path(__file__).resolve().parents[2]
ONTO = REPO / "ontology"
KINDS = json.loads((REPO / "contracts" / "ontology-lookup.schema.json").read_text())["properties"]["kind"]["enum"]


@pytest.fixture(scope="module")
def graph() -> Graph:
    g = Graph()
    g.parse(ONTO / "ezhuthu.ttl", format="turtle")
    return g


@pytest.fixture(scope="module")
def lookups() -> dict[str, list[dict]]:
    return {k: json.loads((ONTO / "lookups" / f"{k}.json").read_text(encoding="utf-8")) for k in KINDS}


def test_ttl_declares_ontology_classes_and_properties(graph):
    assert (URIRef("https://w3id.org/ezhuthu/ontology"), RDF.type, OWL.Ontology) in graph
    for name in ("ScriptStage", "Letter", "Dynasty", "Ruler", "Title", "RoyalPraiseFormula", "Place", "Nadu",
                 "Kottam", "Valanadu", "Mandalam", "Temple", "Deity", "GrantType", "Assembly", "Measure", "Coin", "Tax"):
        assert (EZ[name], RDF.type, OWL.Class) in graph, name
    for name in OBJECT_PROPERTIES:
        assert (EZ[name], RDF.type, OWL.ObjectProperty) in graph, name


def test_backbone_is_reused_by_iri_not_copied(graph):
    assert (EZ.Inscription, RDFS.subClassOf, CRMTEX.TX1_Written_Text) in graph
    assert (EZ.ScriptStage, RDFS.subClassOf, CRMTEX.TX3_Writing_System) in graph
    assert (EZ.Ruler, RDFS.subClassOf, CRM.E21_Person) in graph
    assert (EZ.Edition, RDFS.subClassOf, EPONT.Edition) in graph
    assert (EZ.fallsWithin, RDFS.subPropertyOf, CRM.P89_falls_within) in graph
    # no statements are made *about* backbone terms (they are referenced, not redefined)
    for ns in (CRM, CRMTEX, EPONT):
        assert not [s for s in graph.subjects() if str(s).startswith(str(ns))]
    assert len(CLASSES) >= 25


def test_sample_instances(graph):
    rr = EZ["ruler/rajaraja-i"]
    assert (rr, RDF.type, EZ.Ruler) in graph
    assert (rr, EZ.memberOfDynasty, EZ["dynasty/chola"]) in graph
    assert (rr, SKOS.exactMatch, WD.Q2128757) in graph
    assert (EZ["formula/tirumakal-pola"], RDF.type, EZ.RoyalPraiseFormula) in graph
    assert (EZ["formula/tirumakal-pola"], EZ.praiseOf, rr) in graph
    assert (EZ["admin_unit/kaliyur-kottam"], RDF.type, EZ.Kottam) in graph
    assert (EZ["admin_unit/kaliyur-kottam"], EZ.fallsWithin, EZ["admin_unit/jayankontacozha-mandalam"]) in graph
    assert (EZ["letter/chola-tamil-ka"], EZ.letterOf, EZ["script_stage/chola-tamil"]) in graph
    ins = EZ["inscription/DHARMA_INSUttiramerur00001"]
    assert (ins, RDF.type, EZ.Inscription) in graph
    assert (ins, EZ.writtenIn, EZ["script_stage/chola-tamil"]) in graph
    assert (EZ["title/parakesarivarman"], EZ.attestedIn, ins) in graph


def test_lookups_validate_against_contract(lookups):
    schema = json.loads((REPO / "contracts" / "ontology-lookup.schema.json").read_text())
    validator = jsonschema.Draft202012Validator(schema)
    seen = set()
    for kind, recs in lookups.items():
        assert recs, f"no {kind} entities"
        for r in recs:
            errors = list(validator.iter_errors(r))
            assert not errors, (r["id"], errors[0].message)
            assert r["kind"] == kind and r["id"].startswith(f"ez:{kind}/")
            assert r["id"] not in seen
            seen.add(r["id"])


def test_every_content_entity_is_attested_and_references_resolve(lookups):
    ids = {r["id"] for recs in lookups.values() for r in recs}
    for kind, recs in lookups.items():
        for r in recs:
            if kind not in ("script_stage", "letter"):
                assert r["attested_in"], r["id"]
                assert all(a.startswith("DHARMA_") for a in r["attested_in"])
            for field in ("broader", "dynasty", "ruler", "deity"):
                if r.get(field):
                    assert r[field] in ids, (r["id"], field, r[field])


def test_letters_by_era_covers_all_stages_and_levels():
    doc = json.loads((ONTO / "letters_by_era.json").read_text(encoding="utf-8"))
    assert set(doc["levels"]) == {"L1", "L2", "L3", "L4", "L5"}
    assert len(doc["stages"]) == 8
    for st, d in doc["stages"].items():
        assert d["letters"], st
        assert d["exceptions"] or st == "later-tamil" or st == "grantha", st


def test_coverage_report_is_consistent(lookups):
    cov = json.loads((ONTO / "coverage.json").read_text(encoding="utf-8"))
    assert cov["entities_per_kind"] == {k: len(v) for k, v in lookups.items()}
    assert cov["corpus"]["inscriptions"] == len(cov["splits"]["included_inscriptions"]) > 800
    for kind, w in cov["wikidata"].items():
        assert w["with_qid"] == sum(1 for r in lookups[kind] if r["wikidata"])


def test_shipped_build_is_train_split_only(lookups):
    """No val/test edition (whose <supplied> text is a benchmark answer) feeds the shipped ontology."""
    sp = json.loads((ONTO / "coverage.json").read_text(encoding="utf-8"))["splits"]
    assert sp["used"] == ["train"]
    used = set(sp["included_inscriptions"])
    assert sp["excluded_held_out"] > 0
    for recs in lookups.values():
        for r in recs:
            for ref in r["attested_in"]:
                assert ref.split(":")[0] in used, (r["id"], ref)
    bench = REPO / "benchmark" / "inscriptions.jsonl"
    if bench.exists():  # once the data team's benchmark is on main, guard against split drift
        held = {json.loads(x)["id"] for x in bench.read_text(encoding="utf-8").splitlines()
                if x.strip() and json.loads(x)["split"] != "train"}
        leaked = sorted(used & held)
        msg = f"{len(leaked)} val/test editions used (splits changed?); rebuild: ezhuthu.ontology.build --splits train"
        assert not leaked, (msg, leaked[:5])


def test_tamil_labels_have_no_latin_residue(lookups):
    for recs in lookups.values():
        for r in recs:
            ta = r.get("label_ta")
            if ta:
                assert not re.search(r"[A-Za-z]", re.sub(r"\b[IVX]+\b", "", ta)), (r["id"], ta)


def test_reviewed_wikidata_fixes():
    snap = json.loads((ONTO / "wikidata" / "snapshot.json").read_text(encoding="utf-8"))
    # Q97481257 is an ASI monument item at Erukkampattu, not the Srirangam temple (QA, PR #9)
    assert snap["resolved"]["ez:temple/srirangam-ranganatha"] == "Q2671548"
    assert "Q97481257" not in snap["resolved"].values()
