"""Fine-tuning data for the restorer's decider (issue #37).

The decision: "which candidate fill (or none) matches the expert restoration". Every row is the exact request
``Restorer.rank_and_decide`` sends to a decider, recorded from the restorer itself (a recording decider stands in
for the model), in the two shapes the restorer uses:

* ``choice3``: ``choice`` named ``restoration`` over the pre-rank top-3 (the copy-baseline fill always holds a
  slot) plus ``none``; label = the option whose fill canonically equals the expert target
  (:func:`ezhuthu.eval.metrics.canon`, the scorer of every restoration report), else ``none``. ``none`` keeps its
  natural rate (it is not down-sampled).
* ``noul``: one ``noul`` named ``is_restoration`` per top-3 candidate ("is this the expert restoration?"), yes/no.

Candidates are what the deployed restorer would see: retrieval parallels, the copy floor and the character n-gram
(free), plus Sonnet 4.6 proposals (router ``sonnet``, no escalation; Bedrock replies cached under ``.cache/llm``)
for the items picked for the LLM. Ontology hints are off for every split: the ontology is built from the train
editions, so for a train item it can contain that item's own fill.

Leakage rules (benchmark/DATA_CARD.md "Leakage"):

1. Training rows come from TRAIN items only. Selection uses VAL; TEST is written once and scored once.
2. Train candidates are **cross-fitted**: train inscriptions are cut into ``--folds`` folds by edition group (all
   editions of one stone share a fold), and an item's retrieval corpus and n-gram model are built from the train
   corpus minus its fold. The train corpus has every train fill inline, so without this the copy floor and the
   n-gram would read the item's own answer. VAL/TEST use the full train corpus, as deployed.
3. A train item whose 40-letter context window (20 letters each side, :func:`context_window`) has normalised edit
   similarity >= ``--dup-threshold`` (0.9) with any VAL/TEST item's window is dropped (formulaic near-duplicates),
   and so is one whose window sits inside a VAL/TEST item's context with ``partial_ratio`` >= 90 (the same formula
   gapped at another point, which the window rule misses); both counts are recorded. The reverse direction (a
   VAL/TEST window inside a train item's context) is counted in ``build_meta.json`` (``reverse_direction``) and
   dropped only with ``--symmetric-dups``; ``audit-dups`` adds the count to an existing build.

Gap lengths are Tamil letters (aksharas, ``gap_chars``) throughout. The length check, copy floor, n-gram length
and LLM prompt count letters only in a restorer with the PR #31 fix (``restorer.length_ok``); ``build`` refuses an
older restorer unless ``--allow-char-lengths`` is given, and records which one produced the data.

    # candidates + requests (resumable; Bedrock only with EZHUTHU_LIVE=1; hard cap on live calls across runs)
    python -m ezhuthu.eval.ft_data build --out-dir ../ezhuthu-ft/data --split test --llm all
    python -m ezhuthu.eval.ft_data build --out-dir ../ezhuthu-ft/data --split val --llm 250
    python -m ezhuthu.eval.ft_data build --out-dir ../ezhuthu-ft/data --split train --llm 450
    # rows in every format, sha256s and stats (no model calls)
    python -m ezhuthu.eval.ft_data export --out-dir ../ezhuthu-ft/data \\
        --bench-cands eval/reports/2026-11-02-decider-benchmark-candidates.jsonl
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import random
import sys
import threading
import time
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ..agent import restorer as restorer_module
from ..agent.calibration import CalibrationTable
from ..agent.config import live_enabled, load_models_config
from ..agent.data import BenchmarkItem, CorpusLine
from ..agent.decider import Choice, Noul, choice_payload, noul_payload
from ..agent.llm import LiveCallsDisabled
from ..agent.restorer import Candidate, Restorer
from ..corpus.script import count_aksharas, normalise_for_scoring
from .metrics import canon

log = logging.getLogger(__name__)

CHOICE_K = 3
CHOICE_NAME = "restoration"
NOUL_NAME = "is_restoration"
NONE_OPTION = "none"
TASK_CHOICE = "ezhuthu/restoration-choice3"
TASK_NOUL = "ezhuthu/restoration-noul"
# strands_decider.prompting.NOUL_DEFAULT_CRITERIA: what the server renders for a noul sent without criteria (the
# restorer sends none), so training rows carry exactly these two descriptions.
NOUL_DEFAULT_CRITERIA = {
    "false": "the statement does not hold for this state",
    "true": "the statement holds for this state",
}
WINDOW_LETTERS = 20  # per side: a 40-letter context window
DUP_THRESHOLD = 0.9
PARTIAL_THRESHOLD = 90.0  # shift-invariant formula check (the hard flag's partial_ratio >= 90)
LIVE_BUDGET = 1200  # live Bedrock calls for this dataset, all splits and runs together
SPLITS = ("train", "val", "test")
DECIDER_LAB_SPLIT = {"train": "train", "val": "dev", "test": "test"}  # decider_lab.rows split names


# ---------------------------------------------------------------- leakage --------------------------------------
def _suffix_letters(s: str, n: int) -> str:
    """Longest suffix of ``s`` with at most ``n`` Tamil letters (``count_aksharas`` is monotone in the suffix)."""
    lo, hi = 0, len(s)  # answer start index in [lo, hi]
    while lo < hi:
        mid = (lo + hi) // 2
        if count_aksharas(s[mid:]) <= n:
            hi = mid
        else:
            lo = mid + 1
    return s[lo:]


def _prefix_letters(s: str, n: int) -> str:
    lo, hi = 0, len(s)  # answer end index in [lo, hi]
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if count_aksharas(s[:mid]) <= n:
            lo = mid
        else:
            hi = mid - 1
    return s[:lo]


def context_window(left: str, right: str, n: int = WINDOW_LETTERS) -> str:
    """The gap line's context as compared for near-duplicates: the last ``n`` letters before the gap and the first
    ``n`` after it, letters only (:func:`normalise_for_scoring`: no spaces, hyphens, marks or ``[?N]``)."""
    return f"{_suffix_letters(normalise_for_scoring(left), n)}|{_prefix_letters(normalise_for_scoring(right), n)}"


def near_duplicates(train: Sequence[BenchmarkItem], held_out: Sequence[BenchmarkItem], *,
                    threshold: float = DUP_THRESHOLD, partial_threshold: float | None = PARTIAL_THRESHOLD,
                    n: int = WINDOW_LETTERS, symmetric: bool = False) -> dict[str, dict[str, Any]]:
    """Train items that are formulaic near-duplicates of a VAL/TEST item: ``{train id: {match, split, similarity,
    rule}}`` (best match).

    * ``window``: normalised Levenshtein similarity of the two 40-letter context windows >= ``threshold``.
    * ``partial`` (unless ``partial_threshold`` is None): the train item's window, without the gap mark, scores
      rapidfuzz ``partial_ratio`` >= ``partial_threshold`` inside a VAL/TEST item's whole context (letters only).
      The window rule misses one formula gapped at different points (a gap moved by five letters shifts both
      windows); this is the hard flag's measure (DATA_CARD "How the hard set is defined") and does not care where
      the gap sits.
    * ``reverse`` (only with ``symmetric=True`` and a ``partial_threshold``): the other direction, a VAL/TEST
      item's window inside the train item's whole context (:func:`reverse_near_duplicates`). The data of issue #37
      was built without it (``symmetric=False``); its reverse-direction count is recorded by ``audit-dups``.
    """
    if not train or not held_out:
        return {}
    from rapidfuzz import fuzz, process
    from rapidfuzz.distance import Levenshtein

    tw = [context_window(it.left, it.right, n) for it in train]
    hw = [context_window(it.left, it.right, n) for it in held_out]
    sims = process.cdist(tw, hw, scorer=Levenshtein.normalized_similarity, workers=-1)
    part = None
    if partial_threshold is not None:
        hl = [normalise_for_scoring(it.left) + normalise_for_scoring(it.right) for it in held_out]
        part = process.cdist([w.replace("|", "") for w in tw], hl, scorer=fuzz.partial_ratio, workers=-1)
    out: dict[str, dict[str, Any]] = {}
    for i, it in enumerate(train):
        j = int(sims[i].argmax())
        s = float(sims[i][j])
        if s >= threshold:
            out[it.id] = {"match": held_out[j].id, "split": held_out[j].split, "similarity": round(s, 4),
                          "rule": "window"}
        elif part is not None:
            j = int(part[i].argmax())
            s = float(part[i][j]) / 100.0
            if s * 100.0 >= partial_threshold:
                out[it.id] = {"match": held_out[j].id, "split": held_out[j].split, "similarity": round(s, 4),
                              "rule": "partial"}
    if symmetric and partial_threshold is not None:
        for k, v in reverse_near_duplicates([it for it in train if it.id not in out], held_out,
                                            partial_threshold=partial_threshold, n=n).items():
            out[k] = {"match": v["match"], "split": v["split"], "similarity": v["similarity"], "rule": "reverse"}
    return out


def reverse_near_duplicates(train: Sequence[BenchmarkItem], held_out: Sequence[BenchmarkItem], *,
                            partial_threshold: float = PARTIAL_THRESHOLD,
                            n: int = WINDOW_LETTERS) -> dict[str, dict[str, Any]]:
    """The reverse direction of the ``partial`` rule: a VAL/TEST item's 40-letter window (without the gap mark)
    scores ``partial_ratio`` >= ``partial_threshold`` inside a train item's whole context (letters only).
    ``{train id: {match, split, similarity, matches, same_target}}``: the best match, every held-out item over the
    threshold, and whether any of them has the train item's target (under ``canon``)."""
    if not train or not held_out:
        return {}
    from rapidfuzz import fuzz, process

    hw = [context_window(it.left, it.right, n).replace("|", "") for it in held_out]
    tl = [normalise_for_scoring(it.left) + normalise_for_scoring(it.right) for it in train]
    part = process.cdist(tl, hw, scorer=fuzz.partial_ratio, workers=-1)
    out: dict[str, dict[str, Any]] = {}
    for i, it in enumerate(train):
        hits = [j for j in range(len(held_out)) if float(part[i][j]) >= partial_threshold]
        if not hits:
            continue
        j = max(hits, key=lambda k: float(part[i][k]))
        out[it.id] = {"match": held_out[j].id, "split": held_out[j].split,
                      "similarity": round(float(part[i][j]) / 100.0, 4),
                      "matches": [held_out[k].id for k in hits],
                      "same_target": any(canon(held_out[k].target) == canon(it.target) for k in hits)}
    return out


