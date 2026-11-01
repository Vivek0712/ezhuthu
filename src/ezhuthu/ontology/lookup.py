"""Runtime lookup API over the committed ontology artefacts (no network, no DHARMA checkout needed).

    from ezhuthu.ontology import lookup
    lookup.find_entities("svasti śrī kō-p-parakēcari-varmmaṟku yāṇṭu")
    lookup.valid_letters("chola-tamil")          # or a tutor level: "L2"
    lookup.formulas_for("ez:ruler/rajaraja-i")
    lookup.entity("ez:ruler/rajaraja-i")
    lookup.hints_for_gap("kō-p-para", "rkku yāṇṭu", gap_chars=8)

All text is ISO-15919 (contracts/restore-api.md). Results are plain dicts so they serialise
straight into API responses; each hint carries ``id``, ``kind`` and ``label`` as the restore
contract's ``ontology_hints`` expects.
"""

from __future__ import annotations

import functools
import json
import re
from collections import defaultdict
from pathlib import Path

from ezhuthu.ontology.matcher import MIN_KEY, KeyedText, VariantIndex
from ezhuthu.ontology.normalize import key

DEFAULT_DIR = Path(__file__).resolve().parents[3] / "ontology"
# Kinds worth proposing as gap fills (letters and script stages are not text content).
FILL_KINDS = {
    "ruler", "title", "formula", "dynasty", "place", "admin_unit", "temple", "deity",
    "grant_type", "assembly", "measure", "coin", "tax",
}  # fmt: skip
# After these (folded) stems a regnal year follows: ``<royal name>-kku yāṇṭu``.
_REGNAL_RIGHT = re.compile(r"^(?:[ṟr]k|k)?k?u?yāṇṭu")


