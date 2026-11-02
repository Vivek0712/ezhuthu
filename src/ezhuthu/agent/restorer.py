"""Restoration engine: retrieve parallels, propose fills, check constraints, rank and decide, route.

Each step is also exposed as a Strands tool (``ezhuthu.agent.tools``); this module runs them as a
fixed pipeline so the API is deterministic given the same model responses.
"""

from __future__ import annotations

import logging
import math
import os
import statistics
import time
import uuid
from dataclasses import dataclass, field
from functools import cached_property
from typing import Any

from .calibration import Calibration, CalibrationTable, variant_key
from .config import ModelsConfig, RestorerSettings, load_models_config
from .data import CorpusLine, load_corpus_lines
from .decider import Decider, DeciderUnavailable, NoDecider
from .llm import LiveCallsDisabled, LLMClient
from .ngram import CharNgram
from .ontology_port import Hint, OntologyPort, letters_ok_for_dynasty
from .prompts import RESTORER_SYSTEM, parse_candidates, propose_max_tokens, propose_prompt
from .retrieval import Parallel, ParallelIndex
from .text import (
    DEFAULT_UNKNOWN_GAP,
    akshara_len,
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
NOUL_INSTRUCTIONS = (
    "A Tamil stone inscription (ISO-15919 transliteration) has a damaged gap. Is the candidate fill exactly what "
    "an expert epigraphist would supply for the gap? Use the context, the gap length and the parallel passages."
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
    copy_floor: bool = False  # the copy baseline's fill: best length-ok parallel (never dropped from top-k)
    ngram_rank: int | None = None  # rank among the n-gram model's proposals (0 = best)
    prerank: float = 0.0  # cheap pre-rank score (LLM probability noisy-OR parallel support)
    raw_confidence: float | None = None  # decider/fallback confidence before calibration
    ngram_prob: float | None = None  # softmax share of the 5-gram beam (restorer.ngram_* settings only)

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
            "features": {"prerank": round(self.prerank, 4), "copy_baseline": self.copy_floor,
                         "llm_probability": self.llm_confidence, "parallel_support": len(self.parallels),
                         "best_parallel_match": round(self.retrieval_score / 100.0, 4),
                         "ngram_rank": self.ngram_rank,
                         "ngram_probability": None if self.ngram_prob is None else round(self.ngram_prob, 4),
                         "raw_confidence": None if self.raw_confidence is None else round(self.raw_confidence, 4)},
        }

    def option(self, lt: str, rt: str) -> dict[str, Any]:
        """The decider's view of this candidate: the fill in context plus its evidence scores."""
        out = {"fill": self.text, "restored_line": f"{lt}{self.text}{rt}",
               "parallel_lines_supporting": len(self.parallels),
               "best_parallel_match": round(self.retrieval_score / 100.0, 2),
               "llm_probability": None if self.llm_confidence is None else round(self.llm_confidence, 2),
               "copy_baseline": self.copy_floor, "ngram_proposal": self.ngram_rank is not None,
               "length_matches_gap": self.length_ok}
        if self.ngram_prob is not None:  # only with the restorer.ngram_* settings (unchanged request otherwise)
            out["ngram_probability"] = round(self.ngram_prob, 2)
        return out


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
    strategy: str = ""
    calibration: str | None = None  # variant key whose VAL calibration was applied, if any
    abstain_below: float = 0.5
    llm_truncated: int = 0  # LLM replies cut at max_tokens (after the parse of what arrived)
    llm_retries: int = 0  # stricter re-asks after a truncation
    # One record per LLM call made for this gap (eval cost/latency accounting; not part of the API):
    # {"model": sonnet|opus, "input_tokens", "output_tokens", "latency_ms" (of the original call, also when the
    # reply came from the cache), "cached"}. ``llm_wall_ms``: wall time spent waiting on those calls here.
    llm_calls: list[dict[str, Any]] = field(default_factory=list)
    llm_wall_ms: float = 0.0

    @property
    def best(self) -> Candidate | None:
        return self.candidates[self.chosen] if self.chosen is not None and self.candidates else None

    def to_api(self) -> dict[str, Any]:
        return {
            "index": self.index, "gap_chars": self.gap_chars, "decision": self.decision, "chosen": self.chosen,
            "candidates": [c.to_api(self.decider_model) for c in self.candidates], "escalated": self.escalated,
            # additive:
            "strategy": self.strategy, "calibration": self.calibration, "abstain_below": self.abstain_below,
        }


def length_tolerance(gap_chars: int) -> int:
    """Allowed difference, in Tamil letters, between a fill and the gap's ``gap_chars`` (also letters)."""
    return max(2, round(gap_chars * 0.34))


def length_ok(text: str, gap_chars: int) -> bool:
    """``text`` (ISO) is within :func:`length_tolerance` of the gap, both counted in Tamil letters
    (:func:`ezhuthu.agent.text.akshara_len`). Comparing ISO characters with a letter count wrongly failed
    130/443 VAL expert targets (issue #26)."""
    return abs(akshara_len(text) - gap_chars) <= length_tolerance(gap_chars)


def ngram_softmax(beams: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """The 5-gram baseline's confidence: softmax over the beam's log-probs (relative to the beam, not calibrated)."""
    if not beams:
        return []
    m = max(lp for _, lp in beams)
    exps = [(t, math.exp(lp - m)) for t, lp in beams]
    z = sum(e for _, e in exps)
    return [(t, round(e / z, 4)) for t, e in exps]


def prerank_score(c: Candidate, n_parallel_fills: int, *, ngram: bool = False) -> float:
    """Cheap pre-rank: noisy-OR of the LLM's probability and parallel support, halved for a length mismatch.
    With ``ngram`` (restorer.ngram_prerank) the 5-gram's softmax share is a third noisy-OR term instead of the
    n-gram epsilon.

    Parallel support = best context match (0..1) x share of parallels whose aligned text is this fill; for the
    copy-floor fill it is at least its own match score, so with no LLM evidence the pre-rank top-1 is the copy
    baseline's.
    Ontology completions (an entity running into the gap) and n-gram proposals get small epsilons
    (ontology 0.02, n-gram 0.01/(rank+1)) so they order ahead of unsupported candidates.
    """
    llm = c.llm_confidence or 0.0
    par = (c.retrieval_score / 100.0) * (len(c.parallels) / max(1, n_parallel_fills))
    if c.copy_floor:  # the copy baseline's pick keeps its full match score (never diluted by disagreement)
        par = max(par, c.retrieval_score / 100.0)
    s = 1.0 - (1.0 - llm) * (1.0 - min(1.0, par))
    if ngram:
        s = 1.0 - (1.0 - s) * (1.0 - min(1.0, c.ngram_prob or 0.0))
    if "ontology" in c.sources:
        s += 0.02
    if c.ngram_rank is not None and not ngram:
        s += 0.01 / (1 + c.ngram_rank)
    if not c.length_ok:
        s *= 0.5
    return round(min(1.0, s), 6)


class Restorer:
    def __init__(self, *, llm: LLMClient | None = None, decider: Decider | None = None,
                 ontology: OntologyPort | None = None, corpus: list[CorpusLine] | None = None,
                 config: ModelsConfig | None = None, use_ontology: bool = True,
                 settings: RestorerSettings | None = None, calibration: CalibrationTable | None = None):
        self.llm = llm
        self.decider = decider or NoDecider()
        self._ontology = ontology
        self._corpus = corpus
        self.config = config or (llm.config if llm else load_models_config())
        self.use_ontology = use_ontology
        # EZHUTHU_RESTORER_STRATEGY overrides config/models.yaml restorer.strategy (e.g. on the cloud runtime).
        self.settings = settings or self.config.restorer.with_(strategy=os.environ.get("EZHUTHU_RESTORER_STRATEGY")
                                                                or None)
        if calibration is None:
            env = os.environ.get("EZHUTHU_CALIBRATION")  # a path, or "none" for raw confidences
            spec = None if env == "none" else (env or self.settings.calibration)
            calibration = CalibrationTable.load(spec, min_n=self.settings.calibration_min_n,
                                                min_positives=self.settings.calibration_min_positives)
        self.calibration = calibration

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
                if rest and length_ok(rest, gap_chars):
                    out.append((rest, h))
                continue
            rec = self.ontology.entity(h.id) or {}
            for surface in [rec.get("label_iso", h.label), *rec.get("variants", [])]:
                s = normalize_iso(surface)
                for k in range(min(len(s) - 1, len(lt)), 2, -1):
                    if lt.endswith(s[:k]):
                        rest = s[k:].strip()
                        if rest and length_ok(rest, gap_chars):
                            out.append((rest, h))
                        break
        return out

    def propose_fills(self, role: str, left: str, right: str, gap_chars: int | None,
                      parallels: list[Parallel], hints: list[Hint], k: int,
                      info: dict[str, Any] | None = None) -> list[tuple[str, float | None]]:
        """LLM fills (compact JSON). A reply cut at ``max_tokens`` keeps every complete fill that arrived and,
        if ``restorer.retry_on_truncation``, is re-asked once with a stricter, shorter prompt."""
        if self.llm is None:
            return []
        pars = [{"inscription_id": p.inscription_id, "line_n": p.line_n, "snippet": p.snippet, "fill": p.fill}
                for p in parallels]
        hs = [h.to_api() for h in hints]
        budget = propose_max_tokens(k, gap_chars, ceiling=self.settings.llm_max_tokens)

        def complete(prompt: str, max_tokens: int):
            t0 = time.perf_counter()
            resp = self.llm.complete(role, RESTORER_SYSTEM, prompt, max_tokens=max_tokens)
            if info is not None:
                info["wall_ms"] = info.get("wall_ms", 0.0) + (time.perf_counter() - t0) * 1000
                info.setdefault("calls", []).append({
                    "model": "opus" if role == "escalate" else "sonnet",
                    "input_tokens": int(getattr(resp, "input_tokens", 0) or 0),
                    "output_tokens": int(getattr(resp, "output_tokens", 0) or 0),
                    "latency_ms": float(getattr(resp, "latency_ms", 0.0) or 0.0),
                    "cached": bool(getattr(resp, "cached", False))})
            return resp

        r = complete(propose_prompt(left, right, gap_chars, pars, hs, k), budget)
        got = parse_candidates(r.text)
        if getattr(r, "truncated", False):
            if info is not None:
                info["truncated"] = info.get("truncated", 0) + 1
            if self.settings.retry_on_truncation:
                k2 = max(1, min(k, 4))
                r2 = complete(propose_prompt(left, right, gap_chars, pars, hs, k2, strict=True),
                              self.settings.llm_max_tokens)
                if info is not None:
                    info["retries"] = info.get("retries", 0) + 1
                    if getattr(r2, "truncated", False):
                        info["truncated"] = info.get("truncated", 0) + 1
                got = parse_candidates(r2.text) + got  # the strict answer first, then what the first reply kept
        out: list[tuple[str, float | None]] = []
        seen: set[str] = set()
        for t, c in got:
            n = normalize_iso(t)
            if n and n not in seen:
                seen.add(n)
                out.append((n, c))
        return out

    def check_constraints(self, cands: list[Candidate], gap_chars: int, *, explicit_length: bool,
                          dynasty: str | None = None) -> list[Candidate]:
        kept = []
        for c in cands:
            c.length_ok = (not explicit_length) or length_ok(c.text, gap_chars)
            c.letters_ok = not non_iso_chars(c.text) and letters_ok_for_dynasty(c.text, dynasty)
            if c.letters_ok:
                kept.append(c)
        return kept

    def rank_and_decide(self, cands: list[Candidate], *, left: str, right: str, gap_chars: int,
                        parallels: list[Parallel], hints: list[Hint],
                        strategy: str | None = None, top_k: int | None = None) -> tuple[str, list[Candidate]]:
        """Set ``confidence`` (raw, before calibration) on each candidate and sort; returns the decider model
        name, ``prerank`` or a ``fallback:...`` tag. ``cands`` must already carry ``prerank`` and be in
        pre-rank order (``restore_gap`` does both)."""
        if not cands:
            return "none", cands
        strategy = strategy or self.settings.strategy
        k = top_k or self.settings.top_k
        lt, rt = left.split("\n")[-1][-60:], right.split("\n")[0][:60]
        state = {
            "text_before_gap": left[-120:], "text_after_gap": right[:120],
            "gap_length_tamil_letters": gap_chars,  # aksharas, like gap_chars (not ISO characters)
            "parallel_passages": [f"{p.inscription_id}: {p.snippet}" for p in parallels[:3]],
            "known_entities_nearby": [h.label for h in hints[:5]],
        }
        if strategy == "prerank":
            tag = "prerank-ngram" if self.settings.ngram_prerank else "prerank"
            for c in cands:
                c.confidence, c.confidence_source, c.decider_source = c.prerank, tag, "prerank"
            return tag, sorted(cands, key=lambda c: c.confidence, reverse=True)

        if strategy == "self-report":
            return self._self_report(cands, parallels)
        if strategy == "choice-all":
            top, rest = cands[:23], cands[23:]  # 24 decider slots, one reserved for "none"
        else:
            top = cands[:k]
            floor = next((c for c in cands if c.copy_floor), None)
            if floor is not None and floor not in top:  # the copy baseline always gets a slot
                top = top[: k - 1] + [floor] if k > 1 else [floor]
            ng = next((c for c in cands if c.ngram_rank == 0), None) if self.settings.ngram_slot else None
            if ng is not None and ng not in top and k > 2:
                # restorer.ngram_slot: the 5-gram's top fill also gets one, displacing the lowest pre-ranked
                # candidate that is neither the pre-rank top-1 nor the copy-baseline fill
                drop = next((c for c in reversed(top) if c is not top[0] and c is not floor), None)
                if drop is not None:
                    top = [ng if c is drop else c for c in top]
            rest = [c for c in cands if c not in top]
        try:
            if strategy == "noul-topk":
                model, source = "", ""
                for c in top:
                    res = self.decider.noul({**state, "candidate": c.option(lt, rt)}, NOUL_INSTRUCTIONS,
                                            name="is_restoration")
                    c.confidence, c.confidence_source, c.decider_source = res.probability, "decider-noul", res.source
                    model, source = res.model, res.source
            else:
                options: dict[str, Any] = {f"c{i}": c.option(lt, rt) for i, c in enumerate(top)}
                options[NONE_OPTION] = "none of these candidates fits the gap"
                res = self.decider.choice(state, DECIDER_INSTRUCTIONS, options, name="restoration")
                model, source = res.model, res.source
                for i, c in enumerate(top):
                    # An option missing from the answer was dropped to fit the request size limit
                    # (HostedDecider fit_choice): the decider never saw it, so do not label it as scored.
                    seen = f"c{i}" in res.probabilities
                    c.confidence = res.probabilities.get(f"c{i}", 0.0)
                    c.confidence_source = "decider" if seen else "decider-trimmed"
                    c.decider_source = res.source
            for c in rest:
                c.confidence, c.decider_source = 0.0, source
                c.confidence_source = "decider-overflow" if strategy == "choice-all" else "not-in-top-k"
            ranked = sorted(top, key=lambda c: c.confidence, reverse=True) + rest
            return model, ranked
        except (DeciderUnavailable, AttributeError):  # AttributeError: a decider without noul()
            pass
        return self._self_report(cands, parallels)

    @staticmethod
    def _self_report(cands: list[Candidate], parallels: list[Parallel]) -> tuple[str, list[Candidate]]:
        """No decider (strategy ``self-report``, or the decider failed): LLM self-reported confidence;
        retrieval-only candidates use agreement among parallels."""
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

    def calibrate(self, decider_model: str, ranked: list[Candidate], *, llm: bool | str | None,
                  strategy: str | None = None, top_k: int | None = None) -> tuple[str | None, float]:
        """Apply the VAL-fitted calibration of this decider variant (if any) to every candidate's confidence.

        ``llm``: the short name of the strongest LLM that answered (``sonnet``/``opus``), or None.
        Returns (variant key or None, abstain threshold). Without a usable (non-provisional) calibration the raw
        confidence stays and the threshold is ``routing.abstain_if_confidence_below``."""
        for c in ranked:
            c.raw_confidence = c.confidence
        key = variant_key(decider_model, strategy or self.settings.strategy, top_k or self.settings.top_k, llm)
        cal: Calibration | None = self.calibration.get(key)
        if cal is None:
            return None, self.config.routing.abstain_if_confidence_below
        for c in ranked:
            c.confidence = cal.apply(c.confidence)
        return key, cal.threshold

    # ---- pipeline ----------------------------------------------------------------
    def _estimate_len(self, gap_chars: int | None, parallels: list[Parallel]) -> int:
        if gap_chars:
            return gap_chars
        fills = [akshara_len(p.fill) for p in parallels if p.fill]
        return int(statistics.median(fills)) if fills else DEFAULT_UNKNOWN_GAP

    def restore_gap(self, left: str, right: str, gap_chars: int | None, *, index: int = 0, router: str = "routed",
                    allow_escalation: bool = True, max_candidates: int = 5, exclude_inscription: str | None = None,
                    dynasty: str | None = None, include_llm: bool = True) -> GapResult:
        if router not in ROUTERS:
            raise ValueError(f"router must be one of {ROUTERS}")
        rt, st = self.config.routing, self.settings
        found = self.retrieve_parallels(left, right, gap_chars, k=max(st.parallels_k, st.prompt_parallels),
                                        exclude_inscription=exclude_inscription)
        parallels = found[: st.prompt_parallels]
        length = self._estimate_len(gap_chars, parallels)
        hints = self.ontology.hints_for_gap(left, right) if self.use_ontology else []
        pool: dict[str, Candidate] = {}

        def add(text: str, source: str, *, conf: float | None = None, par: Parallel | None = None,
                hint: Hint | None = None) -> Candidate | None:
            t = normalize_iso(text)
            if not t:
                return None
            c = pool.setdefault(t, Candidate(t))
            c.sources.add(source)
            if conf is not None:
                c.llm_confidence = conf if c.llm_confidence is None else max(c.llm_confidence, conf)
            if par is not None and par not in c.parallels:
                c.parallels.append(par)
                c.retrieval_score = max(c.retrieval_score, par.score)
            if hint is not None and hint not in c.hints:
                c.hints.append(hint)
            return c

        for p in parallels:
            if p.fill:
                add(p.fill, "parallel", par=p)
        # Copy floor (the copy baseline's top-1): the best-scoring parallel fill within the length tolerance,
        # searched over the full retrieval depth, so the pipeline can always fall back to it.
        floor = next((p for p in found if p.fill and (not gap_chars or length_ok(p.fill, gap_chars))), None)
        if floor is not None:
            fc = add(floor.fill, "parallel", par=floor)
            if fc is not None:
                fc.copy_floor = True
        if self.use_ontology:
            for text, h in self.ontology_candidates(left, right, length):
                add(text, "ontology", hint=h)
        ngram_probs: dict[str, float] | None = None
        if st.ngram_features:  # one beam like the 5-gram baseline's (k = beam = ngram_beam); softmax shares
            beams = ngram_softmax(self.ngram.fill(left, right, length, k=st.ngram_beam,
                                                  beam=max(16, st.ngram_beam)))
            ngram_props = beams[: st.ngram_k]
            ngram_probs = {}
            for text, p in beams:
                t = normalize_iso(text)
                if t:
                    ngram_probs[t] = max(p, ngram_probs.get(t, 0.0))
        else:
            ngram_props = [(t, None) for t, _lp in self.ngram.fill(left, right, length, k=st.ngram_k)]
        for rank, (text, _p) in enumerate(ngram_props):
            c = add(text, "ngram")
            if c is not None and (c.ngram_rank is None or rank < c.ngram_rank):
                c.ngram_rank = rank
        # restorer.ngram_gate: a confident 5-gram top fill is filled with no LLM call (the gate threshold is the
        # 5-gram baseline's VAL-fitted abstain threshold). The fill must pass the same constraints as any candidate.
        gated: str | None = None
        if st.ngram_gate is not None and ngram_props and (ngram_props[0][1] or 0.0) >= st.ngram_gate:
            g = normalize_iso(ngram_props[0][0])
            if g and self.check_constraints([Candidate(g)], length, explicit_length=gap_chars is not None,
                                            dynasty=dynasty):
                gated = g

        good_parallel = any(p.fill and p.score >= 50 for p in parallels)
        models_used: list[str] = []
        escalated = False
        llm_on = include_llm and self.llm is not None and router != "none" and gated is None
        if router == "routed":
            pre_escalate = allow_escalation and (
                length > rt.escalate_if_gap_chars_over or (rt.escalate_if_no_parallel and not good_parallel))
            first_role = "escalate" if pre_escalate else "default"
            escalated = pre_escalate
        else:
            first_role = {"sonnet": "default", "opus": "escalate"}.get(router, "default")
        info: dict[str, Any] = {}
        llm_answered: dict[str, str | None] = {"any": None}  # strongest LLM that answered: "sonnet" / "opus"
        used = {"strategy": st.strategy}

        def call_llm(role: str) -> None:
            try:
                props = self.propose_fills(role, left, right, gap_chars, parallels, hints, st.llm_candidates,
                                           info=info)
            except LiveCallsDisabled:
                log.warning("LLM disabled (EZHUTHU_LIVE!=1); retrieval candidates only")
                return
            mid = self.config.model_id(role)
            models_used.append(mid)
            short = "opus" if role == "escalate" else "sonnet"
            if llm_answered["any"] != "opus":
                llm_answered["any"] = short
            for t, c in props:
                add(t, short, conf=c)

        if llm_on:
            call_llm(first_role)

        def finalize() -> tuple[str, list[Candidate], str | None, float]:
            cands = self.check_constraints(list(pool.values()), length, explicit_length=gap_chars is not None,
                                           dynasty=dynasty)
            for c in cands:  # attach gap-level hints to candidates that contain or continue them
                for h in hints:
                    if h not in c.hints:
                        c.hints.append(h)
            n_par = len([p for p in parallels if p.fill])
            for c in cands:
                if ngram_probs is not None:
                    c.ngram_prob = ngram_probs.get(c.text, 0.0)
                c.prerank = prerank_score(c, n_par, ngram=st.ngram_prerank)
            cands.sort(key=lambda c: (-c.prerank, -(c.llm_confidence or 0), -c.retrieval_score, c.text))
            if gated is not None:  # the 5-gram's fill first at its softmax share; the rest in pre-rank order
                used["strategy"] = "ngram-gate"
                for c in cands:
                    c.raw_confidence = c.confidence = c.ngram_prob if c.text == gated else c.prerank
                    c.confidence_source, c.decider_source = "ngram-gate", "ngram-gate"
                cands.sort(key=lambda c: (c.text != gated, -c.confidence, c.text))
                return "ngram-gate", cands, None, float(st.ngram_gate)
            strat = st.strategy_for(bool(llm_answered["any"]))
            used["strategy"] = strat
            model, ranked = self.rank_and_decide(cands, left=left, right=right, gap_chars=length,
                                                 parallels=parallels, hints=hints, strategy=strat)
            key, thr = self.calibrate(model, ranked, llm=llm_answered["any"], strategy=strat)
            return model, ranked, key, thr

        decider_model, ranked, cal_key, threshold = finalize()
        # Escalation compares the RAW top-1 confidence with routing.escalate_if_confidence_below: that threshold
        # is set on the raw scale, and a calibrated score (fitted per variant for the fill/abstain decision) lives
        # on a different one. The fill/abstain decision below uses the calibrated score and its own threshold.
        raw_best = (ranked[0].raw_confidence or 0.0) if ranked else 0.0
        if (llm_on and router == "routed" and allow_escalation and first_role == "default"
                and raw_best < rt.escalate_if_confidence_below):
            call_llm("escalate")
            escalated = True
            decider_model, ranked, cal_key, threshold = finalize()
        best = ranked[0].confidence if ranked else 0.0

        if decider_model not in ("none", "prerank", "prerank-ngram", "ngram-gate") \
                and not decider_model.startswith("fallback:"):
            models_used.append(decider_model)
        decision = "fill" if ranked and best >= threshold else "abstain"
        return GapResult(index=index, gap_chars=length, decision=decision, chosen=0 if ranked else None,
                         candidates=ranked[:max(1, max_candidates)], decider_model=decider_model,
                         models_used=models_used, escalated=escalated, parallels=parallels,
                         strategy=used["strategy"], calibration=cal_key, abstain_below=threshold,
                         llm_truncated=info.get("truncated", 0), llm_retries=info.get("retries", 0),
                         llm_calls=list(info.get("calls", [])), llm_wall_ms=round(info.get("wall_ms", 0.0), 1))

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