def reverse_audit(train: Sequence[BenchmarkItem], held_out: Sequence[BenchmarkItem], *,
                  thresholds: Sequence[float] = (90.0, 85.0, 80.0), n: int = WINDOW_LETTERS) -> dict[str, Any]:
    """Reverse-direction counts over the *kept* train items (``train`` already filtered), per threshold: kept
    train items hit, distinct held-out items they tie to (by split), and (train, held-out) pairs sharing the
    target."""
    out: dict[str, Any] = {"direction": "held-out 40-letter window inside a kept train item's context "
                           "(rapidfuzz partial_ratio)", "kept_train_items": len(train)}
    split_of = {it.id: it.split for it in held_out}
    target_of = {it.id: canon(it.target) for it in held_out}
    tr_target = {it.id: canon(it.target) for it in train}
    for t in sorted(thresholds, reverse=True):
        hits = reverse_near_duplicates(train, held_out, partial_threshold=t, n=n)
        held = {h for v in hits.values() for h in v["matches"]}
        pairs = [(k, h) for k, v in hits.items() for h in v["matches"]]
        out[f"partial_ratio>={t:g}"] = {
            "kept_train_items": len(hits), "heldout_items": len(held),
            "heldout_by_split": dict(sorted(Counter(split_of[h] for h in held).items())), "pairs": len(pairs),
            "pairs_same_target": sum(1 for k, h in pairs if tr_target[k] == target_of[h]),
        }
    return out


