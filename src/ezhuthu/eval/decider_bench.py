"""Decider benchmark: score several deciders on the SAME frozen candidate sets.

    # 1. freeze candidates once (Sonnet 4.6 via Bedrock, cached under .cache/llm; needs EZHUTHU_LIVE=1)
    python -m ezhuthu.eval.decider_bench freeze --split test --subset hard --limit 60 --out <cands.jsonl>
    # 2. score each decider on that file (results cached per decider label)
    python -m ezhuthu.eval.decider_bench score --cands <cands.jsonl> --decider local=http://127.0.0.1:8771 --label 2b
    python -m ezhuthu.eval.decider_bench score --cands <cands.jsonl> --decider hosted --label hosted-v19
    python -m ezhuthu.eval.decider_bench score --cands <cands.jsonl> --decider fallback --label llm-self
    # 3. tutor-policy check on 20 scripted learner states, then the report
    python -m ezhuthu.eval.decider_bench policy --decider local=http://127.0.0.1:8771 --label 2b
    python -m ezhuthu.eval.decider_bench report --cands <cands.jsonl> --labels 2b,e4b,hosted-v19,llm-self \
        --out eval/reports/<date>-decider-benchmark --sync-from-cache

``report`` reads the per-item rows from ``<out>/restoration-<label>.jsonl`` and ``<out>/policy-<label>.jsonl``
(committed next to the report, so every number is re-derivable from git); ``--sync-from-cache`` first copies
them there from ``.cache/decider-bench``.

Each item's decider request is exactly the ``rank_and_decide`` request of the restorer (same state, same
instructions, same options c0..cN + ``none``), so the deciders differ only in the model that answers. The top-1
fill is the candidate with the highest probability, its probability is the confidence, and the item abstains
under ``routing.abstain_if_confidence_below``. ``llm-self`` scores the restorer's flagged fallback (Sonnet's
self-reported confidence, else the retrieval heuristic) on the same candidates.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import shutil
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..agent.config import live_enabled, load_models_config, repo_root
from ..agent.decider import (
    Decider,
    DeciderUnavailable,
    HostedDecider,
    HttpDecider,
    NoDecider,
    choice_payload,
    fit_choice,
    hosted_decider,
    request_chars,
)
from ..agent.prompts import RESTORER_SYSTEM, parse_candidates, propose_prompt
from ..agent.restorer import Candidate, Restorer
from ..agent.text import normalize_iso
from ..agent.tutor import policy
from .metrics import canon, coverage_curve, ece, reliability

CURVE = (0.1, 0.2, 0.3, 0.4, 0.5, 0.7)

log = logging.getLogger(__name__)
PROPOSE_MAX_TOKENS = 2048  # the pipeline's 800 truncates (MaxTokensReachedException); see eval/reports quick eval


# ---------------------------------------------------------------- freeze -------------------------------------
class _Recorder:
    """Records the decider request and refuses it, so the restorer falls back to LLM self-report."""

    def __init__(self):
        self.last: dict[str, Any] | None = None

    def available(self) -> bool:
        return True

    def choice(self, state, instructions, options, *, name="q"):
        self.last = {"state": state, "instructions": instructions, "options": options, "name": name}
        raise DeciderUnavailable("recording only")


class FreezingRestorer(Restorer):
    """The production restorer with a larger LLM output budget and a hook that keeps the decider request."""

    def __init__(self, **kw):
        self.recorder = _Recorder()
        super().__init__(decider=self.recorder, **kw)
        self.frozen: dict[str, Any] | None = None

    def propose_fills(self, role, left, right, gap_chars, parallels, hints, k):
        if self.llm is None:
            return []
        prompt = propose_prompt(left, right, gap_chars,
                                [{"inscription_id": p.inscription_id, "line_n": p.line_n, "snippet": p.snippet,
                                  "fill": p.fill} for p in parallels], [h.to_api() for h in hints], k)
        r = self.llm.complete(role, RESTORER_SYSTEM, prompt, max_tokens=PROPOSE_MAX_TOKENS)
        return [(normalize_iso(t), c) for t, c in parse_candidates(r.text) if normalize_iso(t)]

    def rank_and_decide(self, cands: list[Candidate], **kw):
        self.recorder.last = None
        order = list(cands)
        tag, ranked = super().rank_and_decide(cands, **kw)
        top = order[:23]
        self.frozen = {
            "request": self.recorder.last,
            "fills": [c.text for c in top],
            "sources": [sorted(c.sources) for c in top],
            "llm_confidence": [c.llm_confidence for c in top],
            "fallback_confidence": [c.confidence for c in top],
            "fallback_tag": tag,
        }
        return tag, ranked


def freeze(args) -> int:
    from ..agent.data import data_source, load_items
    from ..agent.llm import BedrockLLM

    if not live_enabled():
        print("freeze calls Bedrock (Sonnet 4.6): set EZHUTHU_LIVE=1", file=sys.stderr)
        return 2
    llm = BedrockLLM()
    r = FreezingRestorer(llm=llm, use_ontology=not args.no_ontology)
    src = data_source()
    items = load_items(args.split, subset=args.subset, limit=args.limit, src=src)
    out = Path(args.out)
    done = {json.loads(ln)["id"] for ln in out.read_text().splitlines() if ln.strip()} if out.exists() else set()
    with out.open("a", encoding="utf-8") as fh:
        for it in items:
            if it.id in done:
                continue
            rec: dict[str, Any] = {"id": it.id, "target": it.target, "gap_chars": it.gap_chars, "hard": it.hard,
                                   "age_set": it.age_set, "inscription_id": it.inscription_id}
            for attempt in range(3):
                try:
                    t0 = time.perf_counter()
                    r.frozen = None
                    r.restore_gap(it.left, it.right, it.gap_chars, router="sonnet", max_candidates=23,
                                  exclude_inscription=it.inscription_id, dynasty=it.dynasty)
                    rec.update(r.frozen or {"request": None, "fills": []})
                    rec["candidate_latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
                    rec.pop("error", None)
                    break
                except Exception as exc:  # noqa: BLE001 - throttling etc.: retry, then record the error
                    rec["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
                    log.warning("freeze %s attempt %d: %s", it.id, attempt + 1, rec["error"])
                    time.sleep(5 * (attempt + 1))
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
    meta = {"split": args.split, "subset": args.subset, "limit": args.limit, "data_dir": str(src.path),
            "router": "sonnet", "llm": llm.config.model_id("default"), "use_ontology": not args.no_ontology,
            "propose_max_tokens": PROPOSE_MAX_TOKENS, "usage": llm.ledger.to_dict()}
    Path(str(out) + ".meta.json").write_text(json.dumps(meta, indent=1))
    print(json.dumps(meta))
    return 0


def read_jsonl(p: str | Path) -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in Path(p).read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------------------------------------------------------------- score --------------------------------------
@dataclass
class ItemScore:
    id: str
    target: str
    top1: str | None
    confidence: float
    correct: bool
    abstained: bool
    oracle: bool  # target is among the candidates
    latency_ms: float | None
    server_latency_ms: float | None
    choice: str | None
    error: str | None = None
    options_sent: int | None = None  # candidates the decider saw (fewer than len(fills) when trimmed to fit)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def score_item(rec: dict[str, Any], decider: Decider | None, abstain_below: float,
               slept: list[float] | None = None, fit_chars: int | None = None) -> ItemScore:
    fills = rec.get("fills") or []
    oracle = any(canon(f) == canon(rec["target"]) for f in fills)
    if not fills or not rec.get("request"):
        return ItemScore(rec["id"], rec["target"], None, 0.0, False, True, oracle, None, None, None,
                         rec.get("error") or "no candidates")
    if decider is None:  # LLM self-confidence fallback, exactly as rank_and_decide's fallback ranks
        confs = [float(c) for c in rec["fallback_confidence"]]
        lat = srv = None
        choice, err = None, None
    else:
        req = rec["request"]
        n0 = sum(slept) if slept is not None else 0.0
        t0 = time.perf_counter()
        try:
            opts = req["options"]
            if fit_chars:
                opts = fit_choice(req["state"], req["instructions"], opts, req["name"], fit_chars)[
                    "questions"][req["name"]]["criteria"]
            res = decider.choice(req["state"], req["instructions"], opts, name=req["name"])
        except DeciderUnavailable as exc:
            return ItemScore(rec["id"], rec["target"], None, 0.0, False, True, oracle, None, None, None, str(exc))
        lat = (time.perf_counter() - t0) * 1000 - ((sum(slept) - n0) * 1000 if slept is not None else 0.0)
        srv = res.latency_ms
        confs = [res.probabilities.get(f"c{i}", 0.0) for i in range(len(fills))]
        choice, err = res.choice, None
        n_opts = sum(1 for k in opts if k != "none") - (getattr(decider, "last_trimmed", 0) or 0)
    best = max(range(len(fills)), key=lambda i: confs[i])
    conf = confs[best]
    return ItemScore(rec["id"], rec["target"], fills[best], round(conf, 4),
                     canon(fills[best]) == canon(rec["target"]), conf < abstain_below, oracle,
                     None if lat is None else round(lat, 1), srv, choice, err,
                     None if decider is None else n_opts)


def make_decider(spec: str, slept: list[float]) -> tuple[Decider | None, str]:
    """``local=<url>`` | ``hosted`` | ``fallback``; returns (decider, model id)."""

    def sleep(s: float) -> None:
        slept.append(s)
        time.sleep(s)

    if spec == "fallback":
        return None, "fallback:llm-self-report"
    if spec == "hosted":
        d = hosted_decider(sleep=sleep)
        if not d.available():
            raise SystemExit(f"hosted decider {d.base_url} / {d.model} not available (key or model missing)")
        return d, d.model
    if spec.startswith("local="):
        d = HttpDecider(spec.split("=", 1)[1], timeout=120)
        h = d.health()
        if not h:
            raise SystemExit(f"local decider {d.base_url} not reachable")
        return d, h.get("checkpoint") or h.get("model")
    raise SystemExit(f"unknown decider spec {spec!r}")


def cache_dir() -> Path:
    p = (repo_root() or Path.cwd()) / ".cache" / "decider-bench"
    p.mkdir(parents=True, exist_ok=True)
    return p


def score(args) -> int:
    recs = read_jsonl(args.cands)
    if args.limit:
        recs = recs[: args.limit]
    slept: list[float] = []
    decider, model = make_decider(args.decider, slept)
    abstain_below = load_models_config().routing.abstain_if_confidence_below
    out = cache_dir() / f"restoration-{args.label}.jsonl"
    done = {r["id"]: r for r in read_jsonl(out)} if out.exists() and not args.fresh else {}
    rows = []
    with out.open("a" if done else "w", encoding="utf-8") as fh:
        for rec in recs:
            if rec["id"] in done and not done[rec["id"]].get("error"):
                rows.append(done[rec["id"]])
                continue
            s = score_item(rec, decider, abstain_below, slept, args.fit_chars)
            row = {**s.to_dict(), "decider_model": model, "decider_spec": args.decider.split("=")[0],
                   "n_candidates": len(rec.get("fills") or []), "fit_chars": args.fit_chars}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            rows.append(row)
    hdr = getattr(decider, "last_headers", {}) if isinstance(decider, HostedDecider) else {}
    print(json.dumps({"label": args.label, "model": model, **summarize(rows),
                      "ratelimit_headers": {k: v for k, v in hdr.items() if "ratelimit" in k or "remaining" in k}}))
    return 0


def pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * q
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return round(xs[f] + (xs[c] - xs[f]) * (k - f), 1)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if not n:
        return {"n": 0}
    ok = [bool(r["correct"]) for r in rows]
    conf = [float(r["confidence"]) for r in rows]
    filled = [r for r in rows if not r["abstained"]]
    lats = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    return {
        "n": n, "errors": sum(1 for r in rows if r.get("error")),
        "top1": round(sum(ok) / n, 4),
        "oracle_in_candidates": round(sum(r["oracle"] for r in rows) / n, 4),
        "top1_given_oracle": round(sum(r["correct"] for r in rows if r["oracle"])
                                   / max(1, sum(r["oracle"] for r in rows)), 4),
        "ece": round(ece(conf, ok), 4),
        "mean_confidence": round(statistics.mean(conf), 4),
        "abstain_rate": round(1 - len(filled) / n, 4),
        "coverage": round(len(filled) / n, 4),
        "selective_accuracy": round(sum(r["correct"] for r in filled) / len(filled), 4) if filled else None,
        "selective_n": len(filled),
        "latency_ms_p50": pct(lats, 0.5), "latency_ms_p95": pct(lats, 0.95), "latency_n": len(lats),
        "items_trimmed": sum(1 for r in rows if r.get("options_sent") is not None
                             and r["options_sent"] < r.get("n_candidates", 0)),
        "coverage_curve": coverage_curve(conf, ok, CURVE),
        "reliability": reliability(conf, ok),
    }


# ---------------------------------------------------------------- policy -------------------------------------
def scripted_states() -> list[dict[str, Any]]:
    """20 learner states in the shape TutorService builds after an answer."""
    S = []

    def st(item_type, level, correct, cer, attempts, hint, secs, recent, remaining):
        S.append({"item_type": item_type, "script_level": level, "correct": correct, "character_error_rate": cer,
                  "attempts_on_item": attempts, "hint_already_given": hint, "seconds_on_item": secs,
                  "recent_accuracy": recent, "items_remaining": remaining})

    st("letter", "L1", True, 0.0, 1, False, 4.0, 1.0, 8)
    st("letter", "L4", True, 0.0, 2, True, 21.0, 0.6, 5)
    st("word", "L2", True, 0.0, 1, False, 9.5, 0.8, 3)
    st("line", "L5", True, 0.0, 3, True, 60.0, 0.4, 1)
    st("letter", "L3", True, 0.0, 1, False, 2.1, None, 9)
    st("letter", "L1", False, 1.0, 1, False, 6.0, 0.8, 7)
    st("letter", "L4", False, 1.0, 1, False, 15.0, 0.2, 6)
    st("word", "L2", False, 0.25, 1, False, 12.0, 0.6, 4)
    st("line", "L3", False, 0.4, 1, False, 48.0, 0.5, 2)
    st("letter", "L5", False, 1.0, 1, False, 30.0, None, 10)
    st("letter", "L4", False, 1.0, 2, True, 25.0, 0.4, 6)
    st("word", "L3", False, 0.5, 2, True, 40.0, 0.2, 3)
    st("letter", "L2", False, 0.0, 2, True, 8.0, 0.8, 5)
    st("line", "L4", False, 0.2, 2, True, 70.0, 0.6, 1)
    st("letter", "L1", False, 1.0, 2, False, 7.0, 0.6, 8)
    st("letter", "L5", False, 1.0, 3, True, 35.0, 0.0, 4)
    st("word", "L4", False, 0.6, 3, True, 55.0, 0.2, 2)
    st("letter", "L3", False, 1.0, 3, False, 20.0, 0.4, 7)
    st("line", "L5", False, 0.8, 4, True, 90.0, 0.0, 0)
    st("word", "L1", False, 0.1, 1, False, 5.0, 1.0, 6)
    return S


def run_policy(args) -> int:
    slept: list[float] = []
    decider, model = make_decider(args.decider, slept)
    if decider is None:
        model = "rules"
    rows = []
    for i, state in enumerate(scripted_states()):
        ref = policy.rules(state["correct"], state["attempts_on_item"], state["hint_already_given"])
        raw = conf = lat = None
        t0 = time.perf_counter()
        n0 = sum(slept)
        if decider is None:
            d = policy.decide(NoDecider(), state)
        else:
            try:
                res = decider.choice(state, policy.INSTRUCTIONS, policy.ACTIONS, name="pedagogy")
                raw, conf = res.choice, round(res.confidence, 4)
                lat = round((time.perf_counter() - t0 - (sum(slept) - n0)) * 1000, 1)
            except DeciderUnavailable as exc:
                raw = f"error: {exc}"
            d = policy.decide(_Replay(res) if raw and not raw.startswith("error") else NoDecider(), state)
        rows.append({"i": i, "state": state, "rules_reference": ref, "decider_raw": raw, "decider_confidence": conf,
                     "final": d.action, "overridden": d.overridden, "backend": d.backend, "latency_ms": lat,
                     "decider_model": model})
    out = cache_dir() / f"policy-{args.label}.jsonl"
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps({"label": args.label, **policy_summary(rows)}))
    return 0


class _Replay:
    """Feeds an already-fetched decider answer to ``policy.decide`` so the decider is called once per state."""

    def __init__(self, res):
        self.res = res

    def choice(self, *a, **k):
        return self.res


def policy_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    raw_ok = [r for r in rows if r["decider_raw"] and not str(r["decider_raw"]).startswith("error")]
    lats = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    dist: dict[str, int] = {}
    for r in raw_ok:
        dist[r["decider_raw"]] = dist.get(r["decider_raw"], 0) + 1
    return {"n": n, "errors": n - len(raw_ok) if rows and rows[0]["backend"] != "rules" else 0,
            "raw_agree_with_rules": round(sum(r["decider_raw"] == r["rules_reference"] for r in raw_ok)
                                          / max(1, len(raw_ok)), 4) if raw_ok else None,
            "final_agree_with_rules": round(sum(r["final"] == r["rules_reference"] for r in rows) / n, 4),
            "guardrail_overrides": sum(r["overridden"] for r in rows), "raw_distribution": dist,
            "latency_ms_p50": pct(lats, 0.5), "latency_ms_p95": pct(lats, 0.95)}


# ---------------------------------------------------------------- report -------------------------------------
def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar p-value for b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(a: list[dict[str, Any]], b: list[dict[str, Any]]) -> dict[str, Any]:
    """Paired comparison on the items both labels scored: right/wrong agreement, McNemar, and pick agreement."""
    ra, rb = {r["id"]: r for r in a}, {r["id"]: r for r in b}
    common = [i for i in ra if i in rb]
    only_a = sum(1 for i in common if ra[i]["correct"] and not rb[i]["correct"])
    only_b = sum(1 for i in common if rb[i]["correct"] and not ra[i]["correct"])
    diff = [i for i in common if canon(ra[i]["top1"] or "") != canon(rb[i]["top1"] or "")]
    return {"n": len(common), "both_correct": sum(1 for i in common if ra[i]["correct"] and rb[i]["correct"]),
            "only_a_correct": only_a, "only_b_correct": only_b,
            "mcnemar_p": round(mcnemar_exact(only_a, only_b), 4),
            "same_correctness_every_item": only_a == only_b == 0,
            "different_pick": len(diff), "different_pick_ids": diff}


def report(args) -> int:
    recs = read_jsonl(args.cands)
    meta_p = Path(str(args.cands) + ".meta.json")
    cmeta = json.loads(meta_p.read_text()) if meta_p.exists() else {}
    labels = [x for x in args.labels.split(",") if x]
    ids = [r["id"] for r in recs]
    stem = Path(args.out) if args.out else (repo_root() or Path.cwd()) / "eval" / "reports" / \
        f"{dt.date.today().isoformat()}-decider-benchmark"
    rows_dir = Path(args.rows_dir) if getattr(args, "rows_dir", None) else stem
    rows_dir.mkdir(parents=True, exist_ok=True)
    if getattr(args, "sync_from_cache", False):
        for lb in labels:
            for kind in ("restoration", "policy"):
                src = cache_dir() / f"{kind}-{lb}.jsonl"
                if src.exists():
                    shutil.copyfile(src, rows_dir / src.name)
    res, pol, byl = {}, {}, {}
    for lb in labels:
        p = rows_dir / f"restoration-{lb}.jsonl"
        if p.exists():
            byid = {r["id"]: r for r in read_jsonl(p)}  # last write wins
            rows = [byid[i] for i in ids if i in byid]
            byl[lb] = rows
            res[lb] = {"model": rows[0]["decider_model"] if rows else None, **summarize(rows),
                       "complete": len(rows) == len(ids), "rows_file": str(p.relative_to(stem.parent))
                       if p.is_relative_to(stem.parent) else str(p)}
        pp = rows_dir / f"policy-{lb}.jsonl"
        if pp.exists():
            prow = read_jsonl(pp)
            pol[lb] = {"model": prow[0]["decider_model"], **policy_summary(prow),
                       "actions": [r["decider_raw"] for r in prow], "final": [r["final"] for r in prow]}
    pairs = {f"{a} vs {b}": compare(byl[a], byl[b])
             for i, a in enumerate(labels) for b in labels[i + 1:] if a in byl and b in byl}
    import hashlib

    cfg = load_models_config()
    limit = ((cfg.decider or {}).get("cloud") or {}).get("max_input_chars")
    # The same count decider-cloud's gateway applies to max_input_chars (request_chars).
    sizes = [request_chars(choice_payload(r["request"]["state"], r["request"]["instructions"],
                                          r["request"]["options"], r["request"]["name"]))
             for r in recs if r.get("request")]
    abstain_below = cfg.routing.abstain_if_confidence_below
    out = {
        "meta": {"date": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"), "task": "restoration rank_and_decide",
                 "candidates_file": str(args.cands),
                 "candidates_sha256": hashlib.sha256(Path(args.cands).read_bytes()).hexdigest(),
                 "candidate_generation": cmeta, "n_items": len(recs),
                 "items_with_candidates": sum(1 for r in recs if r.get("fills")),
                 "mean_candidates": round(statistics.mean(len(r.get("fills") or []) for r in recs), 2),
                 "request_chars_json_ascii": {"median": pct(sizes, 0.5), "p95": pct(sizes, 0.95),
                                              "max": max(sizes) if sizes else None, "limit": limit,
                                              "over_limit": sum(1 for x in sizes if limit and x > limit),
                                              "n": len(sizes)},
                 "abstain_threshold": abstain_below, "notes": args.note or [],
                 "rows_dir": str(rows_dir.relative_to(stem.parent)) if rows_dir.is_relative_to(stem.parent)
                 else str(rows_dir)},
        "restoration": res, "pairwise": pairs, "policy": pol,
        "policy_states": scripted_states(),
    }
    stem.parent.mkdir(parents=True, exist_ok=True)
    stem.with_suffix(".json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    stem.with_suffix(".md").write_text(render_md(out, labels), encoding="utf-8")
    print(stem.with_suffix(".md"))
    return 0


def _f(x: Any) -> str:
    if isinstance(x, float):
        return f"{x:.3f}" if abs(x) <= 1.5 else f"{x:.0f}"
    return "-" if x is None else str(x)


def render_md(out: dict[str, Any], labels: list[str]) -> str:
    m = out["meta"]
    L = ["# Decider benchmark: hosted vs local Strands Decider vs LLM self-confidence", "",
         f"- Date: {m['date']}", (f"- Task: restoration `rank_and_decide` on {m['n_items']} items "
         f"({m['candidate_generation'].get('split', '?')}/{m['candidate_generation'].get('subset', '?')}, first "
         f"{m['candidate_generation'].get('limit', '?')}), one fixed candidate set for every decider "
         f"(`{Path(m['candidates_file']).name}`, sha256 `{m['candidates_sha256'][:12]}`)."),
         (f"- Candidates: {m['candidate_generation'].get('llm', '?')} (router `sonnet`, no escalation) + retrieval "
         f"parallels + character n-gram; ontology {'on' if m['candidate_generation'].get('use_ontology') else 'off'}; "
         f"{m['items_with_candidates']} items have candidates, mean {m['mean_candidates']} candidates per item."),
         f"- Abstain threshold: confidence < {m['abstain_threshold']} (`routing.abstain_if_confidence_below`).",
         (f"- Decider request size (state + questions incl. instructions, JSON with ASCII escapes, as decider-cloud "
         f"counts it): median {m['request_chars_json_ascii']['median']}, p95 {m['request_chars_json_ascii']['p95']}, "
         f"max {m['request_chars_json_ascii']['max']} characters; {m['request_chars_json_ascii'].get('over_limit')} of "
         f"{m['request_chars_json_ascii'].get('n')} over the {m['request_chars_json_ascii'].get('limit')}-character "
         f"free-tier limit."),
         (f"- Per-item rows: `{Path(m.get('rows_dir', '')).name}/` next to this report (restoration-<label>.jsonl, "
          "policy-<label>.jsonl)."), "",
         "## Restoration (same items, same candidates)", "",
         ("| decider | model | N | errors | top-1 | top-1 when target is a candidate | ECE | abstain rate | "
         "selective accuracy (n) | latency p50 / p95 ms |"), "|---|---|---|---|---|---|---|---|---|---|"]
    for lb in labels:
        r = out["restoration"].get(lb)
        if not r:
            L.append(f"| {lb} | not run | | | | | | | | |")
            continue
        L.append(f"| {lb} | `{r['model']}` | {r['n']}{'' if r['complete'] else ' (partial)'} | {r['errors']} | "
                 f"{_f(r['top1'])} | {_f(r['top1_given_oracle'])} | {_f(r['ece'])} | {_f(r['abstain_rate'])} | "
                 f"{_f(r['selective_accuracy'])} ({r['selective_n']}) | {_f(r['latency_ms_p50'])} / "
                 f"{_f(r['latency_ms_p95'])} |")
    any_r = next(iter(out["restoration"].values()), None)
    if any_r:
        L += ["", f"Target among the candidates (ceiling for any decider): {_f(any_r['oracle_in_candidates'])}.", "",
              "Coverage / accuracy if the abstain threshold were moved (confidence >= t):", "",
              "| decider | " + " | ".join(f"t={t}" for t in CURVE) + " |", "|---|" + "---|" * len(CURVE)]
        for lb in labels:
            r = out["restoration"].get(lb)
            if r:
                L.append(f"| {lb} | " + " | ".join(f"{_f(c['coverage'])} / {_f(c['accuracy'])}"
                                                   for c in r["coverage_curve"]) + " |")
    if out.get("pairwise"):
        L += ["", ("Paired comparison on the items both scored (exact McNemar on the discordant items; "
                   "*different pick* counts items where the chosen fill differs, right or wrong):"), "",
              "| pair | N | both right | only first right | only second right | McNemar p | different pick |",
              "|---|---|---|---|---|---|---|"]
        for k, c in out["pairwise"].items():
            L.append(f"| {k} | {c['n']} | {c['both_correct']} | {c['only_a_correct']} | {c['only_b_correct']} | "
                     f"{c['mcnemar_p']:.3f} | {c['different_pick']} |")
    L += ["", "## Tutor policy (20 scripted learner states)", "",
          ("Reference = the rule policy (`tutor/policy.py rules`). *Raw* is the decider's choice before guardrails; "
          "*final* is after the guardrails (never drill a correct item, never loop past 3 attempts)."), "",
          ("| decider | model | raw agrees with rules | final agrees with rules | guardrail overrides | raw choices | "
          "latency p50 / p95 ms |"), "|---|---|---|---|---|---|---|"]
    for lb in labels:
        p = out["policy"].get(lb)
        if not p:
            L.append(f"| {lb} | not run | | | | | |")
            continue
        L.append(f"| {lb} | `{p['model']}` | {_f(p['raw_agree_with_rules'])} | {_f(p['final_agree_with_rules'])} | "
                 f"{p['guardrail_overrides']} | {p['raw_distribution']} | {_f(p['latency_ms_p50'])} / "
                 f"{_f(p['latency_ms_p95'])} |")
    if out["policy"]:
        L += ["", "Per state (rules reference / raw choice per decider):", "",
              "| # | correct | attempts | hint given | rules | " + " | ".join(lb for lb in labels if lb in out["policy"])
              + " |", "|---|---|---|---|---|" + "---|" * sum(lb in out["policy"] for lb in labels)]
        for i, s in enumerate(out["policy_states"]):
            ref = policy.rules(s["correct"], s["attempts_on_item"], s["hint_already_given"])
            cells = [str(out["policy"][lb]["actions"][i] or f"({out['policy'][lb]['final'][i]})")
                     for lb in labels if lb in out["policy"]]
            L.append(f"| {i} | {s['correct']} | {s['attempts_on_item']} | {s['hint_already_given']} | {ref} | "
                     + " | ".join(cells) + " |")
    if m["notes"]:
        L += ["", "## Caveats", ""] + [f"- {n}" for n in m["notes"]]
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("--split", default="test")
    f.add_argument("--subset", default="hard")
    f.add_argument("--limit", type=int, default=60)
    f.add_argument("--no-ontology", action="store_true")
    f.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--cands", required=True)
    s.add_argument("--decider", required=True, help="local=<url> | hosted | fallback")
    s.add_argument("--label", required=True)
    s.add_argument("--limit", type=int, default=None)
    s.add_argument("--fresh", action="store_true")
    s.add_argument("--fit-chars", type=int, default=None,
                   help="drop tail candidates so the request fits this many characters (hosted free tier: 8000)")
    p = sub.add_parser("policy")
    p.add_argument("--decider", required=True)
    p.add_argument("--label", required=True)
    r = sub.add_parser("report")
    r.add_argument("--cands", required=True)
    r.add_argument("--labels", required=True)
    r.add_argument("--out", default=None)
    r.add_argument("--rows-dir", default=None, help="per-item rows (default: <out>/ next to the report)")
    r.add_argument("--sync-from-cache", action="store_true",
                   help="copy restoration-/policy-<label>.jsonl from .cache/decider-bench into the rows dir first")
    r.add_argument("--note", action="append")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return {"freeze": freeze, "score": score, "policy": run_policy, "report": report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
