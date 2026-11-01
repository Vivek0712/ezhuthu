"""The benchmark numbers quoted in README.md and docs/CHARTER.md match benchmark/stats.json.

Each claim is a regex for the sentence that states it and the value it must have. When a sentence is
reworded, update its pattern here; when the benchmark is rebuilt, the docs must follow stats.json.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATS_PATH = ROOT / "benchmark" / "stats.json"

pytestmark = pytest.mark.skipif(not STATS_PATH.exists(), reason="benchmark not built")

N = r"([\d,]+)"  # a number as written in prose: 1,320


def _stats() -> dict:
    return json.loads(STATS_PATH.read_text(encoding="utf-8"))


def _expected(st: dict) -> dict[str, list[tuple[str, list[int]]]]:
    test = st["per_split"]["test"]
    pallava = st["per_collection"]["tfa-pallava-epigraphy"]["items"]
    uttiramerur = st["per_collection"]["tfa-uttiramerur-epigraphy"]["items"]
    damaged_pct = round(100 * st["inscriptions_damaged"] / st["inscriptions"])
    lic = st["licences"]
    return {
        "README.md": [
            (rf"The corpus is \*\*{N}\*\* DHARMA inscriptions, of which \*\*{N}%\*\* are damaged",
             [st["inscriptions"], damaged_pct]),
            (rf"Expert restorations in the benchmark \| \*\*{N}\*\* \(test \*\*{N}\*\*, test-hard \*\*{N}\*\*\)",
             [st["items"], test["items"], test["hard"]]),
            (rf"over 1,100 years old \(Pallava collection only\) \| \*\*{N}\*\* \(age set with Uttiramerur: \*\*{N}\*\*\)",
             [pallava, st["age_set_items"]]),
            (rf"declare \*\*CC BY-SA 4.0\*\* \({N} of {N}; the other {N} have no licence",
             [lic["CC BY-SA 4.0"], st["inscriptions"], lic["(none in header)"]]),
        ],
        "docs/CHARTER.md": [
            (rf"come from {N} published DHARMA editions \(the edition files declare CC BY-SA 4.0\), {N} \({N}%\)"
             + r" of which have damaged passages",
             [st["inscriptions"], st["inscriptions_damaged"], damaged_pct]),
            (rf"benchmark of {N} expert restorations in Tamil lines \(test {N}, of which {N} are hard",
             [st["items"], test["items"], test["hard"]]),
            (rf"including {N} in Pallava inscriptions over 1,100 years old \(the benchmark's age set adds {N}"
             + rf" from Uttiramerur, {N} in all\)",
             [pallava, uttiramerur, st["age_set_items"]]),
            (rf'"1,100 years old" applies only to the Pallava collection \({N} restorations\)\. The age set also'
             + rf" includes {N} Uttiramerur restorations",
             [pallava, uttiramerur]),
        ],
    }


# Planning numbers from before the benchmark was built; none of them is true of the data.
STALE = {
    "README.md": [r"12,900", r"3,800", r"CC BY 4\.0", r"\b87%"],
    "docs/CHARTER.md": [r"12,900", r"3,800", r"CC BY 4\.0", r"\b87%", r"1,200 published"],
}


def _int(text: str) -> int:
    return int(text.replace(",", ""))


@pytest.mark.parametrize("doc", ["README.md", "docs/CHARTER.md"])
def test_doc_numbers_match_stats(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for pattern, want in _expected(_stats())[doc]:
        m = re.search(pattern, text)
        assert m, f"{doc}: claim not found (reworded? update tests/test_doc_numbers.py): {pattern}"
        got = [_int(g) for g in m.groups()]
        assert got == want, f"{doc}: {m.group(0)!r} says {got}, benchmark/stats.json says {want}"


@pytest.mark.parametrize("doc", ["README.md", "docs/CHARTER.md"])
def test_doc_has_no_planning_numbers(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for pattern in STALE[doc]:
        assert not re.search(pattern, text), f"{doc} still quotes the planning number {pattern!r}"


def test_expected_values_are_internally_consistent():
    """Guards the test itself: the derived values add up the way the data card says."""
    st = _stats()
    e = {doc: [v for _, vs in claims for v in vs] for doc, claims in _expected(st).items()}
    assert st["per_collection"]["tfa-pallava-epigraphy"]["items"] + st["per_collection"][
        "tfa-uttiramerur-epigraphy"]["items"] == st["age_set_items"]
    assert sum(st["licences"].values()) == st["inscriptions"]
    assert all(isinstance(v, int) and v > 0 for vs in e.values() for v in vs)
