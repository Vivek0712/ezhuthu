"""The app's instant practice banks (app/web/src/practice/banks/*.json, built by scripts/build_practice.py).

Leakage guard (benchmark/DATA_CARD.md, "Leakage"): practice content comes from the TRAIN split only. No item may
come from a VAL or TEST inscription, from a TRAIN inscription that shares a stone with one, or reuse a VAL/TEST
benchmark item. The committed files must also be exactly what the seeded script builds.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
BANKS = ROOT / "app" / "web" / "src" / "practice" / "banks"
HELD_ITEM_FILES = ("items.val.jsonl", "items.test.jsonl", "items.test-hard.jsonl", "items.test-age.jsonl")

pytestmark = pytest.mark.skipif(not (BENCH / "inscriptions.jsonl").exists(), reason="benchmark not built")


def _read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _bank(name: str) -> dict:
    return json.loads((BANKS / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def splits() -> tuple[dict[str, str], set[str], set[str]]:
    ins = _read(BENCH / "inscriptions.jsonl")
    split = {r["id"]: r["split"] for r in ins}
    held = {i for i, s in split.items() if s != "train"}
    held_items: set[str] = set()
    for f in HELD_ITEM_FILES:
        rows = _read(BENCH / f)
        held |= {r["inscription_id"] for r in rows}
        held_items |= {r["id"] for r in rows}
    for r in ins:
        if any(s in held for s in r.get("same_stone_as") or []):
            held.add(r["id"])
    return split, held, held_items


def _sources() -> list[tuple[str, str]]:
    out = []
    for name in ("words.json", "gaps.json", "formulas.json"):
        out += [(name, it["src"]["inscription_id"]) for it in _bank(name)["items"]]
    for it in _bank("try.json")["words"]:
        out.append(("try.json", it["src"]["inscription_id"]))
    out.append(("worked-example.json", _bank("worked-example.json")["inscription_id"]))
    return out


def test_banks_use_train_inscriptions_only(splits):
    split, held, _ = splits
    sources = _sources()
    assert len({i for _, i in sources}) > 100
    bad = [(f, i) for f, i in sources if split.get(i) != "train" or i in held]
    assert bad == []


def test_gap_items_are_train_benchmark_items_not_held_out(splits):
    _, _, held_items = splits
    train_items = {r["id"]: r for r in _read(BENCH / "items.train.jsonl")}
    for it in _bank("gaps.json")["items"]:
        item_id = it["id"].removeprefix("gap:")
        assert item_id not in held_items
        assert train_items[item_id]["split"] == "train"
        assert it["options"][it["answer"]]["iso"] == train_items[item_id]["target"].strip()


def test_every_bank_says_train_and_credits_dharma():
    for name in ("letters.json", "words.json", "gaps.json", "formulas.json", "try.json", "summary.json",
                 "worked-example.json"):
        meta = _bank(name)["meta"]
        assert meta["split"] == "train"
        assert "DHARMA" in meta["credit"] and "CC BY-SA 4.0" in meta["credit"]


def test_items_are_well_formed():
    total = 0
    for name in ("letters.json", "words.json", "gaps.json", "formulas.json"):
        items = _bank(name)["items"]
        total += len(items)
        assert len({i["id"] for i in items}) == len(items)
        for it in items:
            assert len(it["options"]) == 4 and 0 <= it["answer"] < 4
            assert len({json.dumps(o, ensure_ascii=False, sort_keys=True) for o in it["options"]}) == 4
            assert it["level"] in (1, 2, 3) and it["why_en"] and it["why_ta"]
        for lv in (1, 2, 3):
            assert sum(1 for i in items if i["level"] == lv) >= 10, (name, lv)
    assert total >= 1000


def test_committed_banks_match_the_script():
    pytest.importorskip("aksharamukha")
    spec = importlib.util.spec_from_file_location("build_practice", ROOT / "scripts" / "build_practice.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    assert mod.main(["--check"]) == 0
