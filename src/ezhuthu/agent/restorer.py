"""Restoration engine: retrieve parallels, propose fills, check constraints, rank and decide, route.

Each step is also exposed as a Strands tool (``ezhuthu.agent.tools``); this module runs them as a
fixed pipeline so the API is deterministic given the same model responses.
"""

from __future__ import annotations

import logging
import statistics
import time
import uuid
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from .config import ModelsConfig, load_models_config
from .data import CorpusLine, load_corpus_lines
from .decider import Decider, DeciderUnavailable, NoDecider
from .llm import LiveCallsDisabled, LLMClient
from .ngram import CharNgram
from .ontology_port import Hint, OntologyPort, letters_ok_for_dynasty
from .prompts import RESTORER_SYSTEM, parse_candidates, propose_prompt
from .retrieval import Parallel, ParallelIndex
from .text import (
    DEFAULT_UNKNOWN_GAP,
    fill_gaps,
    find_gaps,
    iso_to_tamil,
    non_iso_chars,
    normalize_iso,
    to_iso,
)

log = logging.getLogger(__name__)

ROUTERS = ("routed", "sonnet", "opus", "none")
NONE_OPTION = "none"
DECIDER_INSTRUCTIONS = (
    "A Tamil stone inscription (ISO-15919 transliteration) has a damaged gap. Which candidate best restores "
    "the gap, i.e. matches what an expert epigraphist would supply? Use the context, the gap length and the "
    "parallel passages. Choose 'none' if no candidate fits."
)


@dataclass
class Candidate:
    text: str
    sources: set[str] = field(default_factory=set)  # parallel | ontology | ngram | sonnet | opus
    llm_confidence: float | None = None
    retrieval_score: float = 0.0
    parallels: list[Parallel] = field(default_factory=list)
    hints: list[Hint] = field(default_factory=list)
    length_ok: bool = True
    letters_ok: bool = True
    confidence: float = 0.0
    confidence_source: str = ""
    decider_source: str = ""  # hosted | local | fallback

    @property
    def model(self) -> str:
        for m in ("opus", "sonnet"):
            if m in self.sources:
                return m
        return "retrieval"

    def to_api(self, decider_model: str) -> dict[str, Any]:
        return {
            "text": self.text, "text_tamil": iso_to_tamil(self.text), "confidence": round(self.confidence, 4),
            "model": self.model, "decider_model": decider_model,
            "parallels": [p.to_api() for p in self.parallels],
            "ontology_hints": [h.to_api() for h in self.hints],
            # additive fields (not in the contract's example, safe to ignore):
            "sources": sorted(self.sources), "confidence_source": self.confidence_source,
            "decider_source": self.decider_source or "fallback",
            "constraints": {"length_ok": self.length_ok, "letters_ok": self.letters_ok},
        }


@dataclass
class GapResult:
    index: int
    gap_chars: int
    decision: str  # fill | abstain
    chosen: int | None
    candidates: list[Candidate]
    decider_model: str
    models_used: list[str]
    escalated: bool = False
    parallels: list[Parallel] = field(default_factory=list)

    @property
    def best(self) -> Candidate | None:
        return self.candidates[self.chosen] if self.chosen is not None and self.candidates else None

    def to_api(self) -> dict[str, Any]:
        return {
            "index": self.index, "gap_chars": self.gap_chars, "decision": self.decision, "chosen": self.chosen,
            "candidates": [c.to_api(self.decider_model) for c in self.candidates], "escalated": self.escalated,
        }


def length_tolerance(gap_chars: int) -> int:
    return max(2, round(gap_chars * 0.34))


