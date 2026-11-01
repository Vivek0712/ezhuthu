import json

import pytest
from conftest import prefer_target_picker

from ezhuthu.agent.baselines import copy_best_parallel, ngram_fill, zero_shot
from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.decider import FakeDecider, HttpDecider, NoDecider
from ezhuthu.agent.llm import BedrockLLM, FakeLLM, LiveCallsDisabled
from ezhuthu.agent.ontology_port import StubOntology, get_ontology
from ezhuthu.agent.prompts import parse_candidates
from ezhuthu.agent.restorer import Restorer
from ezhuthu.agent.tools import make_tools

CFG = load_models_config()


def llm_returning(cands_by_role):
    def respond(role, system, prompt):
        return "```json\n" + json.dumps({"candidates": cands_by_role[role]}, ensure_ascii=False) + "\n```"
    return FakeLLM(respond)


def test_models_come_from_config():
    assert CFG.model_id("default") == "us.anthropic.claude-sonnet-4-6"
    assert CFG.model_id("escalate") == "us.anthropic.claude-opus-4-6-v1"
    assert CFG.routing.escalate_if_gap_chars_over == 12


def test_offline_restore_matches_contract_shape():
    out = Restorer(decider=NoDecider()).restore("svasti śrī kōvirājakēcari[?8] yāṇṭu mūṉṟāvatu")
    assert set(out) >= {"restored_text", "restored_text_tamil", "gaps", "models_used", "trace_id", "latency_ms"}
    g = out["gaps"][0]
    assert g["gap_chars"] == 8 and g["decision"] in ("fill", "abstain")
    c = g["candidates"][0]
    assert set(c) >= {"text", "text_tamil", "confidence", "model", "decider_model", "parallels", "ontology_hints"}
    assert c["text"] == "paṉmaṟku" and c["model"] == "retrieval"
    assert c["decider_model"] == "fallback:retrieval-heuristic"
    assert c["parallels"][0]["inscription_id"].startswith("FIXTURE_")
    assert {"id": "ez:title/rajakesari", "kind": "title", "label": "rājakēcari"} in c["ontology_hints"]
    assert out["models_used"] == []


def test_abstained_gap_keeps_marker_in_restored_text():
    out = Restorer(decider=FakeDecider(lambda s, o: {n: (0.9 if n == "none" else 0.1 / (len(o) - 1)) for n in o})
                   ).restore("svasti śrī kōvirājakēcari[?8] yāṇṭu")
    assert out["gaps"][0]["decision"] == "abstain"
    assert "[?8]" in out["restored_text"] and "[?8]" in out["restored_text_tamil"]


def test_decider_ranks_and_fills():
    target = {"v": "paṉmaṟku"}
    dec = FakeDecider(prefer_target_picker(lambda: target["v"]))
    out = Restorer(decider=dec).restore("svasti śrī kōvirājakēcari[?8] yāṇṭu mūṉṟāvatu")
    g = out["gaps"][0]
    assert g["decision"] == "fill" and g["candidates"][0]["text"] == "paṉmaṟku"
    assert g["candidates"][0]["confidence"] == pytest.approx(0.8)
    assert g["candidates"][0]["decider_model"] == "fake-decider"
    assert out["restored_text"] == "svasti śrī kōvirājakēcaripaṉmaṟku yāṇṭu mūṉṟāvatu"
    opts = dec.calls[0]["options"]
    assert "none" in opts and all("restored_line" in v for k, v in opts.items() if k != "none")


def test_router_escalates_when_sonnet_is_unsure():
    llm = llm_returning({"default": [{"text": "aiñcāvatu", "confidence": 0.4}],
                         "escalate": [{"text": "aiñcāvatu", "confidence": 0.7}]})
    # decider not running -> LLM self-report; 0.4 < 0.6 so routed escalates to Opus
    r = Restorer(llm=llm, decider=NoDecider())
    g = r.restore_gap("kōvirājakēcaripaṉmaṟku yāṇṭu ", " āvatu", 9, router="routed")
    roles = [role for role, _ in llm.calls]
    # "no good parallel" pre-escalates straight to opus per config; otherwise sonnet first
    assert roles[0] in ("default", "escalate") and "escalate" in roles
    assert g.escalated and g.decider_model == "fallback:llm-self-report"
    assert CFG.model_id("escalate") in g.models_used


