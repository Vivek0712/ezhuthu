"""Load benchmark artefacts produced by the Data team (issue #1), or fixtures until they land.

Expected files (issue #1):
- ``benchmark/items.{train,val,test}.jsonl``: contracts/benchmark-item.schema.json records
- ``benchmark/corpus_lines.jsonl``: TRAIN lines for retrieval
  (``inscription_id``, ``line_n``, ``text``; optional ``collection``, ``dynasty``, ``source_url``)
- ``benchmark/inscriptions.jsonl``: metadata for the tutor (Data PR #6 shape: ``id``, ``title``, ``collection``,
  ``dynasty``, ``ruler``, ``regnal_year``, ``approx_date``, ``source_url``, ``text_iso`` with one line per row and
  a leading ``-`` marking a line that continues the previous word; older fixtures use ``date_text``/``text``)

The retrieval corpus must hold no val/test inscription: :func:`load_corpus_lines` refuses to load when it does.

``EZHUTHU_BENCHMARK_DIR`` overrides the directory. ``EZHUTHU_FIXTURES=1`` forces fixtures.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import FIXTURES_DIR, repo_root
from .text import normalize_iso


@dataclass(frozen=True)
class CorpusLine:
    inscription_id: str
    line_n: str
    text: str
    collection: str | None = None
    dynasty: str | None = None
    source_url: str | None = None


@dataclass(frozen=True)
class BenchmarkItem:
    id: str
    inscription_id: str
    collection: str
    split: str
    line_n: str
    left: str
    right: str
    target: str
    gap_chars: int
    hard: bool
    age_set: bool
    source_url: str
    dynasty: str | None = None
    kind: str = "supplied"
    extra: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> BenchmarkItem:
        known = {k for k in cls.__dataclass_fields__ if k != "extra"}
        return cls(**{k: d[k] for k in known if k in d}, extra={k: v for k, v in d.items() if k not in known})

    def to_dict(self) -> dict[str, Any]:
        d = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "extra"}
        d.update(self.extra)
        return d


@dataclass(frozen=True)
class DataSource:
    path: Path
    is_fixture: bool


def data_source() -> DataSource:
    if os.environ.get("EZHUTHU_FIXTURES") == "1":
        return DataSource(FIXTURES_DIR, True)
    env = os.environ.get("EZHUTHU_BENCHMARK_DIR")
    if env:
        return DataSource(Path(env), False)
    root = repo_root()
    if root and (root / "benchmark" / "corpus_lines.jsonl").is_file():
        return DataSource(root / "benchmark", False)
    return DataSource(FIXTURES_DIR, True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def parse_jsonl_text(text: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _line_text(d: dict[str, Any]) -> str:
    for key in ("text", "text_iso", "iso"):
        if d.get(key):
            return d[key]
    raise KeyError(f"corpus line has no text field: {sorted(d)}")


class CorpusLeak(RuntimeError):
    """The retrieval corpus contains a held-out (val/test) inscription."""


def _held_out_ids(directory: Path) -> set[str]:
    ids: set[str] = set()
    for split in ("val", "test"):
        p = directory / f"items.{split}.jsonl"
        if p.is_file():
            ids.update(d["inscription_id"] for d in read_jsonl(p))
    return ids


@lru_cache(maxsize=4)
def _load_corpus(path: str) -> tuple[CorpusLine, ...]:
    rows = read_jsonl(Path(path))
    # Fail closed: an explicit non-train split is dropped, and any line whose inscription has val/test items
    # (whatever its split field says, or when it has none) stops the load.
    held_out = _held_out_ids(Path(path).parent)
    leaked = sorted({r["inscription_id"] for r in rows if r.get("split", "train") == "train"} & held_out)
    if leaked:
        raise CorpusLeak(f"{len(leaked)} val/test inscription(s) in {path}, e.g. {leaked[:3]}")
    return tuple(
        CorpusLine(
            inscription_id=r["inscription_id"], line_n=str(r.get("line_n", "")), text=normalize_iso(_line_text(r)),
            collection=r.get("collection"), dynasty=r.get("dynasty"), source_url=r.get("source_url") or r.get("url"),
        )
        for r in rows
        if r.get("split", "train") == "train"
    )


def load_corpus_lines(src: DataSource | None = None) -> tuple[CorpusLine, ...]:
    src = src or data_source()
    return _load_corpus(str(src.path / "corpus_lines.jsonl"))


def benchmark_files(src: DataSource, split: str) -> list[Path]:
    p = src.path / f"items.{split}.jsonl"
    return [p] if p.is_file() else []


def load_items(split: str = "test", *, subset: str = "full", limit: int | None = None,
               src: DataSource | None = None) -> list[BenchmarkItem]:
    """``subset``: full | hard | age. Blank (no-target) items are skipped."""
    src = src or data_source()
    files = benchmark_files(src, split)
    if not files:
        raise FileNotFoundError(f"no benchmark items for split {split!r} in {src.path}")
    items = [BenchmarkItem.from_dict(d) for f in files for d in read_jsonl(f)]
    items = [it for it in items if it.kind != "blank" and it.target]
    if subset == "hard":
        items = [it for it in items if it.hard]
    elif subset == "age":
        items = [it for it in items if it.age_set]
    elif subset != "full":
        raise ValueError(f"unknown subset {subset!r}")
    return items[:limit] if limit else items


def parse_benchmark_name(name: str) -> tuple[str, str]:
    """``test`` -> (test, full); ``test-hard`` -> (test, hard); ``val-age`` -> (val, age)."""
    split, _, subset = name.partition("-")
    return split, subset or "full"


@lru_cache(maxsize=4)
def _load_inscriptions(path: str) -> dict[str, dict[str, Any]]:
    p = Path(path)
    return {r["id"]: r for r in read_jsonl(p)} if p.is_file() else {}


def load_inscriptions(src: DataSource | None = None) -> dict[str, dict[str, Any]]:
    src = src or data_source()
    return _load_inscriptions(str(src.path / "inscriptions.jsonl"))


def inscription_text(inscription_id: str, src: DataSource | None = None) -> str | None:
    """Full ISO text of an inscription: metadata ``text_iso`` (Data's shape) or ``text``/``lines``, else train
    corpus lines, else the test items reassembled (left + target + right of each line)."""
    src = src or data_source()
    meta = load_inscriptions(src).get(inscription_id, {})
    if meta.get("text_iso"):
        return "\n".join(normalize_iso(strip_continuation(ln)) for ln in meta["text_iso"].split("\n"))
    if meta.get("text"):
        return normalize_iso(meta["text"])
    if meta.get("lines"):
        return "\n".join(normalize_iso(x if isinstance(x, str) else x.get("text", "")) for x in meta["lines"])
    lines = [ln for ln in load_corpus_lines(src) if ln.inscription_id == inscription_id]
    if lines:
        return "\n".join(ln.text for ln in sorted(lines, key=lambda x: _line_key(x.line_n)))
    for split in ("test", "val", "train"):
        try:
            items = [it for it in load_items(split, src=src) if it.inscription_id == inscription_id]
        except FileNotFoundError:
            continue
        if items:
            by_line: dict[str, BenchmarkItem] = {}
            for it in items:
                by_line.setdefault(it.line_n, it)
            return "\n".join(
                normalize_iso(it.left + it.target + it.right)
                for it in sorted(by_line.values(), key=lambda x: _line_key(x.line_n))
            )
    return None


def strip_continuation(line: str) -> str:
    """Data's ``text_iso`` prefixes a line that continues the previous word with one ``-``."""
    return line.removeprefix("-")


def inscription_meta(meta: dict[str, Any]) -> dict[str, Any]:
    """Tutor-facing metadata from either shape (Data PR #6 ``approx_date``/``ruler``; fixtures ``date_text``)."""
    return {"id": meta.get("id"), "title": meta.get("title"), "dynasty": meta.get("dynasty"),
            "ruler": meta.get("ruler"), "regnal_year": meta.get("regnal_year"),
            "approx_date": meta.get("approx_date") or meta.get("date_text"),
            "source_url": meta.get("source_url"), "dharmalekha_url": meta.get("dharmalekha_url"),
            "licence": meta.get("licence")}


def _line_key(n: str) -> tuple[int, str]:
    digits = "".join(ch for ch in n if ch.isdigit())
    return (int(digits) if digits else 0, n)
