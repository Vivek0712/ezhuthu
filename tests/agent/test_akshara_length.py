"""Issue #26: every gap-length comparison counts Tamil letters (aksharas), the unit of ``gap_chars``.

Before the fix ``gap_chars``/``[?N]`` counted letters but the length check, the copy floor, the copy baseline, the
n-gram fill length, the alignment window and the LLM prompt counted ISO-15919 characters, so 130 of 443 VAL expert
targets failed the restorer's own length check.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ezhuthu.agent.baselines import copy_best_parallel
from ezhuthu.agent.calibration import CalibrationTable
from ezhuthu.agent.config import load_models_config
from ezhuthu.agent.data import load_corpus_lines
from ezhuthu.agent.decider import NoDecider
from ezhuthu.agent.ngram import CharNgram
from ezhuthu.agent.prompts import propose_max_tokens, propose_prompt
from ezhuthu.agent.restorer import Restorer, length_ok, length_tolerance
from ezhuthu.agent.retrieval import Parallel, align
from ezhuthu.agent.text import akshara_len, akshara_span_end, akshara_span_start, normalize_iso

ROOT = Path(__file__).resolve().parents[2]
CFG = load_models_config()


@pytest.mark.parametrize(("text", "n"), [
    ("yañ ceytā", 5),  # ya ñ ce y tā: 9 ISO characters
    ("paṉmaṟku", 5), ("celvatāka", 5), ("kai", 1), ("k", 1), ("kka", 2), ("aḵtu", 3), ("rāja-rāja", 4),
    ("", 0), ("  ", 0),
])
def test_akshara_len_counts_tamil_letters(text, n):
    assert akshara_len(text) == n


@pytest.mark.parametrize("split", ["val", "test"])
def test_every_expert_target_has_its_gap_length_in_letters(split):
    """The benchmark's gap_chars is akshara_len of the target, also after the restorer's normalisation; and no
    expert target fails the restorer's length check any more (VAL: 130/443 failed when it counted characters)."""
    path = ROOT / "benchmark" / f"items.{split}.jsonl"
    if not path.exists():
        pytest.skip("benchmark not built")
    items = [json.loads(line) for line in path.open(encoding="utf-8")]
    items = [it for it in items if it["kind"] == "supplied"]
    assert items
    assert all(akshara_len(normalize_iso(it["target"])) == it["gap_chars"] for it in items)
    assert sum(not length_ok(normalize_iso(it["target"]), it["gap_chars"]) for it in items) == 0
    old_fail = sum(abs(len(normalize_iso(it["target"])) - it["gap_chars"]) > length_tolerance(it["gap_chars"])
                   for it in items)
    assert old_fail > 0  # the bug this test guards against was real on this split


def test_length_ok_uses_letters_not_characters():
    assert length_ok("yañ ceytā", 5)  # 5 letters, 9 characters
    assert not length_ok("yañ ceytā", 9)  # 5 letters vs 9: outside the tolerance of 3
    assert not length_ok("paṉmaṟkuvukkāka", 5)  # 9 letters


def test_span_helpers_take_whole_letters():
    line = "kōyilukku nilam"
    assert line[:akshara_span_end(line, 0, 2)] == "kōyi"  # kō yi, not the consonant of "lu"
    assert line[akshara_span_start(line, len("kōyilukku"), 2):len("kōyilukku")] == "kku"  # k ku
    assert akshara_span_end("kai", 0, 1) == 3


def test_one_anchor_alignment_window_is_counted_in_letters():
    line = "svasti śrī kōvirājakēcaripaṉmaṟku yāṇṭu"
    # left anchor only: the window after it holds 5 letters (paṉmaṟku), not 5 characters ("paṉma")
    assert align(line, "kōvirājakēcari", "", 5).fill == "paṉmaṟku"
    # right anchor only: the 5 letters before it
    assert align(line, "", " yāṇṭu", 5).fill == "paṉmaṟku"


def test_ngram_fill_returns_fills_of_exactly_n_letters():
    lm = CharNgram().fit(ln.text for ln in load_corpus_lines())
    out = lm.fill("cantirātittavar ", " vaittēn", 5, k=5)
    assert out and out[0][0] == "celvatāka"
    assert all(akshara_len(t) == 5 for t, _ in out)


def _restorer_with(parallels: list[Parallel]) -> Restorer:
    # the issue #26 pre-rank (no 5-gram term): these tests are about the length unit, not the deployed ranking
    r = Restorer(decider=NoDecider(), use_ontology=False,
                 settings=CFG.restorer.with_(strategy="prerank", ngram_prerank=False), calibration=CalibrationTable())
    r.retrieve_parallels = lambda *a, **k: list(parallels)  # type: ignore[method-assign]
    return r


def test_copy_baseline_and_copy_floor_keep_a_fill_that_is_long_in_characters():
    """A 5-letter parallel fill spelled with 9 characters was dropped by the copy baseline (|9-5| > 2) and could
    not be the copy floor; it is now both."""
    pars = [Parallel("A", "1", "s", None, 90.0, "yañ ceytā"), Parallel("B", "1", "s", None, 40.0, "kōyil")]
    r = _restorer_with(pars)
    assert copy_best_parallel(r, "rāja-rā ", " niṉaippiṉ", 5)[0][0] == "yañ ceytā"
    g = r.restore_gap("rāja-rā ", " niṉaippiṉ", 5, router="none", max_candidates=20)
    floor = next(c for c in g.candidates if c.copy_floor)
    assert floor.text == "yañ ceytā" and floor.length_ok and g.best.text == "yañ ceytā"


def test_unknown_gap_length_is_estimated_in_letters():
    pars = [Parallel("A", "1", "s", None, 90.0, "yañ ceytā"), Parallel("B", "1", "s", None, 80.0, "paṉmaṟku")]
    assert _restorer_with(pars)._estimate_len(None, pars) == 5  # both 5 letters (9 and 8 characters)


def test_propose_prompt_states_the_gap_in_letters():
    p = propose_prompt("a", "b", 5, [], [], 8)
    assert "about 5 Tamil letters" in p and "spaces and hyphens do not count" in p
    assert "ISO-15919 characters, spaces count" not in p
    # the output budget scales with the characters a 5-letter fill takes (about 9), not 5
    assert propose_max_tokens(8, 20) > 60 + 8 * (int(20 * 1.2) + 10)
