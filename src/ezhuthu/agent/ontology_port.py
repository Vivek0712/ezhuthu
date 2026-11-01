"""Ontology interface used by the agent, with a stub until issue #2 lands.

The Ontology team's API (issue #2) is ``ezhuthu.ontology.lookup`` with ``find_entities(text)``,
``valid_letters(stage)``, ``formulas_for(ruler)``, ``entity(id)`` and ``hints_for_gap(left, right)``.
``get_ontology()`` uses it when importable; otherwise it serves ``fixtures/ontology_stub.json``
(records in contracts/ontology-lookup.schema.json format).
"""

from __future__ import annotations

import importlib
import json
import logging
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
        return Hint(d["id"], d.get("kind", ""), d.get("label_iso") or d.get("label", ""), d.get("label_ta"))

    def hints_for_gap(self, left: str, right: str) -> list[Hint]:
        return [self._to_hint(x) for x in self.m.hints_for_gap(left, right)]

    def find_entities(self, text: str) -> list[Hint]:
        return [self._to_hint(x) for x in self.m.find_entities(text)]

    def valid_letters(self, stage: str) -> set[str] | None:
        v = self.m.valid_letters(stage)
        return set(v) if v is not None else None

    def entity(self, entity_id: str) -> dict[str, Any] | None:
        e = self.m.entity(entity_id)
        return e if e is None or isinstance(e, dict) else vars(e)


@lru_cache(maxsize=1)
def get_ontology() -> OntologyPort:
    try:
        mod = importlib.import_module("ezhuthu.ontology.lookup")
        if all(hasattr(mod, f) for f in ("hints_for_gap", "find_entities", "valid_letters", "entity")):
            return ModuleOntology(mod)
    except Exception as exc:  # noqa: BLE001 - any import failure means "not merged yet"
        log.info("ontology API unavailable (%s); using stub", exc)
    root = repo_root()
    if root and (root / "ontology" / "lookups").is_dir():
        onto = StubOntology.from_dir(root / "ontology" / "lookups")
        if onto.records:
            onto.name = "lookups-json"
            return onto
    return StubOntology(json.loads((FIXTURES_DIR / "ontology_stub.json").read_text(encoding="utf-8")))


def letters_ok_for_dynasty(text: str, dynasty: str | None) -> bool:
    """Early (pre-Pallava) Tamil-Brahmi and Vatteluttu Tamil do not write Grantha-only consonants."""
    if not dynasty or dynasty.lower() not in {"tamil-brahmi", "early tamil", "sangam"}:
        return True
    t = normalize_iso(text)
    return not any(g in t for g in GRANTHA_ONLY)
