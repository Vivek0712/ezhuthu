# Dev-set note: restorer quality fixes (issue #22)

> **Development measurements on the VAL split and local profiling only.** Nothing here is a test-set result, and
> none of it may be cited as restoration quality. N is small for the live (LLM) runs, and their items are
> correlated (the first VAL items come from two inscriptions).

Per-run reports (all re-derivable from the JSON next to them):

- `2026-11-02-restorer-val-calibration-retrieval.{md,json}`: all 443 VAL items, router `none` (retrieval + copy floor +
  5-gram, no LLM), local `strands-decider-2B-qwen3.5-v1-2610`, ontology off. 0 Bedrock calls. Writes the
  `...|retrieval` calibration entries.
- `2026-11-02-restorer-val-live-sonnet.{md,json}`: first 20 VAL items, router `sonnet` (Sonnet 4.6), same decider,
  ontology off. Writes the provisional `...|llm` calibration entries.
- `2026-11-02-restorer-val-routed-sanity.{md,json}`: first 6 VAL items, router `routed` (exercises Opus 4.6), no
  decider (cloud-like), no calibration.

Ontology is off in every eval run: the shipped ontology build reads val/test inscriptions (QA gotcha), so it would
leak. The retrieval corpus (`benchmark/corpus_lines.jsonl`) contains no VAL or test inscription (checked: 0 of the
VAL inscription ids occur in it).

## 1. Truncation (`propose_fills`)

| run | LLM calls | replies cut at max_tokens | stricter retries |
|---|---|---|---|
| before: quick live eval, test-hard first 30, `max_tokens=800` (sonnet / routed) | - | 6/30 items / 18/30 items (`MaxTokensReachedException`, item lost) | - |
| after: VAL first 20, router sonnet | 20 (Sonnet) | 0 | 0 |
| after: VAL first 6, router routed | 6 (Opus) + 1 cached Sonnet | 0 | 0 |

The fix: the reply is one line of JSON with only `[fill, probability]` pairs and no reasoning; the output budget
scales with candidates x gap length (cap 2,048); a reply that is still cut keeps every complete fill (partial-JSON
parser) and is re-asked once with a stricter, shorter prompt. Opus replies averaged 119 output tokens (712 over
6 calls). Different items from the "before" row (VAL, not test-hard), so this shows the failure is gone on these
calls, not a rate comparison.

## 2. Throttling

No throttling occurred in these runs (rate limiter at 20 calls/min, one worker), so the backoff path is covered by
unit tests only (`tests/agent/test_restorer_quality.py`: full-jitter delays, retry on throttling codes only, rate
limiter spacing, Strands' lockstep retry disabled).

## 3. Copy floor and 4. decider variants (full VAL, retrieval candidates, n = 443)

Copy baseline on the same items: top-1 **0.228**.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-all | 0.1648 | 0.3499 | 18 / 46 | 0.2648 / 0.617 | 0.1 | 0.031 | 0.0181 / 0.25 | 0.0 / - | 1.0 | 0 / 0 | 1025.1 |
| choice-topk:3 | 0.1874 | 0.3499 | 16 / 34 | 0.2978 / 0.6608 | 0.1105 | 0.0094 | 0.0293 / 0.1538 | 0.0 / - | 1.0 | 0 / 0 | 787.8 |
| choice-topk:5 | 0.1716 | 0.3499 | 18 / 43 | 0.2723 / 0.617 | 0.1008 | 0.0082 | 0.0158 / 0.2857 | 0.0 / - | 1.0 | 0 / 0 | 985.2 |
| noul-topk:3 | 0.2009 | 0.3499 | 12 / 24 | 0.5932 / 0.833 | 0.3931 | 0.0418 | 0.8623 / 0.2225 | 0.0271 / 0.5833 | 0.5609 | 0 / 0 | 1643.5 |
| prerank | 0.2348 | 0.3499 | 3 / 0 | 0.3619 / 1.0 | 0.1342 | 0.0514 | 0.1851 / 0.5244 | 0.1038 / 0.5435 | 0.4025 | 0 / 0 | 56.3 |
| fallback | 0.2167 | 0.3499 | 10 / 15 | 0.1827 / 0.7455 | 0.041 | 0.0229 | 0.0406 / 0.7778 | 0.0406 / 0.6111 | 0.675 | 0 / 0 | 55.7 |

On the 20 LLM items (Sonnet candidates; copy baseline 0/20, target among the candidates on 5/20):

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.2874 / 0.5334 | 0.2874 | 0.0772 | 0.05 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 877.2 |
| choice-topk:5 | 0.05 | 0.25 | 1 / 0 | 0.3019 / 0.4953 | 0.2519 | 0.092 | 0.0 / - | 0.0 / - | 1.0 | 0 / 0 | 1078.1 |
| noul-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.5725 / 0.7164 | 0.5725 | 0.1277 | 0.75 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 1790.7 |
| choice-all | 0.05 | 0.25 | 1 / 0 | 0.1886 / 0.3276 | 0.1386 | 0.0605 | 0.0 / - | 0.0 / - | 1.0 | 0 / 0 | 2110.1 |
| prerank | 0.1 | 0.25 | 2 / 0 | 0.5361 / 0.944 | 0.4417 | 0.1618 | 0.5 / 0.2 | 0.0 / - | 0.6329 | 0 / 0 | 61.7 |
| fallback | 0.15 | 0.25 | 3 / 0 | 0.496 / 0.92 | 0.354 | 0.0754 | 0.45 / 0.2222 | 0.0 / - | 0.6373 | 0 / 0 | 58.5 |

What this shows:

- **The 2B decider does not beat cheaper rankers here.** On full VAL, every decider variant (`choice-all`,
  `choice-topk` k=3/5, `noul-topk` k=3) has lower top-1 than both the pre-rank and the copy baseline, and calibration
  sets its abstain threshold to 1.0 (never fill) for the `choice` variants because no threshold had more right than
  wrong fills on VAL. Restricting the choice to the top-k raises the decider's raw top-1 probability (mean 0.265 ->
  0.298 at k=3), as expected from less spread, but not its accuracy. This matches the 2026-11-02 decider benchmark
  (2B 0.217 vs LLM self-confidence 0.400 on test-hard).
