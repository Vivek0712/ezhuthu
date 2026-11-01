"""Contract tests: every endpoint in contracts/restore-api.md via httpx TestClient, offline."""

import json

import pytest
from fastapi.testclient import TestClient

from ezhuthu.agent.decider import FakeDecider
from ezhuthu.agent.restorer import Restorer
from ezhuthu.api.app import create_app
from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import MemoryStore


def pedagogy_or_restore(state, options):
    if set(options) == {"advance", "repeat", "hint"}:
        return {"advance": 0.2, "repeat": 0.2, "hint": 0.6}
    names = list(options)
    return {n: (0.7 if i == 0 else 0.3 / (len(names) - 1)) for i, n in enumerate(names)}


@pytest.fixture
def client():
    dec = FakeDecider(pedagogy_or_restore)
    svc = EzhuthuService(store=MemoryStore(), llm=None, decider=dec, restorer=Restorer(decider=dec),
                         model_factory=None)
    return TestClient(create_app(svc))


def test_health(client):
    h = client.get("/health").json()
    assert h["status"] == "ok" and h["models"]["default"] == "us.anthropic.claude-sonnet-4-6"


def test_restore_contract(client):
    r = client.post("/api/restore", json={"text": "svasti śrī kōvirājakēcari[?8] yāṇṭu mūṉṟāvatu",
                                          "script": "iso15919", "max_candidates": 3, "allow_escalation": True})
    assert r.status_code == 200
    body = r.json()
    for k in ("restored_text", "restored_text_tamil", "gaps", "models_used", "trace_id", "latency_ms"):
        assert k in body
    g = body["gaps"][0]
    assert {"index", "gap_chars", "decision", "chosen", "candidates"} <= set(g)
    assert g["decision"] in ("fill", "abstain") and len(g["candidates"]) <= 3
    c = g["candidates"][0]
    assert {"text", "text_tamil", "confidence", "model", "decider_model", "parallels", "ontology_hints"} <= set(c)
    assert c["model"] in ("sonnet", "opus", "retrieval") and 0.0 <= c["confidence"] <= 1.0
    for p in c["parallels"]:
        assert set(p) == {"inscription_id", "line_n", "snippet", "url"}
    for h in c["ontology_hints"]:
        assert set(h) == {"id", "kind", "label"}
        assert h["kind"] in ("ruler", "title", "place", "grant", "measure", "formula")


def test_restore_accepts_tamil_script(client):
    body = client.post("/api/restore", json={"text": "சந்திராதித்தவர் [?9] இவை", "script": "tamil"}).json()
    assert body["gaps"][0]["gap_chars"] == 9
    assert body["restored_text_tamil"].startswith("சந்திராதித்தவர்")


def test_restore_rejects_bad_input(client):
    assert client.post("/api/restore", json={"text": "no gap here"}).status_code == 422
    assert client.post("/api/restore", json={"text": "a [?2]", "script": "latin"}).status_code == 422
    assert client.post("/api/restore", json={"text": "a [?2]", "max_candidates": 0}).status_code == 422


def test_evaluate_benchmark_json(client):
    r = client.post("/api/evaluate", json={"benchmark": "test-hard", "limit": 5, "router": "none"})
    assert r.status_code == 200
    b = r.json()
    for k in ("n", "top1", "top20", "cer", "ece", "coverage", "by_router", "items"):
        assert k in b
    assert b["n"] == 2 and "none" in b["by_router"]
    assert {"threshold", "coverage", "accuracy"} <= set(b["coverage"][0])


def test_evaluate_upload_jsonl(client):
    from ezhuthu.agent.config import FIXTURES_DIR

    data = (FIXTURES_DIR / "items.test.jsonl").read_bytes()
    r = client.post("/api/evaluate", files={"file": ("items.jsonl", data, "application/x-ndjson")},
                    data={"router": "baseline-copy", "limit": "3"})
    assert r.status_code == 200 and r.json()["n"] == 3
    r = client.post("/api/evaluate?router=baseline-ngram", content=data,
                    headers={"content-type": "application/x-ndjson"})
    assert r.status_code == 200 and r.json()["n"] == 8


