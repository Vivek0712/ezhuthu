"""Agent integration over stdio: the restorer's ontology is a Strands MCPClient talking to
`python -m ezhuthu.ontology.mcp_server`; the direct API is only a flagged offline fallback."""

from __future__ import annotations

import json

import pytest

from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.ontology_mcp import McpOntology, McpOntologyError
from ezhuthu.agent.ontology_port import ModuleOntology, StubOntology, get_ontology
from ezhuthu.agent.restorer import Restorer
from ezhuthu.agent.tools import build_restorer_agent
from ezhuthu.ontology import lookup


@pytest.fixture(scope="module")
def mcp_onto():
    onto = McpOntology()
    yield onto
    onto.close()


@pytest.fixture
def fresh_port(monkeypatch):
    get_ontology.cache_clear()
    yield monkeypatch
    onto = get_ontology()
    if isinstance(onto, McpOntology):
        onto.close()
    get_ontology.cache_clear()


def test_port_over_mcp_matches_direct_api(mcp_onto):
    assert mcp_onto.name == "mcp:ezhuthu-ontology (stdio)"
    hints = mcp_onto.hints_for_gap("cantirātittavar", " ivai")
    h = next(h for h in hints if h.id == "ez:formula/candradityavat")
    assert h.fill == "aiyum" and h.to_api() == {"id": "ez:formula/candradityavat", "kind": "formula",
                                                 "label": "cantirātittavaraiyum"}
    direct = ModuleOntology(lookup)
    assert hints == direct.hints_for_gap("cantirātittavar", " ivai")
    text = "svasti śrī rājakēsari yāṇṭu"
    assert mcp_onto.find_entities(text) == direct.find_entities(text)
    assert mcp_onto.valid_letters("tamil-brahmi-1") == direct.valid_letters("tamil-brahmi-1")
    assert mcp_onto.entity("ez:ruler/rajaraja-i") == lookup.entity("ez:ruler/rajaraja-i")
    assert mcp_onto.entity("ez:ruler/none") is None
    assert mcp_onto.formulas_for("ez:ruler/rajaraja-i") == lookup.formulas_for("ez:ruler/rajaraja-i")
    raw = mcp_onto.raw_hints_for_gap("svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu", gap_chars=7, limit=3)
    assert raw == lookup.hints_for_gap("svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu", 7, 3)


def test_entity_cache_returns_copies(mcp_onto):
    a = mcp_onto.entity("ez:dynasty/chola")
    a["label_iso"] = "mutated"
    assert mcp_onto.entity("ez:dynasty/chola")["label_iso"] != "mutated"


def test_input_errors_cross_the_wire(mcp_onto):
    with pytest.raises(ValueError, match="Tamil script"):
        mcp_onto.find_entities("கோ")
    with pytest.raises(KeyError, match="unknown script stage"):
        mcp_onto.valid_letters("no-such-stage")


def test_restorer_uses_mcp_ontology_candidates(mcp_onto):
    r = Restorer(decider=NoDecider(), ontology=mcp_onto)
    out = r.restore_gap("cantirātittavar", " ivai", 5)
    assert [c.text for c in out.candidates if "ontology" in c.sources] == ["aiyum"]
    assert any(h["id"] == "ez:formula/candradityavat" for c in out.to_api()["candidates"]
               for h in c["ontology_hints"])


def test_restorer_agent_calls_ontology_tools_over_mcp(mcp_onto, scripted_model):
    """The agentic Restorer gets the MCP server's tools from the same MCPClient and calls one over stdio."""
    model = scripted_model([
        {"tool": "hints_for_gap", "input": {"left": "cantirātittavar", "right": " ivai", "gap_chars": 2}},
        "The formula cantirātittavar[aiyum] fits the gap.",
    ])
    agent = build_restorer_agent(Restorer(decider=NoDecider(), ontology=mcp_onto), model)
    out = agent("Restore cantirātittavar[?2] ivai")
    tools = set(model.seen[0]["tools"])
    assert {"find_entities", "valid_letters", "formulas_for", "entity", "hints_for_gap"} <= tools
    assert {"retrieve_parallels", "rank_and_decide", "ontology_hints"} <= tools
    tool_results = [b["toolResult"] for m in model.seen[1]["messages"] for b in m["content"] if "toolResult" in b]
    assert tool_results and tool_results[0]["status"] == "success"
    assert "ez:formula/candradityavat" in json.dumps(tool_results[0], ensure_ascii=False)
    assert "aiyum" in str(out)


