"""Fixture records follow the contracts; the decider client works against a real `strands-decider serve`."""

import json
import os

import jsonschema
import pytest

from ezhuthu.agent.config import FIXTURES_DIR, repo_root
from ezhuthu.agent.data import read_jsonl
from ezhuthu.agent.decider import HttpDecider
from ezhuthu.agent.restorer import Restorer

CONTRACTS = repo_root() / "contracts"


def test_fixture_items_validate_against_benchmark_schema():
    schema = json.loads((CONTRACTS / "benchmark-item.schema.json").read_text())
    for rec in read_jsonl(FIXTURES_DIR / "items.test.jsonl"):
        jsonschema.validate(rec, schema)
        assert rec["id"].startswith("FIXTURE_") and "example.invalid" in rec["source_url"]


def test_fixture_ontology_validates_against_lookup_schema():
    schema = json.loads((CONTRACTS / "ontology-lookup.schema.json").read_text())
    for rec in json.loads((FIXTURES_DIR / "ontology_stub.json").read_text()):
        jsonschema.validate(rec, schema)


# Opt-in only: a strands-decider left running on the default port by another session must not turn
# `make check` red (QA on #20). Set EZHUTHU_DECIDER_URL to a running `strands-decider serve` to run these.
DECIDER_URL = os.environ.get("EZHUTHU_DECIDER_URL", "")
needs_decider = pytest.mark.skipif(not DECIDER_URL or not HttpDecider(DECIDER_URL).available(),
                                   reason="set EZHUTHU_DECIDER_URL to a running strands-decider serve")


@needs_decider
def test_real_decider_choice_shape():
    d = HttpDecider(DECIDER_URL)
    res = d.choice({"learner": "answered correctly twice"}, "Next teaching step?",
                   {"advance": "move on", "repeat": "drill again", "hint": "give a hint"}, name="pedagogy")
    assert res.choice in ("advance", "repeat", "hint")
    assert abs(sum(res.probabilities.values()) - 1.0) < 1e-2 and 0.0 <= res.confidence <= 1.0
    assert res.model.startswith("strands-decider")


@needs_decider
def test_real_decider_ranks_restoration_candidates():
    g = Restorer(decider=HttpDecider(DECIDER_URL)).restore_gap("svasti śrī kōvirājakēcari", " yāṇṭu", 8)
    assert g.decider_model.startswith("strands-decider")
    assert all(c.confidence_source == "decider" for c in g.candidates)
    assert g.candidates == sorted(g.candidates, key=lambda c: c.confidence, reverse=True)
