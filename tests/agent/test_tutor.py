import json

import pytest
from conftest import ScriptedModel

from ezhuthu.agent.decider import FakeDecider, NoDecider
from ezhuthu.agent.restorer import Restorer
from ezhuthu.agent.tutor import policy
from ezhuthu.agent.tutor.feedback import explain_template, hint_for
from ezhuthu.agent.tutor.lesson import assessment_items, build_items, grade, make_item
from ezhuthu.agent.tutor.service import BadRequest, NotFound, TutorService
from ezhuthu.api.storage import MemoryStore


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def svc(decider=None, model=None, clock=None):
    r = Restorer(decider=decider or NoDecider())
    return TutorService(MemoryStore(), r, decider or NoDecider(),
                        model_factory=(lambda: model) if model else None, clock=clock or Clock())


def test_build_items_levels_and_types():
    items = build_items("svasti śrī kōvirājakēcaripaṉmaṟku yāṇṭu irupattirāvatu", "L5", seed=1)
    kinds = [i.type for i in items]
    assert kinds.count("letter") == 6 and kinds.count("word") == 3 and kinds.count("line") == 1
    assert all(i.script_level == "L5" and i.font == "Noto Sans Brahmi" for i in items)
    assert all("answer" not in i.to_api() and i.to_api()["answer_hidden"] for i in items)
    with pytest.raises(ValueError):
        build_items("ka", "L9")


def test_assessment_is_ten_items_two_per_level_and_deterministic():
    a = assessment_items("pre", 42)
    assert len(a) == 10 and [i.script_level for i in a] == ["L1", "L1", "L2", "L2", "L3", "L3", "L4", "L4",
                                                             "L5", "L5"]
    assert [i.answer for i in a] == [i.answer for i in assessment_items("pre", 42)]
    assert [i.answer for i in a] != [i.answer for i in assessment_items("post", 42)]


def test_grade_accepts_tamil_iso_and_period_spelling():
    assert grade(make_item("letter", "kō", "L1"), "கோ")[0]
    assert grade(make_item("letter", "kō", "L1"), "kō")[0]
    assert grade(make_item("letter", "ka", "L1"), "k")[0]  # inherent vowel left off
    assert not grade(make_item("letter", "kō", "L1"), "ko")[0]  # modern Tamil marks length
    assert grade(make_item("letter", "kō", "L2"), "ko")[0]  # Chola-era script does not
    ok, err = grade(make_item("line", "nantā viḷakku oṉṟu", "L1"), "nanta viḷakku oṉṟu")
    assert ok and 0 < err <= 0.15


def test_policy_rules_and_guardrails():
    st = {"correct": False, "attempts_on_item": 1, "hint_already_given": False}
    assert policy.decide(NoDecider(), st).action == "hint"
    assert policy.decide(NoDecider(), {**st, "hint_already_given": True, "attempts_on_item": 2}).action == "repeat"
    assert policy.decide(NoDecider(), {**st, "attempts_on_item": 3}).action == "advance"
    always_hint = FakeDecider(lambda s, o: {"advance": 0.1, "repeat": 0.1, "hint": 0.8})
    d = policy.decide(always_hint, {**st, "correct": True})
    assert d.action == "advance" and d.overridden and d.source == "fake-decider"
    d = policy.decide(always_hint, st)
    assert d.action == "hint" and d.confidence == 0.8 and not d.overridden


def test_hints_do_not_reveal_answer():
    ta, en = hint_for("letter", "kō")
    assert "கோ" not in ta and "க" not in ta.replace("குறிப்பு", "") and "vallinam" in en and "«ō»" in en
    ta, en = hint_for("word", "nantā")
    assert "nantā" not in en and "3 letters" in en
    for letter in ("ka", "ṉa", "pa", "ma", "ta", "śa"):  # consonant+a: "k" alone is graded correct for "ka"
        ta, en = hint_for("letter", letter)
        cons = letter[:-1]
        assert f"«{cons}" not in en and f" {cons} " not in en and f"«{cons}a»" not in en


def test_explain_template_uses_only_facts():
    out = explain_template({"dynasty": "Chola", "approx_date": None, "level": "L2",
                            "entities": [{"kind": "grant_type", "label": "nantā viḷakku", "label_ta": "நந்தா விளக்கு"}],
                            "abstained_gaps": 1})
    assert "சோழர்" in out["explain_ta"] and "நந்தா விளக்கு" in out["explain_ta"]
    assert "experts are unsure" in out["explain_en"]
    assert "correct" not in out["explain_en"].lower()