def test_restorer_agent_without_mcp_backend_has_no_mcp_tools(scripted_model):
    model = scripted_model(["ok"])
    stub = StubOntology([])
    build_restorer_agent(Restorer(decider=NoDecider(), ontology=stub), model)("hi")
    assert "hints_for_gap" not in model.seen[0]["tools"]


def test_get_ontology_defaults_to_mcp(fresh_port):
    fresh_port.delenv("EZHUTHU_FIXTURES", raising=False)
    fresh_port.delenv("EZHUTHU_ONTOLOGY", raising=False)
    onto = get_ontology()
    assert isinstance(onto, McpOntology) and onto.name.startswith("mcp:")


def test_get_ontology_mcp_mode_even_with_fixtures(fresh_port):
    fresh_port.setenv("EZHUTHU_FIXTURES", "1")
    fresh_port.setenv("EZHUTHU_ONTOLOGY", "mcp")
    assert isinstance(get_ontology(), McpOntology)


def test_fixture_runs_keep_the_stub(fresh_port):
    fresh_port.setenv("EZHUTHU_FIXTURES", "1")
    fresh_port.delenv("EZHUTHU_ONTOLOGY", raising=False)
    assert isinstance(get_ontology(), StubOntology)


def test_direct_mode_is_flagged(fresh_port):
    fresh_port.setenv("EZHUTHU_ONTOLOGY", "direct")
    onto = get_ontology()
    assert isinstance(onto, ModuleOntology) and onto.name == "direct:ezhuthu.ontology.lookup"


def test_mcp_failure_falls_back_to_flagged_direct(fresh_port):
    fresh_port.delenv("EZHUTHU_FIXTURES", raising=False)
    fresh_port.delenv("EZHUTHU_ONTOLOGY", raising=False)
    fresh_port.setattr("ezhuthu.agent.ontology_mcp.SERVER_MODULE", "ezhuthu.no_such_module")
    onto = get_ontology()
    assert isinstance(onto, ModuleOntology) and onto.name == "fallback:direct (mcp unavailable)"
    assert onto.hints_for_gap("cantirātittavar", " ivai")  # the fallback still answers


def test_mcp_start_failure_raises(monkeypatch):
    monkeypatch.setattr("ezhuthu.agent.ontology_mcp.SERVER_MODULE", "ezhuthu.no_such_module")
    with pytest.raises(McpOntologyError, match="did not start"):
        McpOntology(startup_timeout=10)


def test_unknown_mode_is_rejected(fresh_port):
    fresh_port.setenv("EZHUTHU_ONTOLOGY", "neptune")
    with pytest.raises(ValueError, match="EZHUTHU_ONTOLOGY"):
        get_ontology()
    fresh_port.setenv("EZHUTHU_ONTOLOGY", "stub")  # leave a valid mode for the fixture's teardown


def test_server_runs_in_this_environment_from_any_cwd(tmp_path, monkeypatch):
    """The AgentCore bundle case: the child interpreter gets this process's import roots on PYTHONPATH,
    so it finds ezhuthu and the mcp SDK even when they are not installed in site-packages."""
    import sys
    from pathlib import Path

    import ezhuthu
    from ezhuthu.agent.ontology_mcp import server_parameters

    monkeypatch.setenv("PYTHONPATH", "/extra/dir")
    params = server_parameters()
    assert params.command == sys.executable and params.args == ["-m", "ezhuthu.ontology.mcp_server"]
    roots = params.env["PYTHONPATH"].split(":")
    assert roots[0] == str(Path(ezhuthu.__file__).resolve().parents[1]) and roots[-1] == "/extra/dir"
    monkeypatch.delenv("PYTHONPATH")
    monkeypatch.chdir(tmp_path)
    onto = McpOntology()
    try:
        assert onto.entity("ez:dynasty/chola")["kind"] == "dynasty"
    finally:
        onto.close()