class Restorer:
    def __init__(self, *, llm: LLMClient | None = None, decider: Decider | None = None,
                 ontology: OntologyPort | None = None, corpus: list[CorpusLine] | None = None,
                 config: ModelsConfig | None = None, use_ontology: bool = True):
        self.llm = llm
        self.decider = decider or NoDecider()
        self._ontology = ontology
        self._corpus = corpus
        self.config = config or (llm.config if llm else load_models_config())
        self.use_ontology = use_ontology

    # ---- lazily built resources -------------------------------------------------
    @cached_property
    def corpus(self) -> list[CorpusLine]:
        return list(self._corpus if self._corpus is not None else load_corpus_lines())

    @cached_property
    def index(self) -> ParallelIndex:
        return ParallelIndex(self.corpus)

    @cached_property
    def ngram(self) -> CharNgram:
        return CharNgram().fit(ln.text for ln in self.corpus)

    @cached_property
    def ontology(self) -> OntologyPort:
        if self._ontology is not None:
            return self._ontology
        from .ontology_port import get_ontology

        return get_ontology()

    # ---- tools -------------------------------------------------------------------
    def retrieve_parallels(self, left: str, right: str, gap_chars: int | None, *, k: int = 5,
                           exclude_inscription: str | None = None) -> list[Parallel]:
        return self.index.search(left, right, gap_chars=gap_chars, k=k, exclude_inscription=exclude_inscription)

    def ontology_candidates(self, left: str, right: str, gap_chars: int) -> list[tuple[str, Hint]]:
        """Completions of an entity whose surface form starts in the left context and runs into the gap."""
        out: list[tuple[str, Hint]] = []
        lt = normalize_iso(left)[-40:] + (" " if left.endswith(" ") else "")
        for h in self.ontology.hints_for_gap(left, right):
            if h.fill:  # the real API computes the gap text itself (anchored on both contexts)
                rest = normalize_iso(h.fill).strip()
                if rest and abs(len(rest) - gap_chars) <= length_tolerance(gap_chars):
                    out.append((rest, h))
                continue
            rec = self.ontology.entity(h.id) or {}
            for surface in [rec.get("label_iso", h.label), *rec.get("variants", [])]:
                s = normalize_iso(surface)
                for k in range(min(len(s) - 1, len(lt)), 2, -1):
                    if lt.endswith(s[:k]):
                        rest = s[k:].strip()
                        if rest and abs(len(rest) - gap_chars) <= length_tolerance(gap_chars):
                            out.append((rest, h))
                        break
        return out

    def propose_fills(self, role: str, left: str, right: str, gap_chars: int | None,
                      parallels: list[Parallel], hints: list[Hint], k: int) -> list[tuple[str, float | None]]:
        if self.llm is None:
            return []
        prompt = propose_prompt(
            left, right, gap_chars,
            [{"inscription_id": p.inscription_id, "line_n": p.line_n, "snippet": p.snippet, "fill": p.fill}
             for p in parallels],
            [h.to_api() for h in hints], k,
        )
        r = self.llm.complete(role, RESTORER_SYSTEM, prompt, max_tokens=800)
        return [(normalize_iso(t), c) for t, c in parse_candidates(r.text) if normalize_iso(t)]

    def check_constraints(self, cands: list[Candidate], gap_chars: int, *, explicit_length: bool,
                          dynasty: str | None = None) -> list[Candidate]:
        tol = length_tolerance(gap_chars)
        kept = []
        for c in cands:
            c.length_ok = (not explicit_length) or abs(len(c.text) - gap_chars) <= tol
            c.letters_ok = not non_iso_chars(c.text) and letters_ok_for_dynasty(c.text, dynasty)
            if c.letters_ok:
                kept.append(c)
        return kept

    def rank_and_decide(self, cands: list[Candidate], *, left: str, right: str, gap_chars: int,
                        parallels: list[Parallel], hints: list[Hint]) -> tuple[str, list[Candidate]]:
        """Set ``confidence`` on each candidate and sort. Returns the decider model name or fallback tag."""
        if not cands:
            return "none", cands
        top = cands[:23]  # 24 decider slots, one reserved for "none"
        # Each option carries its evidence; in a probe this beat bare strings (see PR notes).
        lt, rt = left.split("\n")[-1][-60:], right.split("\n")[0][:60]
        options: dict[str, Any] = {
            f"c{i}": {"fill": c.text, "restored_line": f"{lt}{c.text}{rt}",
                      "parallel_lines_supporting": len(c.parallels), "length_matches_gap": c.length_ok}
            for i, c in enumerate(top)
        }
        options[NONE_OPTION] = "none of these candidates fits the gap"
        state = {
            "text_before_gap": left[-120:], "text_after_gap": right[:120], "gap_length_chars": gap_chars,
            "parallel_passages": [f"{p.inscription_id}: {p.snippet}" for p in parallels[:3]],
            "known_entities_nearby": [h.label for h in hints[:5]],
        }
        try:
            res = self.decider.choice(state, DECIDER_INSTRUCTIONS, options, name="restoration")
            for i, c in enumerate(top):
                c.confidence = res.probabilities.get(f"c{i}", 0.0)
                c.confidence_source, c.decider_source = "decider", res.source
            for c in cands[23:]:
                c.confidence, c.confidence_source, c.decider_source = 0.0, "decider-overflow", res.source
            ranked = sorted(cands, key=lambda c: c.confidence, reverse=True)
            return res.model, ranked
        except DeciderUnavailable:
            pass
        # Fallback: LLM self-reported confidence; retrieval-only candidates use agreement among parallels.
        n_par = max(1, len([p for p in parallels if p.fill]))
        for c in cands:
            c.decider_source = "fallback"
            if c.llm_confidence is not None:
                c.confidence, c.confidence_source = c.llm_confidence, "llm-self-report"
            else:
                agree = len(c.parallels) / n_par
                c.confidence = round(min(1.0, c.retrieval_score / 100.0) * agree * (1.0 if c.length_ok else 0.5), 4)
                c.confidence_source = "retrieval-heuristic"
        tag = "fallback:llm-self-report" if any(c.llm_confidence is not None for c in cands) \
            else "fallback:retrieval-heuristic"
        return tag, sorted(cands, key=lambda c: c.confidence, reverse=True)

    # ---- pipeline ----------------------------------------------------------------
    def _estimate_len(self, gap_chars: int | None, parallels: list[Parallel]) -> int:
        if gap_chars:
            return gap_chars
        fills = [len(p.fill) for p in parallels if p.fill]
        return int(statistics.median(fills)) if fills else DEFAULT_UNKNOWN_GAP

    def restore_gap(self, left: str, right: str, gap_chars: int | None, *, index: int = 0, router: str = "routed",
                    allow_escalation: bool = True, max_candidates: int = 5, exclude_inscription: str | None = None,
                    dynasty: str | None = None, include_llm: bool = True) -> GapResult:
        if router not in ROUTERS:
            raise ValueError(f"router must be one of {ROUTERS}")
        rt = self.config.routing
        parallels = self.retrieve_parallels(left, right, gap_chars, k=5, exclude_inscription=exclude_inscription)
        length = self._estimate_len(gap_chars, parallels)
        hints = self.ontology.hints_for_gap(left, right) if self.use_ontology else []
        pool: dict[str, Candidate] = {}

        def add(text: str, source: str, *, conf: float | None = None, par: Parallel | None = None,
                hint: Hint | None = None) -> None:
            t = normalize_iso(text)
            if not t:
                return
            c = pool.setdefault(t, Candidate(t))
            c.sources.add(source)
            if conf is not None:
                c.llm_confidence = conf if c.llm_confidence is None else max(c.llm_confidence, conf)
            if par is not None and par not in c.parallels:
                c.parallels.append(par)
                c.retrieval_score = max(c.retrieval_score, par.score)
            if hint is not None and hint not in c.hints:
                c.hints.append(hint)

        for p in parallels:
            if p.fill:
                add(p.fill, "parallel", par=p)
        if self.use_ontology:
            for text, h in self.ontology_candidates(left, right, length):
                add(text, "ontology", hint=h)
        for text, _lp in self.ngram.fill(left, right, length, k=3):
            add(text, "ngram")

        good_parallel = any(p.fill and p.score >= 50 for p in parallels)
        models_used: list[str] = []
        escalated = False
        llm_on = include_llm and self.llm is not None and router != "none"
        if router == "routed":
            pre_escalate = allow_escalation and (
                length > rt.escalate_if_gap_chars_over or (rt.escalate_if_no_parallel and not good_parallel))
            first_role = "escalate" if pre_escalate else "default"
            escalated = pre_escalate
        else:
            first_role = {"sonnet": "default", "opus": "escalate"}.get(router, "default")
        k_llm = max(5, max_candidates)

        def call_llm(role: str) -> None:
            try:
                props = self.propose_fills(role, left, right, gap_chars, parallels, hints, k_llm)
            except LiveCallsDisabled:
                log.warning("LLM disabled (EZHUTHU_LIVE!=1); retrieval candidates only")
                return
            mid = self.config.model_id(role)
            models_used.append(mid)
            short = "opus" if role == "escalate" else "sonnet"
            for t, c in props:
                add(t, short, conf=c)

        if llm_on:
            call_llm(first_role)

        def finalize() -> tuple[str, list[Candidate]]:
            cands = self.check_constraints(list(pool.values()), length, explicit_length=gap_chars is not None,
                                           dynasty=dynasty)
            for c in cands:  # attach gap-level hints to candidates that contain or continue them
                for h in hints:
                    if h not in c.hints:
                        c.hints.append(h)
            # stable pre-order: LLM-ranked first, then parallels by score, then the rest
            cands.sort(key=lambda c: (-(c.llm_confidence or 0), -c.retrieval_score, c.text))
            return self.rank_and_decide(cands, left=left, right=right, gap_chars=length, parallels=parallels,
                                        hints=hints)

        decider_model, ranked = finalize()
        best = ranked[0].confidence if ranked else 0.0
        if (llm_on and router == "routed" and allow_escalation and first_role == "default"
                and best < rt.escalate_if_confidence_below):
            call_llm("escalate")
            escalated = True
            decider_model, ranked = finalize()
            best = ranked[0].confidence if ranked else 0.0

        if decider_model not in ("none",) and not decider_model.startswith("fallback:"):
            models_used.append(decider_model)
        decision = "fill" if ranked and best >= rt.abstain_if_confidence_below else "abstain"
        return GapResult(index=index, gap_chars=length, decision=decision, chosen=0 if ranked else None,
                         candidates=ranked[:max(1, max_candidates)], decider_model=decider_model,
                         models_used=models_used, escalated=escalated, parallels=parallels)

    def restore(self, text: str, *, script: str = "iso15919", max_candidates: int = 5,
                allow_escalation: bool = True, router: str = "routed") -> dict[str, Any]:
        """``POST /api/restore`` (contracts/restore-api.md)."""
        t0 = time.perf_counter()
        iso = to_iso(text, script)
        gaps = find_gaps(iso)
        results: list[GapResult] = []
        fills: list[str | None] = []
        for g in gaps:
            # Earlier gaps use their chosen fill (if any) as context for later ones.
            left = fill_gaps(iso[: g.start], fills)
            res = self.restore_gap(left, g.right, g.gap_chars, index=g.index, router=router,
                                   allow_escalation=allow_escalation, max_candidates=max_candidates)
            results.append(res)
            fills.append(res.best.text if res.decision == "fill" and res.best else None)
        restored = fill_gaps(iso, fills)
        models: list[str] = []
        for r in results:
            for m in r.models_used:
                if m not in models:
                    models.append(m)
        return {
            "restored_text": restored, "restored_text_tamil": iso_to_tamil(restored),
            "gaps": [r.to_api() for r in results], "models_used": models,
            "trace_id": uuid.uuid4().hex, "latency_ms": round((time.perf_counter() - t0) * 1000, 1),
        }
