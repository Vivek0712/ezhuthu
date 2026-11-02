"""Fine-tuning data builder (issue #37): requests are the restorer's own, labels, leakage guards, formats."""

import json
import threading

import pytest

from ezhuthu.agent.data import BenchmarkItem, CorpusLine, load_corpus_lines, load_items
from ezhuthu.agent.decider import FakeDecider
from ezhuthu.agent.llm import FakeLLM, LiveCallsDisabled
from ezhuthu.agent.restorer import DECIDER_INSTRUCTIONS, NOUL_INSTRUCTIONS, Restorer
from ezhuthu.corpus.script import count_aksharas
from ezhuthu.eval import ft_data
from ezhuthu.eval.ft_data import (
    CappedLLM,
    CapturingRestorer,
    assign_folds,
    bench_records,
    build_record,
    context_window,
    edition_groups,
    fold_corpus,
    near_duplicates,
    plan_llm,
    reverse_audit,
    reverse_near_duplicates,
    rows_from_record,
    stats,
    to_decider_lab,
    to_example,
)


def item(i, left, right, target, split="train", insc=None, hard=True):
    return BenchmarkItem(id=f"X{i}:1:0", inscription_id=insc or f"X{i}", collection="c", split=split, line_n="1",
                         left=left, right=right, target=target, gap_chars=count_aksharas(target), hard=hard,
                         age_set=False, source_url="")


def settings3():
    from ezhuthu.agent.config import load_models_config

    return load_models_config().restorer.with_(strategy="choice-topk", top_k=3)


def sonnet(fills):
    def respond(role, system, prompt):
        return "```json\n" + json.dumps({"candidates": [{"text": f, "probability": p} for f, p in fills]},
                                        ensure_ascii=False) + "\n```"
    return FakeLLM(respond)


# ---- leakage -----------------------------------------------------------------------------------------------
def test_context_window_counts_tamil_letters_not_iso_characters():
    w = context_window("svasti śrī kōvirājakēcari", " yāṇṭu mūṉṟāvatu", n=3)
    left, right = w.split("|")
    assert left == "kēcari" and count_aksharas(left) == 3  # 6 ISO characters, 3 letters
    assert right == "yāṇṭu" and count_aksharas(right) == 3  # ṇ (with pulli) is one letter
    assert context_window("", "", n=3) == "|"


def test_near_duplicates_drop_formulaic_train_lines_only():
    held = [item(100, "svasti śrī kō-p-para-kēcari-panmarkku yāṇṭu ", " āvatu", "pattu", split="val")]
    train = [item(1, "svasti śrī kō-p-parakēcaripanmarkku yāṇṭu ", " āvatu", "mūṉṟu"),  # same formula
             item(2, "ivvūr nilam iru-patiṉ ", " kaḻañcu poṉ", "mā")]
    dups = near_duplicates(train, held, threshold=0.9)
    assert set(dups) == {"X1:1:0"}
    assert dups["X1:1:0"]["match"] == "X100:1:0" and dups["X1:1:0"]["split"] == "val"
    assert dups["X1:1:0"]["similarity"] >= 0.9
    assert near_duplicates(train, [], threshold=0.9) == {}


def test_near_duplicates_catch_one_formula_gapped_at_another_point():
    formula = "taṉakkē urimai pūṇṭamai maṉakkoḷa-k kāntaḷūr-c cālai kalam aṟuttaruḷi vēṅkai nāṭum kaṅka-pāṭiyum"
    a, b = formula.index("cālai"), formula.index("kalam")
    held = [item(100, formula[:a], formula[a + 5:], "cālai", split="test")]
    train = [item(1, formula[:b], formula[b + 5:], "kalam")]  # same text, the gap 6 letters later
    assert "X1:1:0" not in near_duplicates(train, held, threshold=0.9, partial_threshold=None)  # windows shift
    dups = near_duplicates(train, held, threshold=0.9)
    assert dups["X1:1:0"]["rule"] == "partial" and dups["X1:1:0"]["match"] == "X100:1:0"


