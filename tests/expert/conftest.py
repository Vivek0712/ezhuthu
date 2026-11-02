"""A small synthetic benchmark and proposal set for the expert-kit tests (no network, no Bedrock)."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

WORDS = ["svasti", "śrī", "kō", "rāja", "kēcari", "panmarkku", "yāṇṭu", "tiru", "nāḷ", "oṉṟukku", "neyyum",
         "viḷakku", "iraṇṭu", "kaḻañcu", "poṉ", "taṉmam", "ūrōm", "vaitta", "tēvar", "nilam"]
FILLS = ["kō", "rāja", "tiru", "poṉ", "nāḷ", "ūrōm", "tēvar", "nilam", "vaitta", "neyyum"]


def _ctx(rng: random.Random, n: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n))


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


@pytest.fixture()
def bench(tmp_path: Path) -> Path:
    rng = random.Random(1)
    d = tmp_path / "benchmark"
    d.mkdir()
    blank, test = [], []
    for i in range(40):
        split = ["test", "val", "train"][i % 3]
        ins = f"DHARMA_INSFake{i // 2:05d}"
        blank.append({"id": f"{ins}:{i}:0", "inscription_id": ins, "collection": "tfa-fake-epigraphy",
                      "dynasty": None, "age_set": False, "split": split, "line_n": str(i),
                      "left": _ctx(rng, 5), "right": _ctx(rng, 5), "target": "", "gap_chars": 2 + i % 5,
                      "hard": False, "kind": "blank", "reason": "lost",
                      "source_url": f"https://example.org/{ins}.xml"})
    for i in range(60):
        ins = f"DHARMA_INSTest{i // 3:05d}"
        test.append({"id": f"{ins}:{i}:0", "inscription_id": ins, "collection": "tfa-fake-epigraphy",
                     "dynasty": "Cōḻa", "age_set": i % 4 == 0, "split": "test", "line_n": str(i),
                     "left": _ctx(rng, 5), "right": _ctx(rng, 5), "target": rng.choice(FILLS) + "-y-um",
                     "gap_chars": 3, "hard": i % 2 == 0, "kind": "supplied", "reason": "lost",
                     "source_url": f"https://example.org/{ins}.xml"})
    _write(d / "blank.jsonl", blank)
    _write(d / "items.test.jsonl", test)
    return d


def fake_proposals(sample: list[dict], *, n: int = 6, include_target_for: int = 2, seed: int = 0) -> list[dict]:
    """Ranked proposals per sampled item; for the first ``include_target_for`` masked items the edition's fill
    (in another spelling) is among them, as happens with retrieval."""
    rng = random.Random(seed)
    out, seen_masked = [], 0
    for rec in sample:
        props = [{"text": f"{w}a", "confidence": round(0.9 - 0.1 * j, 2), "sources": [rng.choice(
            ["sonnet", "parallel", "ngram"])]} for j, w in enumerate(rng.sample(FILLS, n))]
        if rec["role"] != "rating-blank" and rec.get("target"):
            seen_masked += 1
            if seen_masked <= include_target_for:
                props.insert(0, {"text": rec["target"].replace("-", "").upper(), "confidence": 0.95,
                                 "sources": ["parallel"]})
        out.append({"id": rec["id"], "role": rec["role"], "proposals": props})
    return out


@pytest.fixture()
def make_proposals():
    return fake_proposals