def test_lesson_runs_graph_offline_with_template():
    s = svc()
    out = s.lesson(inscription_id="FIXTURE_CHOLA_001", level="L2")
    assert out["graph"]["nodes"] == ["restore", "lesson_builder", "explain_template"]
    assert out["context"]["explained_by"] == "template"
    assert out["context"]["ruler"] == "rājakēcari" and out["context"]["grant"] == "nantā viḷakku"
    assert out["inscription"]["restored_text_tamil"].startswith("ஸ்வஸ்தி")
    assert all(i["script_level"] == "L2" for i in out["items"])
    with pytest.raises(NotFound):
        s.lesson(inscription_id="NOPE")
    with pytest.raises(BadRequest):
        s.lesson(level="L7")


def test_lesson_with_gap_restores_then_teaches():
    s = svc()
    out = s.lesson(text="svasti śrī kōvirājakēcari[?8] yāṇṭu mūṉṟāvatu", level="L1")
    assert out["restoration"]["gaps"][0]["candidates"][0]["text"] == "paṉmaṟku"
    assert "[?" not in " ".join(i.get("glyph_text") or "" for i in out["items"] if i["type"] != "line")


def test_lesson_graph_runs_tutor_assessor_swarm():
    explain = {"explain_ta": "இது சோழர் காலக் கல்வெட்டு.", "explain_en": "This is a Chola inscription."}
    model = ScriptedModel([
        {"tool": "handoff_to_agent", "input": {"agent_name": "assessor", "message": "check this draft"}},
        "Draft handed to the assessor.",  # the tutor's loop closes after the handoff tool result
        json.dumps(explain, ensure_ascii=False),  # the assessor's final JSON
    ])
    out = svc(model=model).lesson(inscription_id="FIXTURE_CHOLA_002", level="L1")
    assert out["graph"]["nodes"] == ["restore", "lesson_builder", "tutor_team"]
    assert out["context"]["explained_by"] == "tutor_team"
    assert out["context"]["explain_ta"] == explain["explain_ta"]
    # the tutor saw the lesson facts handed over by the lesson_builder node
    first_prompt = json.dumps(model.seen[0]["messages"], ensure_ascii=False)
    assert "śrīrājarājīcuram" in first_prompt and "handoff_to_agent" in model.seen[0]["tools"]
    assert len(model.seen) == 3  # tutor (tool call), tutor (close), assessor
    assert "Assessor" in model.seen[2]["system"]


def test_swarm_without_json_falls_back_to_template():
    out = svc(model=ScriptedModel(["I cannot help with that."])).lesson(inscription_id="FIXTURE_CHOLA_002")
    assert out["context"]["explained_by"] == "template-fallback" and out["context"]["explain_ta"]


def test_answer_flow_pre_post_and_progress():
    clock = Clock()
    s = svc(clock=clock)
    pre = s.assessment(None, "pre")
    sid = pre["session_id"]
    items = s.store.get("session", sid)["items"]
    for i, it in enumerate(pre["items"]):
        clock.t += 4.0
        ans = items[it["item_id"]]["answer"] if i < 3 else "zz"
        r = s.answer(sid, it["item_id"], ans)
        assert r["next_action"] == "advance" and r["decider_source"] == "assessment"
        assert "«" not in r["feedback_ta"]  # tests do not reveal answers
    assert s.assessment(sid, "pre")["items"] == pre["items"]  # idempotent per phase

    lesson = s.lesson(inscription_id="FIXTURE_CHOLA_001", level="L1", session_id=sid)
    assert lesson["session_id"] == sid
    it = lesson["items"][0]
    clock.t += 2.0
    r = s.answer(sid, it["item_id"], "wrong")
    assert r["next_action"] == "hint" and r["hint_ta"] and r["decider_confidence"] is None

    post = s.assessment(sid, "post")
    for it in post["items"]:
        clock.t += 2.0
        s.answer(sid, it["item_id"], s.store.get("session", sid)["items"][it["item_id"]]["answer"])
    p = s.progress(sid)
    assert p["pre_score"] == 0.3 and p["post_score"] == 1.0 and p["gain"] == 0.7
    assert sum(p["letters_correct_by_level"].values()) == 13
    assert p["median_seconds_per_letter"] == 2.0
    with pytest.raises(NotFound):
        s.answer(sid, "missing", "x")
    with pytest.raises(NotFound):
        s.progress("missing")
