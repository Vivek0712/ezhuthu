"""The character 5-gram's fills must not depend on the process (QA on PR #31).

``CharNgram.fill`` built its alphabet by iterating a ``set`` and ranked with ``heapq.nlargest`` on the log-prob
alone, so equal log-probs came out in hash order: with ``PYTHONHASHSEED`` varying, the 5-gram baseline's TEST top-1
was 0.5714 on some seeds and 0.5666 on others, and 30 of the 856 VAL+TEST gaps got different 5-gram proposals in the
restorer's candidate pool. Each case below runs ``fill`` in fresh interpreters with different hash seeds.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCHMARK = ROOT / "benchmark" / "corpus_lines.jsonl"
SEEDS = ("0", "1", "42", "31337")

# Gaps whose 5-gram proposals varied with the hash seed before the fix (VAL and TEST).
VARYING_IDS = ["DHARMA_INSCirkali00034:1:11", "DHARMA_INSCirkali00034:2:8", "DHARMA_INSMelKil00011:3:1",
               "DHARMA_INSCirkali00008:7:0", "DHARMA_INSCirkali00013:6:0", "DHARMA_INSCirkali00013:11:0"]

TOY = r"""
import json, sys
from ezhuthu.agent.ngram import CharNgram
# every letter is equally likely after every context: all beams tie, so only the tie-break orders them
lm = CharNgram(order=2).fit(["ka ta pa ma", "ta pa ma ka", "pa ma ka ta", "ma ka ta pa"])
print(json.dumps([lm.fill("ka ", " ma", n, k=8, beam=4) for n in (1, 2)], ensure_ascii=False))
"""

REAL = r"""
import json, sys
from ezhuthu.agent.data import load_corpus_lines, load_items
from ezhuthu.agent.ngram import CharNgram
ids = set(json.loads(sys.argv[1]))
lm = CharNgram().fit(ln.text for ln in load_corpus_lines())
items = [it for split in ("val", "test") for it in load_items(split) if it.id in ids]
print(json.dumps({it.id: [lm.fill(it.left, it.right, it.gap_chars, k=3),
                          lm.fill(it.left, it.right, it.gap_chars, k=20, beam=20)] for it in items},
                 ensure_ascii=False))
"""


def _run(code: str, seed: str, *args: str, fixtures: bool = True) -> str:
    env = {**os.environ, "PYTHONHASHSEED": seed}
    if not fixtures:  # the real benchmark (conftest points unit tests at the fixtures)
        env.pop("EZHUTHU_FIXTURES", None)
        env["EZHUTHU_BENCHMARK_DIR"] = str(BENCHMARK.parent)
    out = subprocess.run([sys.executable, "-c", code, *args], env=env, capture_output=True, text=True, check=True,
                         timeout=600)
    return out.stdout


def test_fill_is_identical_across_hash_seeds_on_ties():
    outs = {s: _run(TOY, s) for s in SEEDS}
    assert len(set(outs.values())) == 1, outs
    fills = json.loads(outs["0"])
    assert fills[0] and all(len(x) == 2 for x in fills[0])
    lps = [lp for _, lp in fills[0]]
    # ties are listed in string order
    assert [t for t, lp in fills[0] if lp == lps[0]] == sorted(t for t, lp in fills[0] if lp == lps[0])


@pytest.mark.skipif(not BENCHMARK.is_file(), reason="benchmark not built")
def test_fill_on_benchmark_gaps_is_identical_across_hash_seeds():
    outs = {s: _run(REAL, s, json.dumps(VARYING_IDS), fixtures=False) for s in SEEDS}
    assert len(set(outs.values())) == 1
    got = json.loads(outs["0"])
    assert set(got) == set(VARYING_IDS)
    assert all(pipe and base for pipe, base in got.values())
