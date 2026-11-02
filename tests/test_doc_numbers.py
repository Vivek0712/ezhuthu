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
        "design/brand/BRAND.md": [
            (rf'"Over 1,100 years old" applies only to the Pallava collection \({N} restorations\)',
             [pallava]),
        ],
    }


# Planning numbers from before the benchmark was built; none of them is true of the data.
STALE = {
    "README.md": [r"12,900", r"3,800", r"CC BY 4\.0", r"\b87%"],
    "docs/CHARTER.md": [r"12,900", r"3,800", r"CC BY 4\.0", r"\b87%", r"1,200 published"],
    # The age claim once covered the whole age set; only the Pallava items are over 1,100 years old.
    "design/brand/BRAND.md": [r"Pallava and Uttiramerur set", r"Uttiramerur[^.]*over 1,100",
                              r"age set[^.]*over 1,100 years old(?! applies only)"],
    # The note asking the lead to confirm "CC BY 4.0" predates the CC BY-SA 4.0 decision.
    "ontology/README.md": [r"lead should confirm", r"charter's \"CC BY 4\.0\""],
}

DOCS = ["README.md", "docs/CHARTER.md", "design/brand/BRAND.md"]


def _int(text: str) -> int:
    return int(text.replace(",", ""))


@pytest.mark.parametrize("doc", DOCS)
def test_doc_numbers_match_stats(doc):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for pattern, want in _expected(_stats())[doc]:
        m = re.search(pattern, text)
        assert m, f"{doc}: claim not found (reworded? update tests/test_doc_numbers.py): {pattern}"
        got = [_int(g) for g in m.groups()]
        assert got == want, f"{doc}: {m.group(0)!r} says {got}, benchmark/stats.json says {want}"


@pytest.mark.parametrize("doc", sorted(STALE))
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


def test_data_card_does_not_age_uttiramerur():
    """Every Uttiramerur title names a Chola-or-later ruler, so none is securely over 1,100 years old."""
    card = (ROOT / "benchmark" / "DATA_CARD.md").read_text(encoding="utf-8")
    assert "none is securely over 1,100 years old" in card
    assert "not all over 1,100" not in card


def test_licence_covers_editions_without_a_header():
    st = _stats()
    assert st["licences"].get("(none in header)", 0) > 0  # the case the sentence exists for
    text = " ".join((ROOT / "benchmark" / "LICENSE").read_text(encoding="utf-8").split())
    assert re.search(r"Editions with no licence header fall under their repository's LICENCE\.txt, which is CC BY 4\.0", text)


# ---------------------------------------------------------------------------------------------- test eval ------
EVAL_PATH = ROOT / "eval" / "reports" / "2026-11-02-test-eval.json"
DEPLOY_PATH = ROOT / "eval" / "reports" / "2026-11-02-deployed-config.json"
F = r"([\d.]+)"  # a number as written in prose: 49.6, 0.113, 0.0066


def _pct(x: float) -> float:
    return round(100 * x, 1)


