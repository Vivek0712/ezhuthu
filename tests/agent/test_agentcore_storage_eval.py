
import pytest

from ezhuthu.agent.data import load_items
from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.restorer import Restorer
from ezhuthu.agentcore_app import ACTIONS, handle
from ezhuthu.api.service import EzhuthuService
from ezhuthu.api.storage import MemoryStore, SQLiteStore
from ezhuthu.eval import run as eval_run
from ezhuthu.eval.metrics import Prediction, coverage_curve, ece, summarize


@pytest.fixture
def service():
    return EzhuthuService(store=MemoryStore(), llm=None, decider=NoDecider(), model_factory=None,
                          admin_token="s3cret", open_review=False)


def test_agentcore_routes_every_action(service):
    assert {"restore", "lesson", "answer", "assessment", "progress", "evaluate"} <= set(ACTIONS)
    r = handle({"action": "restore", "text": "cantirātittavar [?9] ivai"}, service)
    assert r["gaps"][0]["candidates"]
    lesson = handle({"action": "lesson", "inscription_id": "FIXTURE_CHOLA_001", "level": "L1"}, service)
    sid = lesson["session_id"]
    a = handle({"action": "answer", "session_id": sid, "item_id": lesson["items"][0]["item_id"], "answer": "x"},
               service)
    assert a["next_action"] in ("advance", "repeat", "hint")
    assert len(handle({"action": "assessment", "session_id": sid, "phase": "pre"}, service)["items"]) == 10
    assert "gain" in handle({"action": "progress", "session_id": sid}, service)
    ev = handle({"action": "evaluate", "benchmark": "test", "limit": 2, "router": "baseline-copy"}, service)
    assert ev["n"] == 2
    c = handle({"action": "corrections", "gap_ref": "t:0", "corrected_text": "paṉmaṟku"}, service)
    assert handle({"action": "queue"}, service)["pending"] == 1
    denied = handle({"action": "review", "id": c["id"], "review_action": "approve"}, service)
    assert denied["error"]["status"] == 403
    rv = handle({"action": "review", "id": c["id"], "review_action": "approve", "admin_token": "s3cret"}, service)
    assert rv["status"] == "approved"
    assert handle({"action": "review", "id": c["id"]}, service)["error"]["status"] == 422


def test_agentcore_errors_are_structured(service):
    assert handle({"action": "fly"}, service)["error"]["status"] == 422
    assert handle({"action": "answer"}, service)["error"]["status"] == 422
    assert handle({"action": "progress", "session_id": "nope"}, service)["error"]["status"] == 404
    assert handle("not a dict", service)["error"]["status"] == 422


def test_agentcore_http_invocations(service, monkeypatch):
    """The real BedrockAgentCoreApp: POST /invocations with a JSON payload, GET /ping."""
    from starlette.testclient import TestClient

    from ezhuthu import agentcore_app

    monkeypatch.setattr(agentcore_app, "_service", service)
    c = TestClient(agentcore_app.app)
    assert c.get("/ping").status_code == 200
    r = c.post("/invocations", json={"action": "restore", "text": "cantirātittavar [?9] ivai"})
    assert r.status_code == 200 and r.json()["gaps"][0]["gap_chars"] == 9
    assert c.post("/invocations", json={"action": "nope"}).json()["error"]["status"] == 422


@pytest.mark.parametrize("make", [lambda p: MemoryStore(), lambda p: SQLiteStore(str(p / "s.db"))])
def test_stores_roundtrip(tmp_path, make):
    s = make(tmp_path)
    s.put("session", "a", {"x": "எ"})
    s.put("session", "a", {"x": 2})
    s.put("queue", "q1", {"id": "q1"})
    assert s.get("session", "a") == {"x": 2} and s.get("session", "zz") is None
    assert s.list("queue") == [{"id": "q1"}] and s.list("correction") == []
    with pytest.raises(ValueError):
        s.put("bogus", "a", {})


def test_metrics():
    assert ece([0.9, 0.9, 0.1, 0.1], [True, True, False, False]) == pytest.approx(0.1)
    assert ece([1.0], [True]) == 0.0
    cov = coverage_curve([0.9, 0.4], [True, False], thresholds=(0.0, 0.5))
    assert cov == [{"threshold": 0.0, "coverage": 1.0, "accuracy": 0.5},
                   {"threshold": 0.5, "coverage": 0.5, "accuracy": 1.0}]
    p = [Prediction("a", "kōyil", ("kōyil", "x"), 0.8), Prediction("b", "ūr", ("x", "ūr"), 0.3),
         Prediction("c", "nāṭu", (), 0.0, abstained=True)]
    s = summarize(p)
    assert s["top1"] == pytest.approx(1 / 3, abs=1e-4) and s["top20"] == pytest.approx(2 / 3, abs=1e-4)
    assert s["abstain_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert p[1].cer == 1.0 and p[0].cer == 0.0


def test_eval_runner_and_report(tmp_path, monkeypatch):
    items = load_items("test")
    res = eval_run.evaluate_items(items, router="baseline-copy", restorer=Restorer(decider=NoDecider()))
    assert res["n"] == 8 and set(res["by_subset"]) == {"full", "hard", "age"}
    assert res["by_subset"]["hard"]["n"] == 2 and res["by_subset"]["age"]["n"] == 2
    assert 0.0 <= res["top1"] <= res["top20"] <= 1.0
    code = eval_run.main(["--router", "none", "--no-decider", "--out", str(tmp_path), "--limit", "4"])
    assert code == 0
    md = next(tmp_path.glob("*.md")).read_text()
    assert "SYNTHETIC FIXTURE DATA" in md and "fixture-smoke" in next(tmp_path.glob("*.json")).name
    # LLM routers refuse to run without EZHUTHU_LIVE=1
    monkeypatch.delenv("EZHUTHU_LIVE", raising=False)
    assert eval_run.main(["--router", "sonnet", "--out", str(tmp_path)]) == 2


def test_ontology_ablation_changes_candidates():
    with_onto = Restorer(decider=NoDecider()).restore_gap("cantirātittavar ", " ivai", 9)
    without = Restorer(decider=NoDecider(), use_ontology=False).restore_gap("cantirātittavar ", " ivai", 9)
    assert any("ontology" in c.sources for c in with_onto.candidates)
    assert not any("ontology" in c.sources for c in without.candidates)
    assert all(not c.hints for c in without.candidates)
