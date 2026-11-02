# Restore request budget, gap cap and 5-gram warm-up (issue #41)

Raw rows: `eval/reports/2026-11-02-request-budget.json` (`python -m ezhuthu.eval.request_budget`, VAL split only;
TEST was not used). Settings measured: the shipped `config/models.yaml` `restorer:` values,
`request_budget_s` 25, `escalate_min_remaining_s` 8, `llm_min_remaining_s` 6, `gap_min_remaining_s` 1,
`max_gaps_per_request` 8.

## Summary

- **Before (no budget, the pre-#41 code path):** three VAL requests with 7, 5 and 5 gaps took **30.8 s, 49.6 s and
  58.4 s** of wall time with live Bedrock calls. All three exceed the proxy's 27 s (API Gateway: 29 s), so all three
  would have failed in the deployed app.
- **After (shipped budget):** the same requests took **20.9 s, 25.0 s and 25.0 s**. Of the 17 gaps, 13 were
  restored exactly as before. 4 gaps abstained with no work (`abstain_reason: time_budget`), and 3 gaps had no LLM answer because
  the call ran out of time (`llm_skipped: time_budget`; retrieval and 5-gram candidates were kept).
- **Unconstrained gaps are unchanged:** on every gap that the budget did not touch, the decision, chosen fill and
  top-1 are identical before and after (13/13). So the number of fills that match the editors' restoration on those
  gaps is also unchanged. A unit test (`tests/agent/test_restore_budget.py::test_unconstrained_budget_leaves_results_identical`)
  shows the same for a request inside the budget: identical gaps, candidates, confidences and LLM prompts.
- **Warm-up:** the runtime now builds the parallel index (0.16 s) and the character 5-gram (0.95 s) on start, in a
  background thread. These are local figures from an Apple M4 Pro; the deployed-config report measured 5.8 s for
  the 5-gram on a cold AgentCore runtime. Offline (no LLM), the first 7-gap request took 1.74 s cold and 0.54 s
  warm.

## Method

Each request is one VAL benchmark item's context, as a learner would send it. The item's own gap is masked, and so
is every other supplied span on the line (`[?N]` or `[?]`), so one request carries several gaps. The items were
picked from VAL by gap count (4-8 gaps, < 2000 characters, distinct inscriptions), not by result:
`DHARMA_INSCirkali00013:2:2` (7 gaps), `DHARMA_INSKotumpalur00038:2:0` (5),
`DHARMA_INStfaSIIv04p0i0163:4:3` (5). The 7-gap request is above the API's `EZHUTHU_MAX_GAPS` (5) and would be
refused with 400. It is kept here because the tutor calls `restore()` directly on whole inscriptions.

- **before:** a fresh `Restorer` with `request_budget_s: null, max_gaps_per_request: null` (the code path is
  identical to main), with live Bedrock calls (`EZHUTHU_LIVE=1`, profile heisenberg) and an empty LLM cache. The
  first request also paid the index and 5-gram build (about 1.1 s locally).
- **after:** a fresh `Restorer` with the shipped settings, warmed first. Its LLM replies were replayed from the
  before run's cache. Each reply was returned after sleeping its original latency. A reply slower than the call's
  timeout (the time left in the budget) slept the timeout and then raised `TimeoutError`, as Bedrock's read timeout
  would. No prompt missed the cache, so the after run made no new calls.
- Live calls: **17** in all (1 Sonnet 4.6, 16 Opus 4.6; most gaps pre-escalate because the short contexts have no
  good parallel), under the cap of 30. One call was throttled once and retried. Opus latency in this run was
  2.6-16.7 s per call, slower than in the deployed-config report (p50 3.1 s, p90 6.2 s). The before figures therefore
  show today's Bedrock latency, not a typical day's.

## Per request

| request | gaps | before wall s | after wall s | abstained (time_budget) | LLM cut by budget | gaps identical |
|---|---|---|---|---|---|---|
| Cirkali00013:2:2 | 7 | 30.83 | 20.91 | 0 | 1 | 6/7 |
| Kotumpalur00038:2:0 | 5 | 49.60 | 25.01 | 2 | 1 | 2/5 |
| tfaSIIv04p0i0163:4:3 | 5 | 58.35 | 25.02 | 2 | 1 | 2/5 |
| **total** | **17** | **138.78** | **70.94** | **4** | **3** | **10/17** (13/13 not touched by the budget) |

In the after run, the gaps that the budget did not touch matched before on decision, fill and top-1. The 3 "LLM cut"
gaps are pre-escalated Opus calls whose replies took longer than the time left: 2 timed out at the call's timeout,
and 1 (the last gap of the 7-gap request) was not asked because less than `llm_min_remaining_s` was left. Their fills
differ from before, as expected. One of the 4 abstained gaps (tfaSIIv04p0i0163 gap 3) had been filled before the
change.

## What a client sees

Each gap that the budget touched carries `abstain_reason` (`time_budget` | `gap_cap`), `llm_skipped` or
`escalation_skipped` (`time_budget` | `error`). Every response carries a `budget` summary (`limited`, and counts per
reason); see `contracts/restore-api.md`. The tutor does not cache a restoration whose `budget.limited` is true, so a
later lesson can try the full restoration again.

## Limits

- n = 3 requests and 17 gaps: this is a latency check, not an accuracy estimate. The budget trades fills on late
  gaps for a response inside 27 s. Whether to spend the budget differently (for example, Sonnet instead of
  pre-escalating to Opus late in a request) was not tuned, and should be chosen on VAL if it is.
- Running gaps in parallel (the issue's fourth option) was not tried. Each gap uses the earlier gaps' fills as
  context, so running in parallel would change results.