- **`prerank` is never below the copy baseline on VAL** (top-1 0.2348 vs 0.228; 3 items only prerank got right,
  0 only the copy baseline) after the copy-floor fix (the copy
  fill keeps its full parallel-match score instead of being diluted by parallel disagreement). Before that fix it was
  0.2167 with 15 items only the copy baseline got right; that run is superseded and not reported further.
- So the configured default is now `restorer.strategy: prerank` (no decider call; per-variant VAL calibration and
  threshold). The decider variants stay selectable (`EZHUTHU_RESTORER_STRATEGY`, `eval.run --strategy/--top-k`), and
  the hosted v19 decider is still unmeasured (no API key). This is a lead decision; see the PR. With LLM
  candidates (n = 20, correlated) the LLM self-report ranks 3/20 and prerank 2/20; too few items to separate them.
- Calibration helps where it can: cross-validated ECE drops for every variant, and prerank's fitted threshold (cv5)
  fills 10.4% of VAL gaps at 54% accuracy, where the raw 0.5 threshold filled 18.5% at 52%.

## 5. DynamoStore

Contract tests only (`tests/agent/test_dynamo_store.py`), against a fake that reads the key schema from
`infra/lib/data-stack.ts`. Not deployed: the runtime still has `EZHUTHU_STORE=memory` until the App team switches it
(handoff sent).

## 6. `/api/lesson` latency

Profiled in-process on an Apple M4 Pro, cloud-like settings (`EZHUTHU_LIVE=1`, `EZHUTHU_DECIDER=off`, MCP ontology,
Sonnet 4.6 for the Swarm), default lesson (`DHARMA_INSCempiyanMahadevi00001`, level L1, **0 gaps**, so no restoration
call on the path).

| | run 1 (cold) | run 2 | run 3 | p50 | explanation |
|---|---|---|---|---|---|
| before (Swarm inside the Graph) | 35.3 s | 16.1 s | - | 25.7 s (n=2) | run 1 tutor_team; run 2 Swarm returned no JSON -> template-fallback |
| after (`EZHUTHU_LESSON_EXPLAIN=async`) | 0.66 s | 0.04 s | 0.08 s | 0.08 s | template now; Swarm in background (33.1 s), then cached |

"Before" times are the Graph wall time (the rest of the request is session bookkeeping, milliseconds). The first
"before" run (35.3 s) is over the proxy's 27 s budget. After: the learner gets items at once with the template
explanation and `explanation_status: "pending"`; the Swarm's explanation arrives once as `context_update` on the next
`/api/answer`, and later lessons with the same facts get it directly. No feature is dropped: the same Swarm runs, just
off the request path; `EZHUTHU_LESSON_EXPLAIN=sync` restores the old behaviour.