class Ontology:
    def __init__(self, root: Path = DEFAULT_DIR) -> None:
        self.root = Path(root)
        self.entities: dict[str, dict] = {}
        for p in sorted((self.root / "lookups").glob("*.json")):
            for rec in json.loads(p.read_text(encoding="utf-8")):
                self.entities[rec["id"]] = rec
        self.letters = json.loads((self.root / "letters_by_era.json").read_text(encoding="utf-8"))
        self.index = VariantIndex()
        self._prefix: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)  # v[:k] -> (vkey,k,id,variant)
        self._suffix: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)  # v[j:] -> (vkey,j,id,variant)
        for eid, rec in self.entities.items():
            if rec["kind"] not in FILL_KINDS:
                continue
            forms = set(rec.get("variants") or [])
            if rec["kind"] not in ("admin_unit",) or not rec.get("is_type"):
                forms.add(rec["label_iso"])
            for v in forms:
                if "…" in v:
                    continue
                self.index.add(eid, v)
                vk = key(v)
                if len(vk) < MIN_KEY + 1:
                    continue
                for k in range(1, len(vk)):
                    self._prefix[vk[:k]].append((vk, k, eid, v))
                    self._suffix[vk[k:]].append((vk, k, eid, v))

    # -- basic lookups ----------------------------------------------------------------------
    def entity(self, eid: str) -> dict | None:
        return self.entities.get(eid)

    def by_kind(self, kind: str) -> list[dict]:
        return [r for r in self.entities.values() if r["kind"] == kind]

    def find_entities(self, text: str) -> list[dict]:
        """Entities mentioned in ISO-15919 ``text``, with char spans, in text order."""
        out = []
        for m in self.index.scan(text):
            rec = self.entities[m.entity_id]
            out.append({**_brief(rec), "start": m.start, "end": m.end, "surface": m.surface, "variant": m.variant})
        return out

    def valid_letters(self, stage: str) -> list[dict]:
        """Base letters valid in a script stage (``chola-tamil``) or tutor level (``L1``..``L5``)."""
        stages = self.letters["levels"].get(stage, [stage])
        out = []
        for st in stages:
            if st not in self.letters["stages"]:
                raise KeyError(f"unknown script stage or level: {stage!r}")
            for letter in self.letters["stages"][st]["letters"]:
                out.append({**letter, "stage": st, "id": f"ez:letter/{st}-{_letter_slug(letter['iso'])}"})
        return out

    def exceptions(self, stage: str) -> list[dict]:
        return list(self.letters["stages"][stage]["exceptions"])

    def formulas_for(self, ruler: str) -> list[dict]:
        """Formulas a ruler's inscriptions use: his own meykkīrtti/epithets first, then his dynasty's
        formulas, then formulas common to all (svasti śrī, regnal year, duration clause)."""
        rec = self.entities.get(ruler)
        if rec is None:
            raise KeyError(ruler)
        dyn = rec.get("dynasty") if rec["kind"] in ("ruler", "title") else rec["id"] if rec["kind"] == "dynasty" else None
        own, dynastic, common = [], [], []
        for f in self.by_kind("formula"):
            if f.get("ruler") == ruler:
                own.append(f)
            elif f.get("ruler") is None and dyn and f.get("dynasty") == dyn:
                dynastic.append(f)
            elif f.get("ruler") is None and f.get("dynasty") is None:
                common.append(f)

        def order(fs: list[dict]) -> list[dict]:
            return sorted(fs, key=lambda f: (-f.get("inscription_count", 0), f["id"]))

        return order(own) + order(dynastic) + order(common)

    # -- gap hints ----------------------------------------------------------------------------
    def hints_for_gap(self, left: str, right: str, gap_chars: int | None = None, limit: int = 10) -> list[dict]:
        """Ontology entities that could fill a gap between ``left`` and ``right``.

        Two kinds of evidence:
          * ``overlap``: a known variant starts in ``left`` (at a word boundary) and/or ends in
            ``right``; the part in between is proposed as ``fill`` (folded key form, see normalize).
            Other spellings of the same entity that also fit are listed in ``alt_fills``.
          * ``regnal_slot``: the gap sits right before ``-kku yāṇṭu`` (regnal-year formula), so it
            likely holds a royal name or title; the rulers and titles named in the context's
            dynasty are proposed. Without an anchor these carry no ``fill``.
        Hints are ranked by anchor length and fit to ``gap_chars`` (when given).
        """
        lk = KeyedText.of(left)
        L, R = lk.joined, key(right)
        regnal = bool(_REGNAL_RIGHT.search(R))
        left_boundary = not left or bool(re.search(r"[\s\-]$", left))
        cands: dict[str, dict] = {}  # best hint per entity

        def add(eid: str, variant: str, fill: str, a_left: int, a_right: int, vlen: int) -> None:
            if not fill:
                return
            fit = 1.0
            if gap_chars:
                tol = max(2, round(0.4 * gap_chars))
                diff = abs(len(fill) - gap_chars)
                if diff > tol:
                    return
                fit = 1.0 - diff / (tol + 1)
            score = (a_left + a_right) / vlen * 0.6 + fit * 0.4
            if regnal and self.entities[eid]["kind"] in ("ruler", "title"):
                score += 0.3  # a royal name is expected before "-kku yāṇṭu"
            score = round(score, 4)
            prev = cands.get(eid)
            if prev is None or prev["score"] < score:
                alts = ([prev["fill"], *prev["alt_fills"]] if prev else [])
                cands[eid] = {**_brief(self.entities[eid]), "fill": fill, "alt_fills": [a for a in alts if a != fill],
                              "variant": variant, "anchor_left": a_left, "anchor_right": a_right, "score": score,
                              "reason": "overlap"}
            elif fill != prev["fill"] and fill not in prev["alt_fills"]:
                prev["alt_fills"].append(fill)

        # variant begins inside `left` (k >= 1 chars, starting at a token boundary)
        for k in range(1, min(len(L), 40) + 1):
            suf = L[-k:]
            if (len(L) - k) not in lk.starts:
                continue
            for vk, kk, eid, variant in self._prefix.get(suf, ()):
                if kk != k:
                    continue
                rest = vk[k:]
                m = _overlap(rest, R)
                if k < 2 or m == 1 or k + m < 4:
                    continue
                add(eid, variant, rest[: len(rest) - m] if m else rest, k, m, len(vk))
        # variant begins exactly at the gap and ends inside `right`
        if left_boundary:
            for j in range(1, min(len(R), 40) + 1):
                pre = R[:j]
                for vk, jj, eid, variant in self._suffix.get(pre, ()):
                    if len(vk) - jj != j or j < 3:
                        continue
                    add(eid, variant, vk[:jj], 0, j, len(vk))
        hints = sorted(cands.values(), key=lambda h: (-h["score"], -h["anchor_left"] - h["anchor_right"], h["id"]))
        if regnal:
            have = {h["id"] for h in hints}
            context = self.find_entities(left + " " + right)
            dyns = {self.entities[c["id"]].get("dynasty") or (c["id"] if c["kind"] == "dynasty" else None)
                    for c in context} - {None}
            pool = [r for r in self.entities.values() if r["kind"] in ("ruler", "title") and r.get("dynasty")
                    and (not dyns or r.get("dynasty") in dyns) and r["id"] not in have]
            pool.sort(key=lambda r: (-r.get("inscription_count", 0), r["id"]))
            for r in pool[: max(0, limit - len(hints))]:
                hints.append({**_brief(r), "fill": None, "alt_fills": [], "variant": None, "anchor_left": 0, "anchor_right": 0,
                              "score": 0.1, "reason": "regnal_slot"})
        return hints[:limit]


def _overlap(rest: str, right: str) -> int:
    """Largest m < len(rest) such that rest ends with right[:m]."""
    for m in range(min(len(rest) - 1, len(right)), 0, -1):
        if rest.endswith(right[:m]):
            return m
    return 0


def _brief(rec: dict) -> dict:
    return {"id": rec["id"], "kind": rec["kind"], "label": rec["label_iso"], "label_ta": rec.get("label_ta")}


def _letter_slug(iso: str) -> str:
    from ezhuthu.ontology.letters import letter_slug

    return letter_slug(iso)


@functools.lru_cache(maxsize=4)
def load(root: str | None = None) -> Ontology:
    return Ontology(Path(root) if root else DEFAULT_DIR)


def find_entities(text: str) -> list[dict]:
    return load().find_entities(text)


def valid_letters(stage: str) -> list[dict]:
    return load().valid_letters(stage)


def formulas_for(ruler: str) -> list[dict]:
    return load().formulas_for(ruler)


def entity(eid: str) -> dict | None:
    return load().entity(eid)


def hints_for_gap(left: str, right: str, gap_chars: int | None = None, limit: int = 10) -> list[dict]:
    return load().hints_for_gap(left, right, gap_chars, limit)
