"""Split-aware build (--splits train) and the held-out hint evaluation."""

import json
import shutil
from pathlib import Path

import pytest

from ezhuthu.ontology.build import build, split_filter
from ezhuthu.ontology.hint_eval import evaluate_items
from ezhuthu.ontology.lookup import Ontology

HERE = Path(__file__).parent
REPO = HERE.parents[1]
DHARMA = HERE / "fixtures" / "dharma"


def _bench(path: Path, splits: dict[str, str]) -> Path:
    path.write_text("".join(json.dumps({"id": i, "split": s}) + "\n" for i, s in splits.items()), encoding="utf-8")
    return path


def _build(tmp: Path, **kw) -> Path:
    out = tmp / "ontology"
    (out / "seeds").mkdir(parents=True)
    for p in (REPO / "ontology" / "seeds").glob("*.yaml"):
        shutil.copy(p, out / "seeds" / p.name)
    build(DHARMA, out, wikidata_snapshot=None, **kw)
    return out


def _ids(out: Path) -> dict[str, dict]:
    return {r["id"]: r for p in (out / "lookups").glob("*.json") for r in json.loads(p.read_text())}


def test_train_only_build_drops_held_out_editions(tmp_path):
    bench = _bench(tmp_path / "b.jsonl", {"DHARMA_INSTest00001": "train", "DHARMA_INSTest00002": "test"})
    full = _ids(_build(tmp_path / "full"))
    out = _build(tmp_path / "train", splits={"train"}, benchmarks=[bench])
    ids = _ids(out)
    # Rājarāja I and his meykkīrtti are attested only in the test edition: gone from the train build
    assert "ez:ruler/rajaraja-i" in full and "ez:ruler/rajaraja-i" not in ids
    assert "ez:formula/tirumakal-pola" in full and "ez:formula/tirumakal-pola" not in ids
    refs = {ref.split(":")[0] for r in ids.values() for ref in r["attested_in"]}
    assert refs <= {"DHARMA_INSTest00001"}
    sp = json.loads((out / "coverage.json").read_text())["splits"]
    assert sp["used"] == ["train"] and sp["included_inscriptions"] == ["DHARMA_INSTest00001"]
    assert sp["excluded_held_out"] == 1


def test_split_filter_is_strict_across_benchmarks_and_unlisted_editions():
    a = {"x": "train", "y": "train", "z": "val"}
    b = {"x": "train", "y": "test", "z": "train"}
    allowed, info = split_filter(["x", "y", "z", "w"], {"train"}, [a, b])
    assert allowed == {"x"}  # y/z are held out in one of the two benchmarks; w is listed in neither
    assert info["excluded_held_out"] == 2 and info["excluded_not_in_benchmark"] == 1
    assert [bm["per_split"] for bm in info["benchmarks"]] == [{"train": 2, "val": 1, "test": 0},
                                                              {"train": 2, "val": 0, "test": 1}]
    with pytest.raises(ValueError):
        split_filter(["x"], {"train"}, [])


def test_build_rejects_unknown_split(tmp_path):
    bench = _bench(tmp_path / "b.jsonl", {"DHARMA_INSTest00001": "train"})
    with pytest.raises(ValueError, match="unknown split"):
        _build(tmp_path / "o", splits={"dev"}, benchmarks=[bench])


def test_held_out_eval_scores_items_and_refuses_leaked_inscriptions(tmp_path):
    bench = _bench(tmp_path / "b.jsonl", {"DHARMA_INSTest00001": "train", "DHARMA_INSTest00002": "test"})
    onto = Ontology(_build(tmp_path / "o", splits={"train"}, benchmarks=[bench]))
    items = tmp_path / "items.test.jsonl"
    rows = [
        # seed formula (curated, not corpus-derived): restorable without any test edition
        {"inscription_id": "DHARMA_INSTest00002", "left": "svasti ", "right": " maturai koṇṭa", "target": "śrī",
         "gap_chars": 2},
        {"inscription_id": "DHARMA_INSTest00002", "left": "Ivv-ūr ", "right": "yōm", "target": "sabhai", "gap_chars": 3},
        {"inscription_id": "DHARMA_INSTest00002", "left": "a", "right": "b", "target": "x", "gap_chars": 1},
    ]
    items.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    res = evaluate_items(items, k=5, onto=onto)
    assert res["scored"] == 2 and res["skipped_short_target"] == 1
    assert 0 <= res["hits"] <= 2 and res["hit_at_k"] == round(res["hits"] / 2, 4)

    leaked = tmp_path / "items.train.jsonl"
    leaked.write_text(json.dumps({**rows[0], "inscription_id": "DHARMA_INSTest00001"}) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="rebuild with --splits train"):
        evaluate_items(leaked, onto=onto)
    with pytest.raises(ValueError):
        evaluate_items(items, onto=Ontology(_build(tmp_path / "all")))  # an all-editions build is never "held out"