def test_router_stays_on_sonnet_when_confident():
    llm = llm_returning({"default": [{"text": "oṉṟukku", "confidence": 0.9}], "escalate": []})
    r = Restorer(llm=llm, decider=NoDecider())
    g = r.restore_gap("mahādēvarkku nantā viḷakku ", " vaitta āṭu toṇṇūṟu", 7, router="routed")
    assert [role for role, _ in llm.calls] == ["default"]
    assert not g.escalated and g.decision == "fill" and g.best.text == "oṉṟukku"
    assert g.best.model == "sonnet" and "parallel" in g.best.sources


def test_long_gap_pre_escalates_to_opus():
    llm = llm_returning({"default": [], "escalate": [{"text": "tirumakaḷ pōlap", "confidence": 0.8}]})
    Restorer(llm=llm, decider=NoDecider()).restore_gap("svasti śrī ", " perunilac", 15, router="routed")
    assert [role for role, _ in llm.calls] == ["escalate"]


def test_allow_escalation_false_never_calls_opus():
    llm = llm_returning({"default": [{"text": "xyz", "confidence": 0.1}], "escalate": []})
    Restorer(llm=llm, decider=NoDecider()).restore_gap("svasti śrī ", " perunilac", 15, router="routed",
                                                       allow_escalation=False)
    assert [role for role, _ in llm.calls] == ["default"]


def test_constraints_drop_non_iso_and_flag_length():
    llm = llm_returning({"default": [{"text": "paṉmaṟku", "confidence": 0.9}, {"text": "bad#chars", "confidence": 0.9},
                                     {"text": "paṉmaṟkuvukkāka", "confidence": 0.8}], "escalate": []})
    g = Restorer(llm=llm, decider=NoDecider()).restore_gap("svasti śrī kōvirājakēcari", " yāṇṭu", 8,
                                                            router="sonnet", max_candidates=20)
    texts = {c.text: c for c in g.candidates}
    assert "bad#chars" not in texts
    assert texts["paṉmaṟkuvukkāka"].length_ok is False and texts["paṉmaṟku"].length_ok is True


def test_without_live_flag_bedrock_refuses(monkeypatch, tmp_path):
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    with pytest.raises(LiveCallsDisabled):
        BedrockLLM(cache_dir=tmp_path).complete("default", "s", "p")


def test_bedrock_cache_hit_needs_no_network(monkeypatch, tmp_path):
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    llm = BedrockLLM(cache_dir=tmp_path)
    key = llm.cache.key(CFG.model_id("default"), "s", "p", 1024)
    from ezhuthu.agent.llm import LLMResponse

    llm.cache.put(key, LLMResponse("cached text", CFG.model_id("default"), 3, 4))
    r = llm.complete("default", "s", "p")
    assert r.cached and r.text == "cached text" and llm.ledger.cached_calls == 1 and llm.ledger.calls == 0


def test_parse_candidates_tolerates_prose():
    assert parse_candidates('Here: {"candidates": [{"text": "a", "confidence": 2}, "b"]} thanks') == [
        ("a", 1.0), ("b", None)]
    assert parse_candidates("no json") == []


def test_baselines():
    r = Restorer(decider=NoDecider())
    assert copy_best_parallel(r, "mahādēvarkku nantā viḷakku ", " vaitta āṭu", 7)[0][0] == "oṉṟukku"
    ng = ngram_fill(r, "cantirātittavar ", " ivai", 9, k=5)
    assert ng[0][0] == "celvatāka" and abs(sum(c for _, c in ng) - 1) < 1e-3
    zs = zero_shot(llm_returning({"default": [{"text": "x", "confidence": 0.3}]}), "a ", " b", 1)
    assert zs == [("x", 0.3)]


def test_strands_tools_wrap_engine():
    r = Restorer(decider=NoDecider())
    tools = {t.tool_name: t for t in make_tools(r)}
    assert set(tools) == {"retrieve_parallels", "propose_fills", "check_constraints", "rank_and_decide",
                          "ontology_hints"}
    out = tools["check_constraints"](candidates=["paṉmaṟku", "x#"], gap_chars=8)
    assert [o["kept"] for o in out] == [True, False]
    assert tools["rank_and_decide"](left="cantirātittavar ", right=" ivai", gap_chars=9)["candidates"]


def test_ontology_stub_and_port():
    onto = get_ontology()
    assert isinstance(onto, StubOntology)
    hints = onto.hints_for_gap("cantirātittavar ", " ivai")
    assert any(h.id == "ez:formula/candradityavar" for h in hints)
    assert any(h.to_api()["kind"] == "grant" for h in onto.find_entities("nantā viḷakku oṉṟu"))


def test_http_decider_unreachable_is_unavailable():
    d = HttpDecider("http://127.0.0.1:9")
    assert d.available() is False
