"""Interpreter: letters -> words (with their letter ids) -> modern Tamil phrase -> meaning. FakeLLM only."""

from __future__ import annotations

import json

import pytest

from ezhuthu.agent.interpreter import (
    Interpreter,
    InterpretError,
    Letter,
    attested,
    letters_from_text,
    lexicon_hints,
    parse_interpret_reply,
)
from ezhuthu.agent.llm import FakeLLM, LiveCallsDisabled
from ezhuthu.agent.ontology_port import Hint

LEX = {"குளம்": 21, "குடி": 40, "திரு": 1600, "கோபுரம்": 3, "நிலம்": 477}


def line(n: int, letters: str, cs: list[float | None] | None = None) -> list[Letter]:
    out = []
    for i, ch in enumerate(letters.split()):
        out.append(Letter(n, i, None if ch == "?" else ch, (cs or [None] * 99)[i]))
    return out


LINES = [line(0, "தி ரு க் கோ பு ர ம்", [0.9, 0.8, 0.6, 0.7, 0.8, 0.9, 0.7]),
         line(1, "கு ள ம் ? நி ல ம்", [0.8, 0.7, 0.6, None, 0.6, 0.7, 0.8])]


def reply(words, *, p=0.8, phrase="திருக்கோபுரம் குளம் … நிலம்", en="The sacred gateway; a tank; land.",
          ta="திருக்கோபுரம்; குளம்; நிலம்.") -> str:
    return json.dumps({"words": words, "phrase_ta": phrase, "phrase_iso": "tirukkōpuram kuḷam … nilam",
                       "meaning_en": en, "meaning_ta": ta, "notes": "line 2 letter 4 is unread", "p": p},
                      ensure_ascii=False)


GOOD = [{"ids": ["1.1", "1.2"], "ta": "திரு", "iso": "tiru", "en": "sacred", "p": 0.9},
        {"ids": ["1.3", "1.4", "1.5", "1.6", "1.7"], "ta": "கோபுரம்", "iso": "kōpuram", "en": "gateway tower", "p": 0.8},
        {"ids": ["2.1", "2.2", "2.3"], "ta": "குளம்", "iso": "kuḷam", "en": "tank", "p": 0.8},
        {"ids": ["2.5", "2.6", "2.7"], "ta": "நிலம்", "iso": "nilam", "en": "land", "p": 0.7}]


class StubOnto:
    def __init__(self):
        self.seen: list[str] = []

    def find_entities(self, text: str):
        self.seen.append(text)
        return [Hint("ez:measure/kulam", "measure", "kuḷam"), Hint("ez:measure/kulam", "measure", "kuḷam")]


def test_words_phrase_and_meaning_with_letter_ids_and_grounding():
    onto = StubOnto()
    llm = FakeLLM(lambda role, s, p: reply(GOOD))
    out = Interpreter(llm, ontology=onto, lexicon=LEX).interpret(LINES, context="a stone at a temple gateway")
    assert [w["tamil"] for w in out["words"]] == ["திரு", "கோபுரம்", "குளம்", "நிலம்"]
    assert out["words"][1]["letters"] == [[0, 2], [0, 3], [0, 4], [0, 5], [0, 6]]
    assert out["words"][0]["en"] == "sacred" and out["words"][0]["confidence"] == 0.9
    assert out["phrase_tamil"].startswith("திருக்கோபுரம்") and out["phrase_iso"]
    assert out["meaning_en"] and out["meaning_ta"]
    assert all(w["attested"] for w in out["words"]) and out["words_attested"] == 4
    assert out["models_used"] == ["sonnet"] and not out["escalated"] and out["unassigned"] == []
    # Grounding: the lexicon words found in the letter stream and the ontology's entities are in the prompt.
    prompt = llm.calls[0][1]
    assert "1.1 தி (0.90)" in prompt and "2.4 ?" in prompt
    assert "குளம் (kuḷam), attested 21x, letters 2.1-2.3" in prompt
    assert "measure: kuḷam" in prompt and prompt.count("measure: kuḷam") == 1
    assert "a stone at a temple gateway" in prompt
    assert "tirukkōpuram" in onto.seen[0] or "tiru" in onto.seen[0]


def test_escalates_to_opus_when_sonnet_is_unsure_and_keeps_the_more_confident_answer():
    def responder(role, s, p):
        return reply(GOOD[:1], p=0.3) if role == "default" else reply(GOOD, p=0.7)

    llm = FakeLLM(responder)
    out = Interpreter(llm, ontology=None, lexicon=LEX).interpret(LINES)
    assert [c[0] for c in llm.calls] == ["default", "escalate"]
    assert out["escalated"] and out["models_used"] == ["sonnet", "opus"] and out["model"] == "opus"
    assert len(out["words"]) == 4 and out["confidence"] == 0.7