def _eval_claims() -> dict[str, list[tuple[str, list[float]]]]:
    """Every restoration number quoted in README.md and docs/CHARTER.md, with its value in the test-eval JSON.
    ``test_restoration_paragraphs_quote_no_unpinned_number`` checks that the results paragraphs hold no other."""
    r = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    c = {n: v["by_subset"]["full"] for n, v in r["configs"].items()}
    p = r["paired"]
    routed, copy, ngram, sonnet = c["routed"], c["copy"], c["ngram"], c["sonnet"]
    ret_dec = next(n for n in c if n.startswith("retrieval-decider-"))
    onto = p["ontology_on_vs_off"]["full"]
    sd, rd = p["sonnet_decider_vs_prerank"]["full"], p["routed_decider_vs_prerank"]["full"]
    gl = r["by_gap_length"]
    long_max = max(gl[n]["4+ letters"]["top1"] for n in gl)
    one_letter_share = round(100 * gl["routed"]["1 letter"]["n"] / routed["n"])
    matched = round(routed["top1"] * routed["n"])
    readme = [
        (rf"\*\*{F}%\*\* \({N} of {N}; copy-from-parallel baseline {F}%, character 5-gram baseline \*\*{F}%\*\*\)",
         [_pct(routed["top1"]), matched, routed["n"], _pct(copy["top1"]), _pct(ngram["top1"])]),
        (rf"ECE \*\*{F}\*\*; fills \*\*{F}%\*\* of test gaps, and \*\*{F}%\*\* of those fills match",
         [routed["ece"], _pct(routed["coverage"]), _pct(routed["selective_accuracy"])]),
        (rf"copying the best parallel passage \(p = {F}\)", [round(r["configs"]["routed"]["vs_copy"]["full"]["p_mcnemar"],
                                                                  2)]),
        (rf"beats both \(p = {F} against the pipeline\)", [round(p["routed_vs_ngram"]["full"]["p_mcnemar"], 4)]),
        (rf"Most test gaps are a single letter \({F}%\)", [one_letter_share]),
        (rf"Sonnet alone: {F}%", [_pct(sonnet["top1"])]),
    ]
    charter = [
        (rf"matches the expert restoration on {N} of {N} test gaps \({F}%\)", [matched, routed["n"],
                                                                                 _pct(routed["top1"])]),
        (rf"against {F}% for copying the best parallel passage", [_pct(copy["top1"])]),
        (rf"and {F}% for a character 5-gram model", [_pct(ngram["top1"])]),
        (rf"the engine fills {F}% of gaps and {F}% of those fills match", [_pct(routed["coverage"]),
                                                                          _pct(routed["selective_accuracy"])]),
        (rf"Sonnet 4.6 alone \({F}%\)", [_pct(sonnet["top1"])]),
        (rf"{F}% of test gaps are a single letter", [one_letter_share]),
        (rf"\({N} hinted gaps, {N} matches gained and {N} lost\)", [onto["n"], onto["only_a"], onto["only_b"]]),
        (rf"\({N} vs {N} discordant gaps with Sonnet, {N} vs {N} routed\)",
         [sd["only_a"], sd["only_b"], rd["only_a"], rd["only_b"]]),
        (rf"\({F}% vs {F}%, p = {F}\)", [_pct(c[ret_dec]["top1"]), _pct(c["prerank"]["top1"]),
                                          round(p[f"{ret_dec}_vs_prerank"]["full"]["p_mcnemar"], 3)]),
        (rf"confidence: on test, {N} of {N} gaps reach Opus, {N} of them by the last two rules",
         [r["configs"]["routed"]["cost"]["opus_items"], routed["n"], r["configs"]["routed"]["pre_escalated"]]),
    ]
    assert long_max <= 1 / 3 + 1e-9  # "no system matches the expert on more than 1 in 3" (gaps of 4+ letters)
    # The deployed configuration (chosen on VAL, TEST scored once): eval/reports/2026-11-02-deployed-config.json
    d = json.loads(DEPLOY_PATH.read_text(encoding="utf-8"))
    df = d["by_subset"]["full"]
    d_matched = round(df["top1"] * df["n"])
    d_vs_ngram = round(d["vs"]["ngram"]["full"]["p_mcnemar"], 4)
    d_long = d["by_gap_length"]["deployed"]["4+ letters"]["top1"]
    assert d_long <= 1 / 3 + 1e-9  # the "1 in 3" sentence still holds with the deployed configuration
    readme += [
        ((rf"the deployed cloud configuration: routed LLMs \+ 5-gram pre-rank, no decider\) \| \*\*{F}%\*\* \({N} of {N}\);"
          rf" at its VAL-calibrated threshold it fills \*\*{F}%\*\* of test gaps, and \*\*{F}%\*\* of those fills match"),
         [_pct(df["top1"]), d_matched, df["n"], _pct(df["coverage"]), _pct(df["selective_accuracy"])]),
        (rf"no decider matches the expert on {F}% of test gaps, above the 5-gram alone \(p = {F};",
         [_pct(df["top1"]), d_vs_ngram]),
        (rf"its latency is measured per gap \(test p90 {F} s\)", [round(d["latency"]["p90_ms"] / 1000, 1)]),
    ]
    d_sonnet_first = d["cost"]["by_model"]["sonnet"]["calls"]  # one Sonnet call per gap that Sonnet answers first
    d_after_sonnet = d["cost"]["opus_items"] - (df["n"] - d_sonnet_first)  # the rest of the Opus gaps pre-escalated
    charter += [
        (rf"on test only {N} of the {N} gaps Sonnet answered first went on to Opus", [d_after_sonnet, d_sonnet_first]),
        ((rf"Its top fill matches the expert on {N} of {N} test gaps \({F}%\), above the 5-gram alone \(p = {F}\); at its"
          rf" validation-fitted thresholds it fills {F}% of gaps and {F}% of those fills match\. Like every system here it"
          rf" is weakest on long gaps \({F}% on gaps of 4 or more letters\)"),
         [d_matched, df["n"], _pct(df["top1"]), d_vs_ngram, _pct(df["coverage"]), _pct(df["selective_accuracy"]),
          _pct(d_long)]),
    ]
    return {"README.md": readme, "docs/CHARTER.md": charter}


