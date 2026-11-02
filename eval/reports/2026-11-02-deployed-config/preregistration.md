# Deployed restorer configuration: pre-registration (written before any VAL scoring)

Committed before any of the variants below was scored. The code that implements it is
`src/ezhuthu/eval/deploy_config.py` (`VARIANTS`, `RULE`) at the same commit.

## What the cloud runtime runs today (before this issue)

`config/models.yaml` `restorer:` ships `strategy: self-report` (retrieval-only gaps) and `strategy_llm: noul-topk`,
`top_k: 3` (once an LLM answered). The AgentCore runtime sets `EZHUTHU_DECIDER_BACKEND=hosted` when Secrets Manager
`ezhuthu/decider-api-key` exists at deploy time (it now does), else `fallback`. So:

- with the key: routed Sonnet 4.6 -> Opus 4.6, then the hosted v19 decider's `noul` on each of the top 3 candidates
  (3 hosted calls per ranking, up to 6 per gap when Sonnet's answer escalates);
- without it: `noul-topk` raises `DeciderUnavailable` and falls back to the LLM's self-reported probability.

Neither has a calibration entry (`calibration.json` has only 2B-decider, prerank and retrieval-heuristic keys), so
both fill or abstain at the raw 0.5 threshold, and neither has been measured. The hosted free tier allows 10 decider
requests a minute and the client paces at that rate (one call every 6 s), so `noul-topk:3` alone needs at least
12 s of pacing per ranking (24 s+ for an escalated gap, before any LLM latency): it cannot fit the proxy's 27 s
per-request limit, which is why the hosted variant below is `choice-topk:3` (one hosted call per ranking).

## Items

- **Selection set (VAL, 280 items):** the issue #26 seeded VAL sample (120 items, seed 26) plus 160 more VAL items
  drawn with seed 26 from the other 323. Full VAL (443) needs about 340 new Bedrock calls for the routed variants
  (248 Opus replies for gaps that pre-escalate are not cached), over this issue's 300-call budget, which also has to
  cover TEST; 280 is the largest nested sample whose worst case (about 200 calls) leaves room for TEST.
- **Hosted set (VAL, 120 items):** the issue #26 seeded VAL sample (a subset of the selection set; every Sonnet and
  Opus reply it needs is cached, so it costs hosted-decider calls only).
- The 5-gram baseline is also reported on full VAL (443).

## Variants

All use config/models.yaml as shipped (models, routing thresholds 0.6 / 12 letters / no-parallel, ontology on,
`top_k` 3, `ngram_k` 3) unless stated. Retrieval-only gaps (an LLM call failed) use `self-report` in every variant.

| id | variant | what changes |
|---|---|---|
| a | `ngram` | character 5-gram baseline only (beam 20); fills when its softmax share >= 0.9103 (issue #26 full-VAL threshold) |
| b1 | `hybrid-gate` | 5-gram gate: when the 5-gram top fill's share >= 0.9103 and it passes the letter constraints, fill it with no LLM call; otherwise exactly `routed-prerank` |
| b2 | `hybrid-prerank` | routed, `prerank` with the 5-gram share as a third noisy-OR term (no hand-set weight) |
| c | `routed-prerank` | routed, `prerank` (LLM probability noisy-OR parallel support), no decider |
| d | `routed-hosted-v19` | routed, hosted v19 `choice-topk:3` over the b2 pre-rank; the 5-gram top fill always gets one of the 3 slots (as the copy-baseline fill does); the decider sees each option's 5-gram share |
| e | `routed-selfreport` | routed, LLM self-reported probability (the runtime without a decider) |

b1 and b2 are the two hybrid designs; neither has a parameter fitted on these runs.

## Selection rule

Stage 1: on the same VAL items (the 280-item selection set), the decider-free variant (a, b1, b2, c, e) with the
most top-1 matches wins; a tie in matches goes to the lower estimated USD per gap, then the lower p50 latency.
Stage 2: the hosted-v19 variant (d) replaces the stage-1 winner only if it has strictly more top-1 matches on the
120-item hosted set; otherwise the decider-free winner (cheaper, faster, no external dependency) stands.
No escalation threshold, n-gram threshold or strategy parameter is re-tuned.

## Also reported per variant (not part of the rule)

Top-1 with a bootstrap CI, McNemar vs the 5-gram, top-20, CER, estimated USD per gap (list prices), LLM calls,
latency per gap (p50/p90/max and gaps over 27 s), and coverage / selective accuracy at VAL-fitted abstain thresholds
(Platt + threshold per calibration key, the keys the runtime looks up; in-sample and 5-fold out-of-fold).

## After the choice

1. Fit the chosen configuration's calibration entries on VAL (n >= 100 per key, or the key stays raw), under the
   keys the runtime looks up; `|llm-sonnet` keys from a Sonnet-only run of the same variant on the selection set
   (as in issue #26), the others from the routed run.
2. Set `config/models.yaml` to the chosen configuration for both runtime paths (with and without the decider key).
3. Score it once on TEST (413), reusing PR #31's cached replies; bootstrap CI and McNemar vs copy, the 5-gram and
   PR #31's routed row.