def test_keeps_sonnet_when_opus_is_less_sure_and_survives_an_escalation_failure():
    llm = FakeLLM(lambda role, s, p: reply(GOOD, p=0.4) if role == "default" else reply(GOOD[:2], p=0.2))
    out = Interpreter(llm, ontology=None, lexicon=LEX).interpret(LINES)
    assert out["model"] == "sonnet" and out["escalated"] and len(out["words"]) == 4

    def boom(role, s, p):
        if role == "escalate":
            raise RuntimeError("throttled")
        return reply(GOOD, p=0.4)

    out = Interpreter(FakeLLM(boom), ontology=None, lexicon=LEX).interpret(LINES)
    assert out["model"] == "sonnet" and len(out["words"]) == 4


def test_no_escalation_when_sonnet_is_sure():
    llm = FakeLLM(lambda role, s, p: reply(GOOD, p=0.9))
    Interpreter(llm, ontology=None, lexicon=LEX).interpret(LINES)
    assert [c[0] for c in llm.calls] == ["default"]


def test_parser_enforces_one_word_per_letter_in_reading_order():
    words = [{"ids": ["1.1", "1.2", "9.9"], "ta": "திரு", "p": 0.9},          # unknown id dropped
             {"ids": ["1.2", "1.3"], "ta": "ருக்", "p": 0.2},                 # 1.2 is shared: moves to this word
             {"ids": ["1.1"], "ta": "தி", "p": 0.5},                          # goes backwards: dropped
             {"ids": ["2.1", "2.2", "2.3", "2.5"], "ta": "குளம்நி", "p": 0.4},  # the unread 2.4 inside is pulled in
             {"ids": [], "ta": "x"}, {"ids": ["2.6"], "ta": ""}, "junk"]
    out = parse_interpret_reply(reply(words), LINES)
    assert [w["tamil"] for w in out["words"]] == ["திரு", "ருக்", "குளம்நி"]
    assert out["words"][0]["letters"] == [[0, 0]] and out["words"][1]["letters"] == [[0, 1], [0, 2]]
    assert out["words"][2]["letters"] == [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]]
    assert [0, 3] in out["unassigned"] and [1, 3] not in out["unassigned"]  # unread letters are never "unassigned"


def test_parser_moves_a_sandhi_letter_to_the_word_it_spells():
    # The model spelled குளம் but gave it only ள ம், leaving கு on the previous word.
    lines = [line(0, "ர கு டி க கு ள ம்")]
    words = [{"ids": ["1.1", "1.2", "1.3", "1.4", "1.5"], "ta": "ர்குடிக்கு", "p": 0.5},
             {"ids": ["1.6", "1.7"], "ta": "குளம்", "p": 0.7}]
    out = parse_interpret_reply(reply(words), lines)
    assert out["words"][0]["letters"] == [[0, 0], [0, 1], [0, 2], [0, 3]]
    assert out["words"][1]["letters"] == [[0, 4], [0, 5], [0, 6]]


def test_parser_survives_garbage_and_code_fences():
    assert parse_interpret_reply("not json", LINES)["words"] == []
    fenced = "```json\n" + reply(GOOD) + "\n```"
    assert len(parse_interpret_reply(fenced, LINES)["words"]) == 4
    out = parse_interpret_reply(json.dumps({"words": GOOD, "p": "high"}), LINES)
    assert out["confidence"] is None and out["meaning_en"] is None


def test_text_input_and_limits():
    lines = letters_from_text("tiru-k-kōpuram\nகுளம் [?2] nilam\n\n")
    assert [[x.ta for x in ln] for ln in lines] == [["தி", "ரு", "க்", "கோ", "பு", "ர", "ம்"],
                                                    ["கு", "ள", "ம்", None, None, "நி", "ல", "ம்"]]
    llm = FakeLLM(lambda role, s, p: reply(GOOD))
    out = Interpreter(llm, ontology=None, lexicon=LEX).interpret_text("tirukkōpuram\nகுளம் [?1] nilam")
    assert out["input"]["lines"] == ["திருக்கோபுரம்", "குளம்?நிலம்"]
    with pytest.raises(InterpretError):
        Interpreter(llm, ontology=None, lexicon=LEX).interpret_text("[?3]")
    with pytest.raises(InterpretError):
        Interpreter(llm, ontology=None, lexicon=LEX).interpret_text("   ")
    with pytest.raises(LiveCallsDisabled):
        Interpreter(None, ontology=None, lexicon=LEX).interpret(LINES)


def test_lexicon_hints_match_at_letter_boundaries_without_pulli_and_across_lines():
    lines = [line(0, "கு ள"), line(1, "ம ? நி ல ம")]
    hints = lexicon_hints(lines, lexicon=LEX)
    # Same length: the more attested word first.
    assert [h["ta"] for h in hints] == ["நிலம்", "குளம்"]
    assert hints[1]["letters"] == ["1.1", "1.2", "2.1"]  # runs on to the next line
    assert attested("குளம", LEX) and not attested("குளமா", LEX)