def test_reverse_direction_finds_a_held_out_window_inside_a_longer_train_context():
    formula = "taṉakkē urimai pūṇṭamai maṉakkoḷa-k kāntaḷūr-c cālai kalam aṟuttaruḷi vēṅkai nāṭum kaṅka-pāṭiyum"
    pre = "ivvūr nilam iru-patiṉ kaḻañcu poṉ koṭuttu "  # train line: other text, then the whole formula
    a = formula.index("cālai")
    held = [item(100, formula[:a], formula[a + 5:], "cālai", split="test")]
    b = len(pre) + 4  # gapped inside the unrelated prefix, so its own window is not the formula
    line = pre + formula
    train = [item(1, line[:b], line[b + 3:], line[b:b + 3]), item(2, "ivvūr nilam ", " kaḻañcu poṉ", "mā")]
    assert near_duplicates(train, held) == {}  # the one-way rules miss it
    rev = reverse_near_duplicates(train, held)
    assert set(rev) == {"X1:1:0"} and rev["X1:1:0"]["matches"] == ["X100:1:0"]
    assert rev["X1:1:0"]["split"] == "test" and rev["X1:1:0"]["same_target"] is False
    sym = near_duplicates(train, held, symmetric=True)
    assert sym["X1:1:0"]["rule"] == "reverse" and "X2:1:0" not in sym
    audit = reverse_audit(train, held, thresholds=(90.0, 80.0))
    assert audit["partial_ratio>=90"] == {"kept_train_items": 1, "heldout_items": 1, "heldout_by_split": {"test": 1},
                                          "pairs": 1, "pairs_same_target": 0}
    assert audit["partial_ratio>=80"]["kept_train_items"] >= 1
    assert reverse_near_duplicates(train, []) == {}


def test_reverse_direction_flags_a_shared_target():
    formula = "taṉakkē urimai pūṇṭamai maṉakkoḷa-k kāntaḷūr-c cālai kalam aṟuttaruḷi vēṅkai nāṭum kaṅka-pāṭiyum"
    a = formula.index("cālai")
    held = [item(100, formula[:a], formula[a + 5:], "cālai", split="val")]
    line = "ivvūr nilam iru-patiṉ kaḻañcu poṉ koṭuttu " + formula
    c = line.index("cālai")
    train = [item(1, line[:c], line[c + 5:], "cālai")]
    rev = reverse_near_duplicates(train, held)
    assert rev["X1:1:0"]["same_target"] is True
    assert reverse_audit(train, held, thresholds=(90.0,))["partial_ratio>=90"]["pairs_same_target"] == 1


def test_folds_keep_every_edition_of_a_stone_together_and_are_seeded():
    insc = {"A": {"same_stone_as": ["B"]}, "B": {"same_stone_as": ["A", "C"]}, "C": {}, "D": {}, "E": {}}
    groups = edition_groups(insc)
    assert groups["A"] == groups["B"] == groups["C"] == "A" and groups["D"] == "D"
    f1 = assign_folds(insc, groups, 3, seed=13)
    assert f1 == assign_folds(insc, groups, 3, seed=13)
    assert f1["A"] == f1["B"] == f1["C"]
    lines = [CorpusLine(i, "1", "x") for i in "ABCDE"]
    kept = {ln.inscription_id for ln in fold_corpus(lines, f1, f1["A"])}
    assert not kept & {"A", "B", "C"}


def test_cross_fitted_train_candidates_never_read_the_items_own_inscription():
    it = load_items("test")[0]
    # a train corpus holds every train fill inline, the item's own line included (here: its other edition too)
    own = [CorpusLine("OWN", "1", f"{it.left}{it.target}{it.right}"),
           CorpusLine("OWN_EDITION2", "1", f"{it.left}{it.target}{it.right}")]
    corpus = list(load_corpus_lines()) + own
    it = BenchmarkItem(**{**it.to_dict(), "inscription_id": "OWN", "split": "train"})
    folds = assign_folds({ln.inscription_id for ln in corpus},
                         edition_groups({"OWN": {"same_stone_as": ["OWN_EDITION2"]}}), 2, seed=13)
    leaky = build_record(CapturingRestorer(corpus=corpus, settings=settings3()), it, llm=False, fold=None)
    assert "OWN_EDITION2" in " ".join(leaky["choice"]["state"]["parallel_passages"])  # the leak being guarded
    r = CapturingRestorer(corpus=fold_corpus(corpus, folds, folds["OWN"]), settings=settings3())
    rec = build_record(r, it, llm=False, fold=folds["OWN"])
    assert not any(p.startswith("OWN") for p in rec["choice"]["state"]["parallel_passages"])