def test_evaluate_offline_reports_effective_router(client):
    b = client.post("/api/evaluate", json={"benchmark": "test", "limit": 2, "router": "routed"}).json()
    assert b["router_requested"] == "routed" and b["router_effective"] == "none" and "none" in b["by_router"]
    assert client.post("/api/evaluate", json={"router": "baseline-zeroshot"}).status_code == 422


def test_evaluate_errors(client):
    assert client.post("/api/evaluate", json={"benchmark": "nosuch"}).status_code == 422
    assert client.post("/api/evaluate", json={"router": "gpt"}).status_code == 422
    assert client.post("/api/evaluate", content=b"{not json", headers={"content-type": "application/json"}
                       ).status_code == 422


def test_corrections_and_queue(client):
    r = client.post("/api/corrections", json={"gap_ref": "trace1:0", "accepted_candidate": "paṉmaṟku", "user": "t"})
    assert r.status_code == 200
    qid = r.json()["id"]
    client.post("/api/corrections", json={"gap_ref": "trace1:1", "corrected_text": "oṉṟukku"})
    q = client.get("/api/queue").json()
    assert q["pending"] == 2 and q["items"][0]["status"] == "pending"
    r = client.post(f"/api/queue/{qid}", json={"action": "edit", "text": "paṉmaṟku "})
    assert r.status_code == 200 and r.json()["status"] == "edited" and r.json()["history"]
    assert client.post(f"/api/queue/{qid}", json={"action": "edit"}).status_code == 422
    assert client.post("/api/queue/nope", json={"action": "approve"}).status_code == 404
    assert client.post("/api/corrections", json={"gap_ref": "x"}).status_code == 422
    assert client.get("/api/queue").json()["pending"] == 1


def test_tutor_endpoints(client):
    lesson = client.post("/api/lesson", json={"inscription_id": "FIXTURE_PALLAVA_001", "level": "L3", "lang": "ta"})
    assert lesson.status_code == 200
    body = lesson.json()
    assert {"session_id", "inscription", "items", "context"} <= set(body)
    assert {"id", "title", "dynasty", "approx_date", "source_url", "restored_text", "restored_text_tamil"} <= set(
        body["inscription"])
    for it in body["items"]:
        assert {"item_id", "type", "prompt_ta", "prompt_en", "script_level", "answer_hidden"} <= set(it)
        assert it["type"] in ("letter", "word", "line") and ("glyph_text" in it or "glyph_svg" in it)
        assert "answer" not in it
    assert {"explain_ta", "explain_en"} <= set(body["context"])
    sid, item = body["session_id"], body["items"][0]

    ans = client.post("/api/answer", json={"session_id": sid, "item_id": item["item_id"], "answer": "qq"}).json()
    assert {"correct", "feedback_ta", "feedback_en", "next_action", "decider_confidence"} <= set(ans)
    assert ans["next_action"] == "hint" and ans["decider_confidence"] == 0.6 and "hint_ta" in ans

    pre = client.post("/api/assessment", json={"session_id": sid, "phase": "pre"}).json()
    assert len(pre["items"]) == 10
    prog = client.get(f"/api/progress/{sid}").json()
    assert {"pre_score", "post_score", "gain", "letters_correct_by_level", "median_seconds_per_letter"} <= set(prog)

    assert client.post("/api/lesson", json={"level": "L6"}).status_code == 422
    assert client.post("/api/lesson", json={"inscription_id": "NOPE"}).status_code == 404
    assert client.post("/api/answer", json={"session_id": "nope", "item_id": "x", "answer": "a"}).status_code == 404
    assert client.post("/api/assessment", json={"phase": "mid"}).status_code == 422
    assert client.get("/api/progress/nope").status_code == 404


def test_vatteluttu_items_carry_svg_key(client):
    body = client.post("/api/lesson", json={"inscription_id": "FIXTURE_PANDYA_001", "level": "L4"}).json()
    assert all(i["glyph_svg"].startswith("vatteluttu:") for i in body["items"])
    json.dumps(body, ensure_ascii=False)  # serialisable