Not measured live: lessons on inscriptions **with gaps** still restore on the request path (one LLM call per gap,
Opus for long gaps; 3.0-4.7 s per gap in the routed sanity run). Restored texts are now cached per process, so only
the first lesson on an inscription pays it; a long, heavily damaged inscription (VAL p90 is 11 gaps) can still exceed
27 s on a cold cache. Pre-restoring the lesson inscriptions offline is the follow-up.

## 7. Tutor confidence

`decider_source: "rules"` now always comes with `decider_confidence: null` (also when the decider answered with an
unusable choice). The app's `confidence 0%` comes from rendering `null` as 0; handed to the App team.

## Cost

Bedrock calls this wave: 20 Sonnet + 6 Opus for the eval runs (estimated $0.0906 + $0.0482, ledger list prices), plus
three tutor Swarm runs for the latency profile (not in a ledger; the Swarm calls Bedrock directly, 2-4 calls each).
Every re-scoring after the first live run replayed cached replies (0 live calls).

## QA follow-up on PR #25 (same day)

QA found that the shipped defaults (prerank + `calibration.json`) escalated and abstained on almost every LLM-on gap:
the `prerank|...|llm` entry (n=20, 2 positives, cv5 fill coverage 0.0) squashed confidences, and `restore_gap`
compared the *calibrated* top-1 with `escalate_if_confidence_below` (a raw-scale threshold). On the 20 live-Sonnet VAL
rows that meant 19/20 escalations and 1/20 fills, and a confident, correct LLM fill (p=0.85 / 0.92) was escalated and
abstained 10/10. Changes:

- **Escalation compares the raw top-1** with `routing.escalate_if_confidence_below`; the calibrated score is used only
  for fill/abstain against the variant's own threshold.
- **Minimum-sample guard**: entries with n < `restorer.calibration_min_n` (100) or positives <
  `calibration_min_positives` (10) are provisional and ignored. All n=20 `|llm` entries are therefore inert; LLM-on
  gaps use raw confidences and the 0.5 abstain threshold, as on main. The retrieval-only entries (n=443) still apply.
- **Router-aware keys**: `|llm` became `|llm-sonnet` / `|llm-opus` (Opus whenever Opus answered).
- **`prerank` only for retrieval-only gaps**: new `restorer.strategy_llm` (default `self-report`: the LLM's own
  probability, i.e. main's no-decider behaviour) once an LLM answered. Reason found while re-running QA's
  simulation on real VAL items: `[?N]` counts Tamil letters but the length check counts ISO characters, so 130/443
  VAL targets fail it and prerank halves them (a correct p=0.85 fill became 0.425 and abstained; with only the two
  fixes above, 4/10 filled). With `self-report`: QA's simulation on the first 10 VAL items (FakeLLM returns the expert
  target at p=0.85 or 0.92, router routed, shipped defaults) fills 10/10 correctly, 0 escalations after Sonnet; 8/10
  start on Opus by the unchanged pre-escalation rule (no parallel scoring >= 50), exactly as on main. Self-report also
  had the better top-1 of the two on the 20 live-Sonnet rows (0.15 vs 0.10). Counting letters in the length check
  (`text.aksharas` matches `gap_chars` on 422/443 VAL targets) is left as a separate change because it moves the
  copy baseline and every committed number.
- **What this means in practice** (honest cost note): on the same 20 live-Sonnet rows the raw self-report top-1 is
  under 0.6 on 15/20, so a routed run would still call Opus after Sonnet on about three gaps in four (5/20 no
  escalation, versus 19/20 escalations before); at raw 0.5 it fills 9/20 and 2 of those fills are right. These are 20
  items from 2 inscriptions where Sonnet's top-1 was right 3/20, so the escalations are mostly warranted, but the cost
  and latency of Opus on most hard gaps is real. A routed eval on more VAL items (budgeted) is needed before tuning 0.6.
- New end-to-end test (`tests/agent/test_restorer_defaults.py`): `Restorer(llm=FakeLLM)` with no env overrides, the
  shipped `config/models.yaml` and `calibration.json`, and a FakeLLM returning the correct fill at p=0.85 and 0.92
  fills every gap with one LLM call and never escalates without a pre-escalation reason; a second test covers a
  correct fill that is 5 letters but 9 ISO characters. A copy-floor test now fails if the copy-floor line in
  `prerank_score` is removed.
- Report provenance: the three report files now name the last data commit (20584c8) and the code commit separately;
  the prerank/fallback rows of the two calibration reports were replayed at 575f3ab (0 Bedrock calls) and reproduced
  exactly. The routed-sanity report predates 585bbad; its replay matches top-1/top-20/abstain but not CER (see its note).