def test_plan_llm_is_a_seeded_sample():
    ids = [f"i{n}" for n in range(50)]
    assert plan_llm(ids, 10, 13) == plan_llm(list(reversed(ids)), 10, 13)
    assert len(plan_llm(ids, 10, 13)) == 10 and plan_llm(ids, None, 13) == set(ids)


# ---- the recorded request is the restorer's request ---------------------------------------------------------
def test_recorded_choice_and_noul_requests_equal_what_a_real_decider_receives():
    it = load_items("test")[0]
    fills = [(it.target, 0.7), ("paṉmarku", 0.2)]
    cap = CapturingRestorer(llm=sonnet(fills), settings=settings3())
    rec = build_record(cap, it, llm=True, fold=None)
    assert rec["candidate_source"] == "sonnet+retrieval" and rec["llm_in_pool"]

    dec = FakeDecider(lambda s, o: {k: 1 / len(o) for k in o}, noul_fn=lambda s: 0.5)
    for strategy in ("choice-topk", "noul-topk"):
        real = Restorer(llm=sonnet(fills), decider=dec, use_ontology=False,
                        settings=settings3().with_(strategy=strategy), calibration=cap.calibration)
        real.restore_gap(it.left, it.right, it.gap_chars, router="sonnet", exclude_inscription=it.inscription_id,
                         dynasty=it.dynasty)
    choice_call, noul_calls = dec.calls[0], dec.calls[1:]
    assert rec["choice"]["state"] == choice_call["state"]
    assert rec["choice"]["options"] == choice_call["options"]
    assert rec["choice"]["instructions"] == DECIDER_INSTRUCTIONS and rec["choice"]["name"] == "restoration"
    assert list(rec["choice"]["options"])[-1] == "none" and len(rec["choice"]["options"]) <= 4
    assert [n["state"] for n in rec["noul"]] == [c["state"] for c in noul_calls]
    assert all(n["instructions"] == NOUL_INSTRUCTIONS and n["name"] == "is_restoration" for n in rec["noul"])
    assert len(rec["noul"]) == len(rec["choice"]["options"]) - 1


def test_labels_choice_and_noul():
    it = load_items("test")[0]
    rec = build_record(CapturingRestorer(llm=sonnet([(it.target, 0.9)]), settings=settings3()), it, llm=True,
                       fold=None)
    (c,), nouls = rows_from_record(rec)
    k = c["label"]
    assert k != "none" and c["request"]["questions"]["restoration"]["criteria"][k]["fill"] == it.target
    assert c["target_in_options"] and c["option_keys"][c["label_index"]] == k
    assert [n["label"] for n in nouls].count("yes") == 1
    assert nouls[int(k[1:])]["label"] == "yes"

    miss = {**rec, "target": "zzz"}
    (c2,), n2 = rows_from_record(miss)
    assert c2["label"] == "none" and c2["label_index"] == len(c2["option_keys"]) - 1
    assert {n["label"] for n in n2} == {"no"}


def test_label_is_canonical_spaces_and_case_ignored():
    rec = {"id": "a", "split": "train", "inscription_id": "A", "hard": True, "age_set": False, "gap_letters": 2,
           "target": "Śrī ka", "candidate_source": "retrieval", "pool": [],
           "choice": {"name": "restoration", "instructions": "q", "state": {"s": 1},
                      "options": {"c0": {"fill": "ka"}, "c1": {"fill": "śrīka"}, "none": "none fits"}},
           "noul": []}
    (c,), _ = rows_from_record(rec)
    assert c["label"] == "c1"


def test_budget_cap_falls_back_to_retrieval_and_is_labelled():
    it = load_items("test")[0]
    r = CapturingRestorer(llm=CappedLLM(sonnet([(it.target, 0.9)]), 0), settings=settings3())
    rec = build_record(r, it, llm=True, fold=None)
    assert rec["llm_planned"] and rec["candidate_source"] == "retrieval" and not rec["llm_in_pool"]
    assert r.llm.refused == 1