@pytest.mark.skipif(not EVAL_PATH.exists(), reason="test evaluation not run")
@pytest.mark.parametrize("doc", ["README.md", "docs/CHARTER.md"])
def test_doc_restoration_numbers_match_the_test_eval(doc):
    text = " ".join((ROOT / doc).read_text(encoding="utf-8").split())
    for pattern, want in _eval_claims()[doc]:
        m = re.search(pattern, text)
        assert m, f"{doc}: claim not found (reworded? update tests/test_doc_numbers.py): {pattern}"
        got = [float(g.replace(",", "")) for g in m.groups()]
        assert got == [float(w) for w in want], f"{doc}: {m.group(0)!r} says {got}, the test-eval JSON says {want}"


# The paragraphs that quote TEST results (by their first words), and the numbers in them that are not TEST results:
# model versions, rule settings, the 60-gap benchmark size, "1 in 3".
RESULT_PARAGRAPHS = {
    "README.md": ["| Fills that match the expert restoration (top-1, test, measured", "| Calibration (ECE) and coverage",
                  "| Fills that match the expert restoration (top-1, test, the deployed", "**What the test evaluation says**"],
    "docs/CHARTER.md": ["**Measured (test, scored once", "**Deployed configuration (chosen afterwards",
                        "1. **Restoration ranking and abstention:**", "2. **Model routing:**"],
}
NOT_RESULTS = {"4.6", "2", "1", "3", "4", "0.6", "12", "60", "19", "3.5", "2610", "26", "2026", "11", "02", "0.5"}


@pytest.mark.skipif(not EVAL_PATH.exists(), reason="test evaluation not run")
@pytest.mark.parametrize("doc", sorted(RESULT_PARAGRAPHS))
def test_restoration_paragraphs_quote_no_unpinned_number(doc):
    """A TEST figure added to a results paragraph without a pin in ``_eval_claims`` fails here."""
    lines = (ROOT / doc).read_text(encoding="utf-8").splitlines()
    claims = _eval_claims()[doc]
    text = " ".join(" ".join(ln.split()) for ln in lines)
    pinned: set[str] = set()
    for pattern, _ in claims:
        m = re.search(pattern, text)
        assert m, pattern
        pinned.update(g for g in m.groups())
    for start in RESULT_PARAGRAPHS[doc]:
        para = next(ln for ln in lines if ln.startswith(start))
        # links, code, "5-gram", "top-1": not quoted figures
        para = re.sub(r"\([^)]*\.md\)|`[^`]*`|\[[^\]]*\]\([^)]*\)|\d+-gram|top-\d+", " ", para)
        for num in re.findall(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?", para):
            assert num in pinned or num in NOT_RESULTS, f"{doc}: {num!r} in {start!r} is not pinned to the test eval"


# Sentences that must stay next to the numbers: what was measured, and what was not (QA on PR #31).
MEASURED_SCOPE = {
    "README.md": [
        "Fills that match the expert restoration (top-1, test, measured with the local 2B decider)",
        ("**These numbers were measured with the local strands-decider-2B and its VAL calibration, a configuration the "
         "cloud runtime never ran; the configuration it does run was chosen afterwards on VAL by a pre-registered rule, "
         "calibrated on VAL and scored once on test"),
        "Fills that match the expert restoration (top-1, test, the deployed cloud configuration",
        # QA on PR #40: the deployed restorer makes no decider call; the decider serves the tutor
        "Restoration (deployed): a decider-free pre-rank with the character 5-gram's score ranks the candidates, with no decider call",
        "Strands Decider makes the tutor's advance / repeat / hint decision",
        "the 27 s proxy limit applies per request",
    ],
    "docs/CHARTER.md": [
        ("with the local 2B decider and its validation calibration (a configuration the cloud runtime never ran; the "
         "deployed one is below), the engine's top fill matches"),
        ("**Deployed configuration (chosen afterwards on validation by a pre-registered rule, calibrated on validation, "
         "test scored once;"),
        "the strongest restorer in that evaluation (the deployed configuration below beats it)",
        "The deployed runtime escalates on the raw (uncalibrated) `prerank-ngram` score of Sonnet's best candidate",
    ],
}


@pytest.mark.parametrize("doc", sorted(MEASURED_SCOPE))
def test_doc_says_which_configuration_was_measured(doc):
    text = " ".join((ROOT / doc).read_text(encoding="utf-8").split())
    for sentence in MEASURED_SCOPE[doc]:
        assert sentence in text, f"{doc} lost the measured-scope sentence: {sentence!r}"
    for word in ("shipped pipeline", "shipped engine", "strongest restorer measured so far",
                 "Strands Decider: ranks LLM candidates", "when the decider's confidence in Sonnet's best candidate"):
        assert word not in text, f"{doc}: the measured configuration is not what the cloud runtime ships"


def test_readme_has_no_tbd_restoration_numbers():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    for row in ("Fills that match the expert restoration", "Calibration (ECE) and coverage"):
        line = next(ln for ln in text.splitlines() if row in ln)
        assert "TBD" not in line
