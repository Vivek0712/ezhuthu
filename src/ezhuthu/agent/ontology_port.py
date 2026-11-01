"""Ontology interface used by the agent: the ontology MCP server (default), the direct
``ezhuthu.ontology.lookup`` API (flagged offline fallback), or a stub for fixtures.

The Ontology team's API is ``ezhuthu.ontology.lookup`` with ``find_entities(text)``, ``valid_letters(stage)``,
``formulas_for(ruler)``, ``entity(id)`` and ``hints_for_gap(left, right)``; ``ezhuthu.ontology.mcp_server``
serves the same functions as MCP tools. ``get_ontology()`` picks the backend (see its docstring); when the
ontology package is missing it serves ``ontology/lookups/*.json`` or ``fixtures/ontology_stub.json``
(records in contracts/ontology-lookup.schema.json format).
"""

from __future__ import annotations

import importlib
import json
import logging
import os
import threading
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

from .config import FIXTURES_DIR, repo_root
from .text import normalize_iso

log = logging.getLogger(__name__)

# Letters absent from early Tamil-Brahmi / Vatteluttu Tamil: Grantha consonants used for Sanskrit.
GRANTHA_ONLY = ("ś", "ṣ", "s", "h", "j", "kṣ")



@dataclass(frozen=True)
class Hint:
    id: str
    kind: str
    label: str
    label_ta: str | None = None
    fill: str | None = None  # the real API's proposed gap text for this entity, when it has one

    def to_api(self) -> dict[str, str]:
        kind = _API_KIND.get(self.kind, self.kind)
        return {"id": self.id, "kind": kind, "label": self.label}


# Ontology kinds (ontology-lookup schema) -> the smaller set the restore API names.
_API_KIND = {"grant_type": "grant", "temple": "place", "admin_unit": "place", "assembly": "place",
             "dynasty": "ruler", "coin": "measure", "tax": "measure"}


class OntologyPort(Protocol):
    name: str

    def hints_for_gap(self, left: str, right: str) -> list[Hint]: ...

    def find_entities(self, text: str) -> list[Hint]: ...

    def valid_letters(self, stage: str) -> set[str] | None: ...

    def entity(self, entity_id: str) -> dict[str, Any] | None: ...


class StubOntology:
    """Substring matching over lookup records (labels and variants)."""

    name = "stub"

    def __init__(self, records: list[dict[str, Any]]):
        self.records = records
        self._by_id = {r["id"]: r for r in records}
        self._surface: list[tuple[str, dict[str, Any]]] = []
        for r in records:
            for s in [r["label_iso"], *r.get("variants", [])]:
                s = normalize_iso(s)
                if len(s) >= 4:
                    self._surface.append((s, r))
        self._surface.sort(key=lambda x: len(x[0]), reverse=True)

    @classmethod
    def from_dir(cls, path: Path) -> StubOntology:
        recs: list[dict[str, Any]] = []
        for f in sorted(path.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, list):
                recs.extend(d for d in data if isinstance(d, dict) and "id" in d and "label_iso" in d)
        return cls(recs)

    @staticmethod
    def _hint(r: dict[str, Any]) -> Hint:
        return Hint(r["id"], r["kind"], r["label_iso"], r.get("label_ta"))

    def find_entities(self, text: str) -> list[Hint]:
        t = normalize_iso(text)
        seen: dict[str, Hint] = {}
        for s, r in self._surface:
            if s in t and r["id"] not in seen:
                seen[r["id"]] = self._hint(r)
        return list(seen.values())

    def hints_for_gap(self, left: str, right: str) -> list[Hint]:
        """Entities whose surface form overlaps the gap: it ends in the left context's tail or starts
        in the right context's head, or is a formula the context begins."""
        lt, rt = normalize_iso(left)[-40:], normalize_iso(right)[:40]
        out: dict[str, Hint] = {}
        for s, r in self._surface:
            for k in range(min(len(s) - 1, len(lt)), 2, -1):
                if lt.endswith(s[:k]):  # left context starts this entity; the gap may continue it
                    out.setdefault(r["id"], self._hint(r))
                    break
            for k in range(min(len(s) - 1, len(rt)), 2, -1):
                if rt.startswith(s[-k:]):
                    out.setdefault(r["id"], self._hint(r))
                    break
        return list(out.values())

    def valid_letters(self, stage: str) -> set[str] | None:
        return None  # the real API derives these with Aksharamukha (issue #2, item 3)

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        return self._by_id.get(entity_id)


