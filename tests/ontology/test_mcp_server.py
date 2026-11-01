"""MCP tool tests for ezhuthu.ontology.mcp_server: in-process for the edge cases, and one real stdio session.

Every tool must return exactly what the direct lookup API returns (the server is a thin adapter)."""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import pytest
from mcp import Client, StdioServerParameters

from ezhuthu.ontology import lookup
from ezhuthu.ontology.mcp_server import TOOL_NAMES, build_server

UTTIRAMERUR = ("svasti śrī maturai koṇṭa kō-p-parakēcari-varmmarkku yāṇṭu paṉṉiraṇṭu Āvatu "
               "Uttiramēru-c-caturvvedimaṅkalattu sabhaiyōm")


def _data(res: Any) -> dict[str, Any]:
    assert not res.is_error, res.content
    text = json.loads(res.content[0].text)
    assert res.structured_content == text  # structured and text content carry the same JSON
    return text


async def _session(server: Any, calls: list[tuple[str, dict[str, Any]]]) -> tuple[list[str], list[Any]]:
    async with Client(server) as c:
        tools = [t.name for t in (await c.list_tools()).tools]
        return tools, [await c.call_tool(name, args) for name, args in calls]


def _run(calls: list[tuple[str, dict[str, Any]]], server: Any = None) -> tuple[list[str], list[Any]]:
    return asyncio.run(_session(server if server is not None else build_server(), calls))


def test_tools_listed_with_schemas():
    server = build_server()

    async def go() -> list[Any]:
        async with Client(server) as c:
            return (await c.list_tools()).tools

    tools = {t.name: t for t in asyncio.run(go())}
    assert set(tools) == set(TOOL_NAMES)
    assert set(tools["hints_for_gap"].input_schema["required"]) == {"left", "right"}
    assert set(tools["hints_for_gap"].input_schema["properties"]) == {"left", "right", "gap_chars", "limit"}
    assert tools["entity"].input_schema["required"] == ["id"]
    assert all(t.description for t in tools.values())


def test_tools_match_direct_api():
    calls = [
        ("find_entities", {"text": UTTIRAMERUR}),
        ("valid_letters", {"stage": "L2"}),
        ("formulas_for", {"ruler": "ez:ruler/rajaraja-i"}),
        ("entity", {"id": "ez:ruler/rajaraja-i"}),
        ("entity", {"id": "ez:ruler/no-such-ruler"}),
        ("hints_for_gap", {"left": "svasti śrī maturai koṇṭa kō-p-para", "right": "rkku yāṇṭu", "gap_chars": 7}),
        ("hints_for_gap", {"left": "cantirātittavar", "right": " ivai", "limit": 3}),
    ]
    _, res = _run(calls)
    found, letters, formulas, rr, missing, hints, moon = (_data(r) for r in res)
    assert found["entities"] == lookup.find_entities(UTTIRAMERUR)
    assert [e["id"] for e in found["entities"]][:3] == ["ez:formula/svasti-sri", "ez:formula/matirai-konta",
                                                        "ez:title/parakesarivarman"]
    assert letters == {"stage": "L2", "letters": lookup.valid_letters("L2")}
    assert formulas["formulas"] == lookup.formulas_for("ez:ruler/rajaraja-i") and formulas["formulas"]
    assert rr["entity"] == lookup.entity("ez:ruler/rajaraja-i") and rr["entity"]["wikidata"] == "Q2128757"
    assert missing == {"entity": None}
    assert hints["hints"] == lookup.hints_for_gap("svasti śrī maturai koṇṭa kō-p-para", "rkku yāṇṭu", 7)
    assert hints["hints"][0]["id"] == "ez:title/parakesarivarman"
    assert moon["hints"] == lookup.hints_for_gap("cantirātittavar", " ivai", limit=3)
    assert moon["hints"][0]["fill"] == "aiyum"


@pytest.mark.parametrize("name,args,message", [
    ("find_entities", {"text": "கோ"}, "Tamil script"),
    ("find_entities", {"text": "a" * (lookup.MAX_TEXT_CHARS + 1)}, "chars"),
    ("hints_for_gap", {"left": "a", "right": "b", "gap_chars": 0}, "gap_chars"),
    ("valid_letters", {"stage": "no-such-stage"}, "stage"),
])
def test_bad_input_is_a_tool_error_with_the_api_message(name, args, message):
    with pytest.raises((ValueError, KeyError)) as direct:
        getattr(lookup, name)(**args)  # the direct API rejects it ...
    _, (res,) = _run([(name, args)])
    assert res.is_error  # ... and the MCP tool reports it, with the reason
    assert direct.type.__name__ in res.content[0].text and message in res.content[0].text


def test_results_are_copies():
    _, (a,) = _run([("entity", {"id": "ez:ruler/rajaraja-i"})])
    _data(a)["entity"]["label_iso"] = "mutated"
    assert lookup.entity("ez:ruler/rajaraja-i")["label_iso"] != "mutated"


def test_stdio_subprocess_serves_the_shipped_build():
    """The real transport: `python -m ezhuthu.ontology.mcp_server` as a subprocess, MCP over stdin/stdout."""
    params = StdioServerParameters(command=sys.executable, args=["-m", "ezhuthu.ontology.mcp_server"])
    tools, (hint, ent) = _run([
        ("hints_for_gap", {"left": "cantirātittavar", "right": " ivai", "gap_chars": 2}),
        ("entity", {"id": "ez:dynasty/chola"}),
    ], server=params)
    assert set(tools) == set(TOOL_NAMES)
    assert _data(hint)["hints"][0]["id"] == "ez:formula/candradityavat"
    assert _data(ent)["entity"] == lookup.entity("ez:dynasty/chola")


def test_root_option_serves_another_build(tmp_path):
    """--root / EZHUTHU_ONTOLOGY_ROOT points the server at another build directory."""
    (tmp_path / "lookups").mkdir()
    rec = {"id": "ez:ruler/test-king", "kind": "ruler", "label_iso": "Kōvintaṉ", "label_ta": None,
           "variants": [], "era": None, "dynasty": None, "broader": None, "wikidata": None, "attested_in": []}
    (tmp_path / "lookups" / "ruler.json").write_text(json.dumps([rec]), encoding="utf-8")
    (tmp_path / "letters_by_era.json").write_text(json.dumps({"levels": {}, "stages": {}}), encoding="utf-8")
    _, (res, shipped) = _run([("entity", {"id": "ez:ruler/test-king"}), ("entity", {"id": "ez:ruler/rajaraja-i"})],
                             server=build_server(str(tmp_path)))
    assert _data(res)["entity"]["label_iso"] == "Kōvintaṉ"
    assert _data(shipped)["entity"] is None  # not the shipped build