def edition_groups(inscriptions: dict[str, dict[str, Any]]) -> dict[str, str]:
    """Inscription id -> group id (the smallest id among the editions of one stone, via ``same_stone_as``)."""
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for iid, meta in inscriptions.items():
        find(iid)
        for other in meta.get("same_stone_as") or []:
            a, b = find(iid), find(other)
            if a != b:
                parent[max(a, b)] = min(a, b)
    return {iid: find(iid) for iid in list(parent)}


def assign_folds(inscription_ids: Iterable[str], groups: dict[str, str], k: int, seed: int) -> dict[str, int]:
    """Deterministic fold per inscription; every edition group lands in one fold."""
    roots = sorted({groups.get(i, i) for i in inscription_ids})
    random.Random(seed).shuffle(roots)
    fold_of_root = {r: n % k for n, r in enumerate(roots)}
    return {i: fold_of_root[groups.get(i, i)] for i in inscription_ids}


def fold_corpus(corpus: Sequence[CorpusLine], folds: dict[str, int], fold: int) -> list[CorpusLine]:
    """The train corpus without the inscriptions of ``fold`` (lines of inscriptions without a fold are kept)."""
    return [ln for ln in corpus if folds.get(ln.inscription_id) != fold]


def plan_llm(ids: Sequence[str], n: int | None, seed: int) -> set[str]:
    """A seeded sample of ``n`` ids (``None`` = all) that get Sonnet proposals."""
    ids = sorted(ids)
    if n is None or n >= len(ids):
        return set(ids)
    return set(random.Random(seed).sample(ids, n))


# ---------------------------------------------------------------- recording ------------------------------------
class RecordingDecider:
    """Stands in for the decider: records every request (per thread) and answers uniformly, so the restorer runs
    its normal decider path and the recorded request is exactly what a real decider would receive."""

    model = "ft-data-recorder"

    def __init__(self) -> None:
        self._tl = threading.local()

    @property
    def calls(self) -> list[dict[str, Any]]:
        if not hasattr(self._tl, "calls"):
            self._tl.calls = []
        return self._tl.calls

    def reset(self) -> None:
        self._tl.calls = []

    def available(self) -> bool:
        return True

    def choice(self, state: Any, instructions: str, options: dict[str, Any], *, name: str = "q") -> Choice:
        self.calls.append({"type": "choice", "name": name, "state": state, "instructions": instructions,
                           "options": options})
        p = 1.0 / len(options)
        return Choice(next(iter(options)), {k: p for k in options}, 0.0, self.model, source="fake")

    def noul(self, state: Any, instructions: str, *, name: str = "q") -> Noul:
        self.calls.append({"type": "noul", "name": name, "state": state, "instructions": instructions})
        return Noul(0.5, self.model, source="fake")


def _snapshot(c: Candidate) -> dict[str, Any]:
    return {"fill": c.text, "sources": sorted(c.sources), "llm_probability": c.llm_confidence,
            "retrieval_score": c.retrieval_score, "parallel_support": len(c.parallels), "copy_floor": c.copy_floor,
            "ngram_rank": c.ngram_rank, "prerank": c.prerank, "length_ok": c.length_ok}