def test_capped_llm_never_exceeds_its_cap_under_threads():
    capped = CappedLLM(sonnet([("ka", 0.5)]), 5)
    errors = []

    def call():
        try:
            capped.complete("default", "s", "p")
        except LiveCallsDisabled:
            errors.append(1)

    ts = [threading.Thread(target=call) for _ in range(20)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert capped.reserved == 5 and len(errors) == 15 and capped.inner.ledger.calls == 5


def test_no_restorer_change_needed_letter_flag_is_reported():
    assert isinstance(ft_data.restorer_counts_letters(), bool)


# ---- formats -----------------------------------------------------------------------------------------------
def _render_line(desc):  # strands_decider.prompting: render_content, then one line per option
    from ezhuthu.eval.ft_data import _desc

    return " ".join(_desc(desc).split())


def test_example_rows_render_like_the_dict_the_restorer_sends():
    it = load_items("test")[0]
    rec = build_record(CapturingRestorer(llm=sonnet([(it.target, 0.9)]), settings=settings3()), it, llm=True,
                       fold=None)
    (c,), nouls = rows_from_record(rec)
    ex = to_example(c)
    crit = c["request"]["questions"]["restoration"]["criteria"]
    assert ex["kind"] == "choice" and [n for n, _ in ex["options"]] == list(crit)
    assert ex["options"][ex["label"]][0] == c["label"]
    for name, desc in ex["options"]:
        v = crit[name]
        want = " ".join((v if isinstance(v, str) else json.dumps(v, indent=2, ensure_ascii=False)).split())
        assert " ".join(desc.split()) == want and isinstance(desc, str)
    assert set(ex) == {"kind", "state", "instructions", "options", "label", "task", "weight", "instruction_variants"}
    nx = to_example(nouls[0])
    assert nx["kind"] == "noul" and [n for n, _ in nx["options"]] == ["false", "true"]
    assert nx["state"]["candidate"]["fill"] == nouls[0]["fill"]
    assert nx["label"] == (1 if nouls[0]["label"] == "yes" else 0)
    lab = to_decider_lab({**c, "split": "val"})
    assert lab["split"] == "dev" and lab["id"] == c["id"]


def test_bench_records_take_the_first_three_options_plus_none():
    opts = {f"c{i}": {"fill": f, "restored_line": f"x{f}"} for i, f in enumerate(["a", "b", "śrī", "d"])}
    opts["none"] = "none of these candidates fits the gap"
    fr = {"id": "T:1:0", "target": "śrī", "gap_chars": 2, "hard": True, "age_set": False, "inscription_id": "T",
          "request": {"state": {"x": 1}, "instructions": "q", "options": opts, "name": "restoration"},
          "fills": ["a", "b", "śrī", "d"], "llm_confidence": [0.1, 0.2, 0.6, None],
          "fallback_confidence": [0.1, 0.2, 0.6, 0.0]}
    (rec,) = bench_records([fr, {"id": "E", "request": None}])
    assert list(rec["choice"]["options"]) == ["c0", "c1", "c2", "none"] and len(rec["noul"]) == 3
    (c,), nouls = rows_from_record(rec)
    assert c["label"] == "c2" and [n["label"] for n in nouls] == ["no", "no", "yes"]
    s = stats([c], nouls)
    assert s["target_in_top3"] == 1.0 and s["self_report_top3_top1"] == 1.0 and s["first_option_top1"] == 0.0


def test_export_writes_every_format_with_sha256(tmp_path):
    it = load_items("test")[0]
    rec = build_record(CapturingRestorer(llm=sonnet([(it.target, 0.9)]), settings=settings3()), it, llm=True,
                       fold=None)
    (tmp_path / "records").mkdir()
    (tmp_path / "records" / "test.jsonl").write_text(json.dumps(rec, ensure_ascii=False) + "\n")
    m = ft_data.export(tmp_path)
    for f in ("test.choice3.jsonl", "test.noul.jsonl", "strands-decider/test.choice3.jsonl",
              "sparrow/test.noul.jsonl"):
        assert m["files"][f]["rows"] >= 1 and len(m["files"][f]["sha256"]) == 64
    assert m["stats"]["test"]["rows_choice3"] == 1 and "test-hard" in m["stats"]
    assert json.loads((tmp_path / "manifest.json").read_text())["records"]["test"]["rows"] == 1


@pytest.mark.parametrize("n", [0, 1, 5])
def test_window_prefix_suffix_bounds(n):
    w = context_window("abcdeka", "kakiku", n=n)
    left, right = w.split("|")
    assert count_aksharas(left) <= n and count_aksharas(right) <= n