class ModuleOntology:
    """Adapter over ``ezhuthu.ontology.lookup`` (issue #2)."""

    name = "ezhuthu.ontology.lookup"

    def __init__(self, module: Any):
        self.m = module

    @staticmethod
    def _to_hint(x: Any) -> Hint:
        if isinstance(x, Hint):
            return x
        d = x if isinstance(x, dict) else vars(x)
        return Hint(d["id"], d.get("kind", ""), d.get("label_iso") or d.get("label", ""), d.get("label_ta"),
                    d.get("fill") or None)

    def hints_for_gap(self, left: str, right: str) -> list[Hint]:
        return [self._to_hint(x) for x in self.m.hints_for_gap(left, right)]

    def find_entities(self, text: str) -> list[Hint]:
        return [self._to_hint(x) for x in self.m.find_entities(text)]

    def valid_letters(self, stage: str) -> set[str] | None:
        v = self.m.valid_letters(stage)
        if v is None:
            return None
        # the real API returns letter records ({"iso": ..., ...}); older shapes return plain strings
        return {x.get("iso") or x.get("letter") or x.get("id") if isinstance(x, dict) else x for x in v} - {None}

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        e = self.m.entity(entity_id)
        return e if e is None or isinstance(e, dict) else vars(e)


ONTOLOGY_MODE_ENV = "EZHUTHU_ONTOLOGY"  # mcp (default) | direct | stub
ONTOLOGY_MODES = ("mcp", "direct", "stub")


def _fixture_stub() -> StubOntology:
    return StubOntology(json.loads((FIXTURES_DIR / "ontology_stub.json").read_text(encoding="utf-8")))


_ONTOLOGY_LOCK = threading.Lock()


def get_ontology() -> OntologyPort:
    """The agent's ontology, built once per process (``get_ontology.cache_clear()`` resets it). The first build
    is under a lock: two FastAPI threadpool workers asking at once would otherwise each start an MCP server
    and leak one."""
    with _ONTOLOGY_LOCK:
        return _build_ontology()


@lru_cache(maxsize=1)
def _build_ontology() -> OntologyPort:
    """The agent's ontology. Default: the ontology MCP server over stdio via a Strands MCPClient
    (``ezhuthu.agent.ontology_mcp``). ``EZHUTHU_ONTOLOGY=direct`` uses the in-process lookup API instead
    (offline fallback, flagged in ``name``); so does a failed MCP start, flagged ``fallback:direct``.
    ``EZHUTHU_ONTOLOGY=stub`` (or ``EZHUTHU_FIXTURES=1`` with no mode set) uses the fixture stub."""
    mode = os.environ.get(ONTOLOGY_MODE_ENV, "").strip().lower()
    if mode and mode not in ONTOLOGY_MODES:
        raise ValueError(f"{ONTOLOGY_MODE_ENV}={mode!r}; expected one of {ONTOLOGY_MODES}")
    # The synthetic fixture corpus names synthetic entities (fixtures/ontology_stub.json); pair it with
    # that stub so fixture runs stay self-consistent. Real benchmark data uses the real ontology.
    if mode == "stub" or (not mode and os.environ.get("EZHUTHU_FIXTURES") == "1"):
        return _fixture_stub()
    flag = "direct:ezhuthu.ontology.lookup"
    if mode in ("", "mcp"):
        try:
            from .ontology_mcp import McpOntology

            return McpOntology()
        except Exception as exc:  # noqa: BLE001 - the direct API is the flagged offline fallback
            log.warning("ontology MCP server unavailable (%s); falling back to the direct lookup API", exc)
            flag = "fallback:direct (mcp unavailable)"
    try:
        mod = importlib.import_module("ezhuthu.ontology.lookup")
        if all(hasattr(mod, f) for f in ("hints_for_gap", "find_entities", "valid_letters", "entity")):
            onto = ModuleOntology(mod)
            onto.name = flag
            return onto
    except Exception as exc:  # noqa: BLE001 - any import failure means the ontology package is missing
        log.info("ontology API unavailable (%s); using stub", exc)
    root = repo_root()
    env_dir = os.environ.get("EZHUTHU_ONTOLOGY_DIR")  # a lookups/ dir in the contract schema
    lookups = Path(env_dir) if env_dir else (root / "ontology" / "lookups" if root else None)
    if lookups and lookups.is_dir():
        stub = StubOntology.from_dir(lookups)
        if stub.records:
            stub.name = "lookups-json"
            return stub
    return _fixture_stub()


get_ontology.cache_clear = _build_ontology.cache_clear  # type: ignore[attr-defined]


def letters_ok_for_dynasty(text: str, dynasty: str | None) -> bool:
    """Early (pre-Pallava) Tamil-Brahmi and Vatteluttu Tamil do not write Grantha-only consonants."""
    if not dynasty or dynasty.lower() not in {"tamil-brahmi", "early tamil", "sangam"}:
        return True
    t = normalize_iso(text)
    return not any(g in t for g in GRANTHA_ONLY)