class CapturingRestorer(Restorer):
    """The production restorer; ``rank_and_decide`` records the ``choice-topk:3`` request, the ``noul-topk:3``
    requests and the pool (pre-rank order, with the self-report fallback confidence of every candidate) instead
    of deciding. One instance can serve several threads (captures are thread-local)."""

    def __init__(self, **kw: Any):
        self.recorder = RecordingDecider()
        kw.setdefault("calibration", CalibrationTable(min_n=0, min_positives=0))
        kw.setdefault("use_ontology", False)
        super().__init__(decider=self.recorder, **kw)
        self._tl = threading.local()

    @property
    def capture(self) -> dict[str, Any] | None:
        return getattr(self._tl, "capture", None)

    def clear(self) -> None:
        self._tl.capture = None

    def rank_and_decide(self, cands: list[Candidate], **kw: Any) -> tuple[str, list[Candidate]]:
        order = list(cands)
        pool = [_snapshot(c) for c in order]
        kw = {**kw, "top_k": CHOICE_K}
        self.recorder.reset()
        super().rank_and_decide(list(order), **{**kw, "strategy": "choice-topk"})
        choice = next((c for c in self.recorder.calls if c["type"] == "choice"), None)
        self.recorder.reset()
        super().rank_and_decide(list(order), **{**kw, "strategy": "noul-topk"})
        nouls = [c for c in self.recorder.calls if c["type"] == "noul"]
        self.recorder.reset()
        tag, ranked = self._self_report(list(order), kw.get("parallels") or [])
        for snap, c in zip(pool, order, strict=True):
            snap["self_report"] = round(c.confidence, 4)
            snap["self_report_source"] = c.confidence_source
        self._tl.capture = {"choice": choice, "noul": nouls, "pool": pool, "fallback_tag": tag}
        return tag, ranked


def restorer_counts_letters() -> bool:
    """True when the installed restorer compares gap lengths in Tamil letters (PR #31, issue #26)."""
    return hasattr(restorer_module, "length_ok")


class CappedLLM:
    """Thread-safe hard cap on live (uncached) calls: a call is reserved before it is made, so concurrent workers
    can never exceed ``max_live``. Over the cap it raises ``LiveCallsDisabled`` (the restorer then keeps retrieval
    candidates only, and the item is labelled so)."""

    def __init__(self, inner: Any, max_live: int):
        self.inner, self.max_live = inner, max_live
        self.config, self.ledger = inner.config, inner.ledger
        self._lock = threading.Lock()
        self.reserved = 0
        self.refused = 0
        self.attempts = 0  # Bedrock invocations including throttling retries

    def complete(self, role: str, system: str, prompt: str, *, max_tokens: int = 1024):
        cache = getattr(self.inner, "cache", None)
        cached = cache is not None and cache.get(cache.key(self.config.model_id(role), system, prompt,
                                                           max_tokens)) is not None
        if not cached:
            with self._lock:
                if self.reserved >= self.max_live:
                    self.refused += 1
                    raise LiveCallsDisabled(f"live-call budget of {self.max_live} reached")
                self.reserved += 1
        r = self.inner.complete(role, system, prompt, max_tokens=max_tokens)
        if not getattr(r, "cached", False):
            with self._lock:
                self.attempts += int(getattr(r, "attempts", 1) or 1)
        return r


# ---------------------------------------------------------------- records --------------------------------------
def build_record(r: CapturingRestorer, it: BenchmarkItem, *, llm: bool, fold: int | None) -> dict[str, Any]:
    """One item: its candidate pool and the recorded decider requests."""
    rec: dict[str, Any] = {
        "id": it.id, "split": it.split, "inscription_id": it.inscription_id, "collection": it.collection,
        "fold": fold, "hard": it.hard, "age_set": it.age_set, "gap_letters": it.gap_chars, "target": it.target,
        "target_letters": count_aksharas(it.target), "llm_planned": llm,
    }
    r.clear()
    t0 = time.perf_counter()
    g = r.restore_gap(it.left, it.right, it.gap_chars, router="sonnet" if llm else "none", max_candidates=23,
                      exclude_inscription=it.inscription_id, dynasty=it.dynasty)
    cap = r.capture or {"choice": None, "noul": [], "pool": [], "fallback_tag": None}
    # The request is the one the restorer sends once the LLM answered (even if it proposed nothing new), so the
    # source follows the call; llm_in_pool says whether an LLM fill survived the constraints.
    llm_answered = any(("sonnet" in m or "opus" in m) for m in g.models_used)
    rec.update({
        "candidate_source": "sonnet+retrieval" if llm_answered else "retrieval",
        "llm_in_pool": any(("sonnet" in p["sources"] or "opus" in p["sources"]) for p in cap["pool"]),
        "models_used": g.models_used, "llm_truncated": g.llm_truncated, "llm_retries": g.llm_retries,
        "latency_ms": round((time.perf_counter() - t0) * 1000, 1), **cap,
    })
    return rec


def _label_choice(options: dict[str, Any], target: str) -> str:
    t = canon(target)
    for k, v in options.items():
        if k != NONE_OPTION and isinstance(v, dict) and canon(v.get("fill", "")) == t:
            return k
    return NONE_OPTION


def rows_from_record(rec: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Native ``choice3`` and ``noul`` rows of one record (none when the restorer had no candidate)."""
    req = rec.get("choice")
    if not req:
        return [], []
    t = canon(rec["target"])
    pool = rec.get("pool") or []
    by_fill = {p["fill"]: p for p in pool}
    in_pool = any(canon(p["fill"]) == t for p in pool)
    opts = req["options"]
    keys = list(opts)
    fills = [opts[k]["fill"] for k in keys if k != NONE_OPTION]
    label = _label_choice(opts, rec["target"])
    common = {
        "item_id": rec["id"], "split": rec["split"], "inscription_id": rec["inscription_id"], "fold": rec.get("fold"),
        "hard": rec["hard"], "age_set": rec["age_set"], "gap_letters": rec["gap_letters"], "target": rec["target"],
        "candidate_source": rec["candidate_source"], "target_in_pool": in_pool, "pool_size": len(pool),
    }
    choice_row = {
        "id": f"{rec['id']}#choice3", "shape": "choice3", **common,
        "label": label, "label_index": keys.index(label), "option_keys": keys, "fills": fills,
        "target_in_options": label != NONE_OPTION,
        "self_report": [by_fill.get(f, {}).get("self_report") for f in fills],
        "llm_probability": [by_fill.get(f, {}).get("llm_probability") for f in fills],
        "prerank": [by_fill.get(f, {}).get("prerank") for f in fills],
        "fill_sources": [by_fill.get(f, {}).get("sources") for f in fills],
        "pool_self_report_top1": (max(pool, key=lambda p: p.get("self_report") or 0.0)["fill"] if pool else None),
        "request": choice_payload(req["state"], req["instructions"], opts, req["name"]),
    }
    noul_rows = []
    for i, nq in enumerate(rec.get("noul") or []):
        cand = nq["state"]["candidate"]
        noul_rows.append({
            "id": f"{rec['id']}#noul{i}", "shape": "noul", **common, "option_key": f"c{i}", "fill": cand["fill"],
            "label": "yes" if canon(cand["fill"]) == t else "no",
            "self_report": by_fill.get(cand["fill"], {}).get("self_report"),
            "request": noul_payload(nq["state"], nq["instructions"], nq["name"]),
        })
    return [choice_row], noul_rows


def bench_records(frozen: Iterable[dict[str, Any]], k: int = CHOICE_K) -> list[dict[str, Any]]:
    """Records from the frozen decider-benchmark candidates (``decider_bench freeze``, choice-all request, pre-#31
    shape): the first ``k`` options + ``none`` is exactly what ``decider_bench score --top-k 3`` sent (hosted v19
    top-3 0.450), and the noul requests are the restorer's noul over those ``k``."""
    from ..agent.restorer import NOUL_INSTRUCTIONS

    out = []
    for fr in frozen:
        req = fr.get("request")
        if not req:
            continue
        opts = req["options"]
        keys = [x for x in opts if x != NONE_OPTION][:k] + [x for x in opts if x == NONE_OPTION]
        top = {x: opts[x] for x in keys}
        fills = fr.get("fills") or []
        confs = fr.get("fallback_confidence") or []
        pool = [{"fill": f, "self_report": (confs[i] if i < len(confs) else None),
                 "llm_probability": (fr.get("llm_confidence") or [None] * len(fills))[i], "prerank": None}
                for i, f in enumerate(fills)]
        nouls = [{"type": "noul", "name": NOUL_NAME, "instructions": NOUL_INSTRUCTIONS,
                  "state": {**req["state"], "candidate": top[x]}} for x in keys if x != NONE_OPTION]
        out.append({
            "id": fr["id"], "split": "test", "inscription_id": fr.get("inscription_id"), "fold": None,
            "hard": fr.get("hard"), "age_set": fr.get("age_set"), "gap_letters": fr.get("gap_chars"),
            "target": fr["target"], "candidate_source": "sonnet+retrieval",
            "choice": {**req, "options": top}, "noul": nouls, "pool": pool,
        })
    return out


# ---------------------------------------------------------------- formats --------------------------------------
def _desc(v: Any) -> str:
    """An option as the decider renders it: ``render_content`` gives a dict as indented JSON, then the option line
    collapses whitespace, so this string renders to the same line as the dict the restorer sends."""
    return v if isinstance(v, str) else json.dumps(v, indent=2, ensure_ascii=False)


def to_example(row: dict[str, Any]) -> dict[str, Any]:
    """A ``strands_decider.data.format.Example`` (= Sparrow training row): kind, state, instructions, options,
    label (index), task, weight, instruction_variants."""
    q = next(iter(row["request"]["questions"].values()))
    if q["type"] == "choice":
        options = [[k, _desc(v)] for k, v in q["criteria"].items()]
        label = [k for k, _ in options].index(row["label"])
        task = TASK_CHOICE
    else:
        options = [["false", NOUL_DEFAULT_CRITERIA["false"]], ["true", NOUL_DEFAULT_CRITERIA["true"]]]
        label = 1 if row["label"] == "yes" else 0
        task = TASK_NOUL
    return {"kind": q["type"], "state": row["request"]["state"], "instructions": q["instructions"],
            "options": options, "label": label, "task": task, "weight": 1.0, "instruction_variants": []}


def to_decider_lab(row: dict[str, Any]) -> dict[str, Any]:
    """A decider-lab row (``decider_lab.rows``): the Example plus ``split`` (train/dev/test) and ``id``."""
    return {**to_example(row), "split": DECIDER_LAB_SPLIT.get(row["split"], row["split"]), "id": row["id"]}


# ---------------------------------------------------------------- stats ----------------------------------------
def stats(choice_rows: Sequence[dict[str, Any]], noul_rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    n = len(choice_rows)
    if not n:
        return {"rows_choice3": 0, "rows_noul": len(noul_rows)}
    labels = Counter(r["label"] for r in choice_rows)
    llm = [r for r in choice_rows if r["candidate_source"] == "sonnet+retrieval"]

    def share(rows: Sequence[dict[str, Any]], key: str) -> float | None:
        return round(sum(bool(r[key]) for r in rows) / len(rows), 4) if rows else None

    sr_top3 = [r for r in choice_rows if any(x is not None for x in r["self_report"])]
    return {
        "rows_choice3": n, "rows_noul": len(noul_rows),
        "label_counts": dict(sorted(labels.items())), "none_share": round(labels.get(NONE_OPTION, 0) / n, 4),
        "noul_yes_share": round(sum(r["label"] == "yes" for r in noul_rows) / max(1, len(noul_rows)), 4),
        "llm_share": round(len(llm) / n, 4),
        "llm_fill_in_top3_share": round(sum(any("sonnet" in (s or []) for s in r.get("fill_sources", []))
                                            for r in choice_rows) / n, 4),
        "hard_share": share(choice_rows, "hard"),
        "target_in_top3": share(choice_rows, "target_in_options"),
        "target_in_top3_llm": share(llm, "target_in_options"),
        "target_in_top3_retrieval": share([r for r in choice_rows if r not in llm], "target_in_options"),
        "target_in_pool": share(choice_rows, "target_in_pool"),
        # reference points on the same rows (no decider): c0 (pre-rank top-1) and self-report over the top-3
        "first_option_top1": round(sum(r["label"] == "c0" for r in choice_rows) / n, 4),
        "self_report_top3_top1": round(sum(
            r["label"] == r["option_keys"][max(range(len(r["fills"])), key=lambda i: r["self_report"][i] or 0.0)]
            for r in sr_top3) / max(1, len(sr_top3)), 4),
        "pool_self_report_top1": round(sum(canon(r["pool_self_report_top1"] or "") == canon(r["target"])
                                           for r in choice_rows) / n, 4),
    }


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def export(out_dir: Path, *, bench_cands: Path | None = None) -> dict[str, Any]:
    """Rows in every format from ``records/<split>.jsonl`` (+ the frozen 60-item benchmark), with sha256s and
    stats in ``manifest.json``. No model calls."""
    sets: dict[str, list[dict[str, Any]]] = {s: read_jsonl(out_dir / "records" / f"{s}.jsonl") for s in SPLITS}
    if bench_cands is not None:
        sets["test-bench60"] = bench_records(read_jsonl(bench_cands))
    files: dict[str, dict[str, Any]] = {}
    st: dict[str, Any] = {}
    for name, recs in sets.items():
        recs = [r for r in recs if not r.get("error")]
        choice_rows, noul_rows = [], []
        for rec in recs:
            c, nl = rows_from_record(rec)
            choice_rows += c
            noul_rows += nl
        st[name] = {"items": len(recs), "items_without_candidates": sum(1 for r in recs if not r.get("choice")),
                    **stats(choice_rows, noul_rows)}
        if name == "test":
            hard = [r for r in choice_rows if r["hard"]]
            st["test-hard"] = stats(hard, [r for r in noul_rows if r["hard"]])
        for shape, rows in (("choice3", choice_rows), ("noul", noul_rows)):
            for fmt, conv, sub in (("ezhuthu", None, ""), ("strands-decider", to_decider_lab, "strands-decider/"),
                                   ("sparrow", to_example, "sparrow/")):
                p = out_dir / f"{sub}{name}.{shape}.jsonl"
                n = write_jsonl(p, (conv(r) if conv else r for r in rows))
                files[str(p.relative_to(out_dir))] = {"rows": n, "sha256": sha256_file(p), "format": fmt}
    manifest = {"created": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "files": files, "stats": st}
    for s in SPLITS:
        p = out_dir / "records" / f"{s}.jsonl"
        if p.is_file():
            manifest.setdefault("records", {})[s] = {"sha256": sha256_file(p), "rows": len(sets[s])}
    meta = out_dir / "build_meta.json"
    if meta.is_file():
        manifest["build"] = json.loads(meta.read_text())
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    return manifest


# ---------------------------------------------------------------- build ----------------------------------------
def _git_head(path: Path) -> str | None:
    """HEAD of the checkout at ``path``, only when ``path`` is that checkout's root (has its own ``.git``): an
    exported tree that happens to sit inside another repository must not report that repository's commit."""
    import subprocess

    if not (path / ".git").exists():
        return None
    try:
        return subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def build(args: argparse.Namespace) -> int:
    from ..agent.data import data_source, load_corpus_lines, load_inscriptions, load_items

    if not restorer_counts_letters() and not args.allow_char_lengths:
        print("this restorer compares gap lengths in ISO characters (pre-PR #31); run with the letter-count fix "
              "or pass --allow-char-lengths", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    (out_dir / "records").mkdir(parents=True, exist_ok=True)
    usage_p = out_dir / "usage.json"
    usage = json.loads(usage_p.read_text()) if usage_p.is_file() else {"live_calls": 0, "attempts": 0, "runs": []}
    remaining = max(0, args.budget - usage["live_calls"])

    src = data_source()
    if src.is_fixture and not args.allow_fixtures:
        print(f"benchmark not found (fixtures at {src.path}); run from the repo root", file=sys.stderr)
        return 2
    items = load_items(args.split, src=src)
    corpus = list(load_corpus_lines(src))
    insc = load_inscriptions(src)
    meta: dict[str, Any] = {}
    folds: dict[str, int] = {}
    dropped: dict[str, dict[str, Any]] = {}
    if args.split == "train":
        held = load_items("val", src=src) + load_items("test", src=src)
        dropped = near_duplicates(items, held, threshold=args.dup_threshold,
                                  partial_threshold=None if args.no_partial_dups else args.partial_threshold,
                                  symmetric=args.symmetric_dups)
        (out_dir / "dropped_near_duplicates.json").write_text(json.dumps(dropped, indent=1, ensure_ascii=False))
        groups = edition_groups({k: v for k, v in insc.items() if v.get("split") == "train"})
        folds = assign_folds([k for k, v in insc.items() if v.get("split") == "train"], groups, args.folds,
                             args.seed)
        meta = {"train_items": len(items), "dropped_near_duplicates": len(dropped),
                "dropped_by_rule": dict(Counter(v["rule"] for v in dropped.values())),
                "dropped_by_heldout_split": dict(Counter(v["split"] for v in dropped.values())),
                "dup_threshold": args.dup_threshold, "partial_threshold": None if args.no_partial_dups
                else args.partial_threshold, "window_letters": 2 * WINDOW_LETTERS, "folds": args.folds,
                "symmetric_dups": args.symmetric_dups}
        items = [it for it in items if it.id not in dropped]
        meta["reverse_direction"] = reverse_audit(items, held)
    if args.limit:
        items = items[: args.limit]
    planned = plan_llm([it.id for it in items], None if args.llm == "all" else int(args.llm), args.seed)

    llm = None
    if planned and args.llm != "0":
        if not live_enabled():
            print("Sonnet proposals need EZHUTHU_LIVE=1 (cached replies are reused); or pass --llm 0",
                  file=sys.stderr)
            return 2
        from ..agent.llm import BedrockLLM

        llm = CappedLLM(BedrockLLM(), remaining)
    settings = load_models_config().restorer.with_(strategy="choice-topk", top_k=CHOICE_K)
    restorers: dict[int | None, CapturingRestorer] = {}
    if args.split == "train":
        for f in range(args.folds):
            restorers[f] = CapturingRestorer(llm=llm, corpus=fold_corpus(corpus, folds, f), settings=settings)
    else:
        restorers[None] = CapturingRestorer(llm=llm, corpus=corpus, settings=settings)
    for r in restorers.values():  # build lazily-cached resources before threads share them
        _ = r.index, r.ngram

    out = out_dir / "records" / f"{args.split}.jsonl"
    done = {r["id"] for r in read_jsonl(out) if not r.get("error")}
    todo = [it for it in items if it.id not in done]
    lock = threading.Lock()

    def one(it: BenchmarkItem) -> None:
        fold = folds.get(it.inscription_id) if args.split == "train" else None
        try:
            rec = build_record(restorers[fold], it, llm=it.id in planned and llm is not None, fold=fold)
        except Exception as exc:  # noqa: BLE001 - recorded, retried on the next run
            rec = {"id": it.id, "split": it.split, "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
            log.warning("item %s: %s", it.id, rec["error"])
        with lock, out.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    t0 = time.time()
    run: dict[str, Any] = {"split": args.split, "items": len(items), "new": len(todo), "llm_planned": len(planned),
                           "at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}
    base_calls, base_attempts = usage["live_calls"], usage["attempts"]
    usage["runs"].append(run)

    def save_usage() -> None:  # after every item, so a killed run still leaves an exact count
        run["seconds"] = round(time.time() - t0, 1)
        if llm is not None:
            run.update({"live_calls": llm.reserved, "attempts": llm.attempts, "refused_over_budget": llm.refused,
                        "usage": llm.ledger.to_dict()})
            usage["live_calls"] = base_calls + llm.reserved
            usage["attempts"] = base_attempts + llm.attempts
        usage_p.write_text(json.dumps(usage, indent=1))

    def one_and_save(it: BenchmarkItem) -> None:
        one(it)
        with lock:
            save_usage()

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        list(ex.map(one_and_save, todo))
    # keep the last record per id (a failed one is replaced on a re-run)
    last = {r["id"]: r for r in read_jsonl(out)}
    write_jsonl(out, [last[it.id] for it in items if it.id in last])
    save_usage()
    bm = out_dir / "build_meta.json"
    allmeta = json.loads(bm.read_text()) if bm.is_file() else {}
    root = Path(__file__).resolve().parents[3]
    allmeta[args.split] = {
        **meta, "llm_planned": len(planned), "seed": args.seed, "llm_model": load_models_config().model_id("default"),
        "router": "sonnet (no escalation)", "use_ontology": False, "strategy_recorded": f"choice-topk:{CHOICE_K}, "
        f"noul-topk:{CHOICE_K}", "letter_counting_restorer": restorer_counts_letters(),
        "restorer_file": restorer_module.__file__, "code_head": _git_head(root), "code_note": args.code_note,
        "data_dir": str(src.path),
        "data_commit": _git_head(src.path.parent), "benchmark_sha256": {
            f: sha256_file(src.path / f) for f in (f"items.{args.split}.jsonl", "corpus_lines.jsonl")},
    }
    bm.write_text(json.dumps(allmeta, indent=1))
    print(json.dumps({**run, "budget_left": args.budget - usage["live_calls"]}))
    return 0


def audit_dups(out_dir: Path, thresholds: Sequence[float]) -> int:
    """Add the reverse-direction audit to ``build_meta.json`` ``train`` for a build made before it existed. The
    kept train items are the train split minus ``dropped_near_duplicates.json``; nothing else is rewritten (the
    rows, their sha256s and ``manifest.json`` stay as built). Pairs at the highest threshold go to
    ``reverse_near_duplicates.json``."""
    from ..agent.data import data_source, load_items

    src = data_source()
    if src.is_fixture:
        print(f"benchmark not found (fixtures at {src.path}); run from the repo root", file=sys.stderr)
        return 2
    bm = out_dir / "build_meta.json"
    allmeta = json.loads(bm.read_text())
    if sha256_file(src.path / "items.train.jsonl") != allmeta["train"]["benchmark_sha256"]["items.train.jsonl"]:
        print("items.train.jsonl differs from the one the data was built from", file=sys.stderr)
        return 2
    dropped = json.loads((out_dir / "dropped_near_duplicates.json").read_text())
    kept = [it for it in load_items("train", src=src) if it.id not in dropped]
    held = load_items("val", src=src) + load_items("test", src=src)
    audit = reverse_audit(kept, held, thresholds=thresholds)
    audit["at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    audit["note"] = "recorded after the build by audit-dups; not used to drop rows (the rows are as built)"
    rev = reverse_near_duplicates(kept, held, partial_threshold=max(thresholds))
    (out_dir / "reverse_near_duplicates.json").write_text(json.dumps(rev, indent=1, ensure_ascii=False))
    allmeta["train"]["reverse_direction"] = audit
    bm.write_text(json.dumps(allmeta, indent=1))
    print(json.dumps(audit, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="candidate pools + recorded decider requests for one split")
    b.add_argument("--out-dir", required=True)
    b.add_argument("--split", required=True, choices=SPLITS)
    b.add_argument("--llm", default="0", help="items with Sonnet proposals: a number (seeded sample), all or 0")
    b.add_argument("--budget", type=int, default=LIVE_BUDGET, help="live Bedrock calls for the whole dataset")
    b.add_argument("--folds", type=int, default=5)
    b.add_argument("--seed", type=int, default=13)
    b.add_argument("--dup-threshold", type=float, default=DUP_THRESHOLD)
    b.add_argument("--partial-threshold", type=float, default=PARTIAL_THRESHOLD)
    b.add_argument("--no-partial-dups", action="store_true", help="only the 40-letter window rule")
    b.add_argument("--symmetric-dups", action="store_true",
                   help="also drop train items whose context holds a VAL/TEST window (rule 'reverse')")
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--limit", type=int, default=None)
    b.add_argument("--allow-char-lengths", action="store_true")
    b.add_argument("--allow-fixtures", action="store_true")
    b.add_argument("--code-note", default=None, help="provenance of the code tree when it is not a git checkout")
    e = sub.add_parser("export", help="rows in every format, sha256s and stats (no model calls)")
    e.add_argument("--out-dir", required=True)
    e.add_argument("--bench-cands", default=None)
    a = sub.add_parser("audit-dups", help="record the reverse-direction near-duplicate counts of an existing "
                       "train build in build_meta.json (no model calls, rows unchanged)")
    a.add_argument("--out-dir", required=True)
    a.add_argument("--thresholds", default="90,85,80")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.cmd == "build":
        return build(args)
    if args.cmd == "audit-dups":
        return audit_dups(Path(args.out_dir), [float(t) for t in args.thresholds.split(",")])
    m = export(Path(args.out_dir), bench_cands=Path(args.bench_cands) if args.bench_cands else None)
    print(json.dumps(m["stats"], indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
