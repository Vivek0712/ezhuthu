# Deployed restorer configuration: chosen on VAL, calibrated on VAL, scored once on TEST (2026-11-02)

> **What this is.** The configuration the cloud app (AgentCore runtime) runs, chosen on the validation split by a
> rule committed before any of the variants was scored ([`preregistration.md`](2026-11-02-deployed-config/preregistration.md),
> commit `1322bdb`), calibrated on VAL, and then scored **once** on the 413 TEST gaps. "Matches the expert
> restoration" means the fill equals the DHARMA editor's supplied text after ISO normalisation; it does not mean
> "correct". Gap lengths are Tamil letters. The PR #31 numbers ([`2026-11-02-test-eval.md`](2026-11-02-test-eval.md))
> are unchanged and still describe what they measured (the local 2B decider pipeline, never deployable as measured).

## Headline

- **Deployed configuration:** routed Sonnet 4.6 -> Opus 4.6 (unchanged routing), then the decider-free pre-rank with
  the character 5-gram's share as a third noisy-OR term (`strategy_llm: prerank`, `ngram_prerank: true` in
  `config/models.yaml`; tag `prerank-ngram`). The cloud runtime runs the same restorer settings **with and without**
  the hosted decider key: no decider call is made for restoration (the key now only serves the tutor's decisions).
- **TEST (scored once):** top-1 matches the expert on **259 of 413** gaps (**0.6271**, 95% CI 0.5787-0.6731), above
  the character 5-gram baseline (0.5666; 34 vs 9 discordant gaps, p = 0.0002), copy (0.4722; 88 vs 24, p < 0.0001)
  and PR #31's measured routed + local 2B pipeline (0.4964; 74 vs 20, p < 0.0001).
- **Abstention, on a calibrated scale:** at its VAL-fitted thresholds it fills **49.9%** of TEST gaps and **90.8%** of
  those fills match the expert (187 of 206); ECE 0.110. Both runtime calibration keys
  (`prerank-ngram|prerank|kall|llm-sonnet` / `|llm-opus`) were fitted on VAL with n >= 224.
- **Where it still fails:** most TEST gaps are a single letter (281 of 413), where it reaches 0.7367; on gaps of 4+
  letters (n = 51) it matches 0.1961, the same as copying the best parallel.
- **The hosted v19 decider did not earn its place:** on the 120-gap hosted set it matched 39 vs 41 for the chosen
  configuration (2 vs 4 discordant, p = 0.69), and it made 13 of 120 gaps exceed the 27 s proxy limit (latency p90
  28.1 s; median hosted call 7.5 s).
- **Cost and latency (TEST, original call latencies):** 122 Sonnet + 297 Opus calls, about $2.49 at list prices
  ($0.0060 per gap); 296 of 413 gaps use Opus (291 by pre-escalation, 5 after Sonnet). Latency per gap p50 3.2 s,
  p90 5.5 s, max 16.1 s; no gap over 27 s. **The 27 s proxy limit (API Gateway: 29 s) is per request, not per
  gap:** `restore()` handles a request's gaps one after another with no cap, so at the p90 a request with about 5 gaps,
  or a first request that also pays the 5.8 s 5-gram build, can exceed it. This predates this PR; follow-up #41.

## How the choice was made (read before re-using the rows)

- **Pre-registered rule** (committed before scoring): stage 1, the decider-free variant with the most VAL top-1
  matches on the same 280 VAL gaps (ties: cheaper, then faster); stage 2, the hosted-v19 variant replaces it only with
  strictly more matches on the 120-gap hosted set. Selection used top-1 only; nothing was re-tuned (escalation 0.6,
  5-gram gate 0.9103, `top_k` 3 as shipped).
- **Why 280 VAL gaps, not 443:** the routed variants on full VAL needed about 340 new Bedrock calls (248 Opus replies
  for pre-escalated gaps were not cached), over this issue's 300-call budget, which also had to cover TEST. The
  selection set is the issue #26 seeded 120-gap sample plus 160 more VAL gaps (seed 26); the hosted set is the 120.
  The 5-gram baseline on full VAL is 0.2980 (n = 443), on the selection set 0.2821.
- **VAL is harder than TEST for every system** (copy 0.2415 vs 0.4722, 5-gram 0.2980 vs 0.5666, chosen variant 0.3571
  on the selection set vs 0.6271): VAL has fewer single-letter gaps (205 of 443, 46%, vs 281 of 413, 68%), more gaps of
  4+ letters (116, 26%, vs 51, 12%) and more hard gaps (90% vs 77%). VAL is used only to rank the variants against each
  other on the same gaps and to fit the calibration; its absolute levels are not a forecast of TEST.
- **One deviation, found after the VAL runs and before the calibration was written:** `fit_platt` (undamped Newton)
  diverged on the chosen variant's scores (a = 218, threshold 1.0, which would have filled 88% of gaps at 40% accuracy
  in-sample). It now halves the Newton step when a full step does not lower the penalised loss. Every issue #26
  entry refits to the same digits from its rows (tested), and the choice itself (top-1) is unaffected.
- **Calibration source:** `|llm-opus` from the routed run's Opus-answered gaps (n = 224), `|llm-sonnet` from a
  Sonnet-only run of the same variant on the selection set (n = 278; as in issue #26, a routed run has too few gaps
  Sonnet alone answers). The out-of-fold columns in the VAL tables are the honest within-VAL estimate; the in-sample
  ones are optimistic. **The `|llm-sonnet` fitting and runtime populations differ:** it was fitted on every
  selection-set gap answered by Sonnet alone, but at runtime it applies only to gaps Sonnet answered without
  escalation (117 of 413 on TEST, where 83 of its 88 fills match; the Opus key: 104 of 118). The thresholds are
  therefore not exact for the runtime mix, as in issue #26. TEST selective accuracy (0.908) is well above the VAL
  out-of-fold estimate (0.726); both keys are above it on TEST, so most of that difference is the VAL-TEST level gap
  (next bullet), and this mismatch could move it either way on other data.
- **Runtime path checked:** `config/models.yaml` and `calibration.json` ship in the bundle; infra sets no restorer
  override (`infra/test/agent-runtime.test.ts`), and `tests/agent/test_runtime_restorer_config.py` builds the
  runtime's `EzhuthuService()` with `EZHUTHU_DECIDER_BACKEND=hosted` and `=fallback` and checks both resolve to this
  configuration, make no decider call for restoration, and fill or abstain on the VAL calibration.
- **5-gram in the runtime:** it was already built there (the pipeline always added 5-gram proposals). Built from the
  14,355 train corpus lines it holds about 36 MB with the corpus, takes 5.8 s to fit on first use (cold start) and
  11 ms per gap to fill (p50; p90 43 ms, max 205 ms; Apple M4 Pro). The corpus file is 6.8 MB of the bundle.
- **Live calls:** Bedrock 168 new (35 Sonnet, 133 Opus), all on VAL; TEST made 0 (every reply was in PR #31's cache).
  Hosted decider 144 calls (VAL only). Budgets: 300 Bedrock, 600 hosted.
- **Not deployed** by this PR; the next deploy picks the settings up from the bundle.

## VAL: stage 1 (selection set, same items)

| variant | n | top-1 [95% CI] | matches | top-20 | vs ngram (only / only, p) | LLM calls (Sonnet / Opus) | gaps with no LLM call | decider calls | est. USD per gap | latency p50 / p90 / max s (gaps over 27 s) | coverage / selective acc., in-sample | same, 5-fold out-of-fold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a. Character 5-gram only (no LLM, no decider) | 280 | 0.2821 [0.2321, 0.3357] | 79 | 0.4821 | - | 0 / 0 | 0 | 0 | 0.00000 | 0.0 / 0.1 / 0.2 (0) | 0.2143 / 0.7500 (45/60) | 0.2143 / 0.7500 (45/60) |
| b1. 5-gram gate (fill the 5-gram when its share >= 0.9103), else routed + prerank | 280 | 0.3286 [0.275, 0.3857] | 92 | 0.5571 | 30 / 17, p=0.0789 | 39 / 190 | 60 | 0 | 0.00549 | 3.2 / 6.6 / 17.5 (0) | 0.4607 / 0.6124 (79/129) | 0.4571 / 0.6094 (78/128) |
| b2. Routed + prerank with the 5-gram share as a noisy-OR term | 280 | 0.3571 [0.3, 0.4143] | 100 | 0.5536 | 25 / 4, p=0.0001 | 61 / 225 | 0 | 0 | 0.00668 | 3.4 / 7.1 / 17.5 (0) | 0.2536 / 0.8028 (57/71) | 0.2607 / 0.7260 (53/73) |
| c. Routed + prerank (no decider) | 280 | 0.2964 [0.2429, 0.3536] | 83 | 0.5536 | 35 / 31, p=0.7122 | 61 / 231 | 0 | 0 | 0.00683 | 3.4 / 7.6 / 19.4 (0) | 0.2929 / 0.7073 (58/82) | 0.2786 / 0.7179 (56/78) |
| e. Routed + self-report (the cloud runtime without a decider) | 280 | 0.3036 [0.2464, 0.3607] | 85 | 0.5536 | 38 / 32, p=0.5504 | 61 / 237 | 0 | 0 | 0.00699 | 3.2 / 7.6 / 17.4 (0) | 0.3179 / 0.6180 (55/89) | 0.2500 / 0.6143 (43/70) |

Ranking by the rule: hybrid-prerank, hybrid-gate, routed-selfreport, routed-prerank, ngram. Stage-1 winner: **hybrid-prerank**.

## VAL: stage 2 (hosted set, 120 items, same items)

| variant | n | top-1 [95% CI] | matches | top-20 | vs ngram (only / only, p) | LLM calls (Sonnet / Opus) | gaps with no LLM call | decider calls | est. USD per gap | latency p50 / p90 / max s (gaps over 27 s) | coverage / selective acc., in-sample | same, 5-fold out-of-fold |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a. Character 5-gram only (no LLM, no decider) | 120 | 0.2750 [0.2, 0.35] | 33 | 0.4417 | - | 0 / 0 | 0 | 0 | 0.00000 | 0.0 / 0.0 / 0.2 (0) | 0.1833 / 0.8636 (19/22) | 0.1833 / 0.8636 (19/22) |
| b1. 5-gram gate (fill the 5-gram when its share >= 0.9103), else routed + prerank | 120 | 0.3333 [0.25, 0.425] | 40 | 0.5333 | 13 / 6, p=0.1671 | 19 / 84 | 22 | 0 | 0.00555 | 3.3 / 6.6 / 17.5 (0) | 0.6083 / 0.5342 (39/73) | 0.6083 / 0.5342 (39/73) |
| b2. Routed + prerank with the 5-gram share as a noisy-OR term | 120 | 0.3417 [0.2583, 0.4333] | 41 | 0.5250 | 9 / 1, p=0.0215 | 24 / 98 | 0 | 0 | 0.00651 | 3.3 / 7.9 / 17.5 (0) | 0.6750 / 0.4691 (38/81) | 0.7583 / 0.4505 (41/91) |
| c. Routed + prerank (no decider) | 120 | 0.2750 [0.2, 0.3667] | 33 | 0.5250 | 14 / 14, p=1.0000 | 24 / 103 | 0 | 0 | 0.00681 | 3.4 / 9.2 / 19.4 (0) | 0.2083 / 0.7200 (18/25) | 0.5500 / 0.4697 (31/66) |
| e. Routed + self-report (the cloud runtime without a decider) | 120 | 0.2750 [0.2, 0.3583] | 33 | 0.5250 | 14 / 14, p=1.0000 | 24 / 105 | 0 | 0 | 0.00691 | 3.2 / 9.0 / 17.4 (0) | 0.1250 / 0.7333 (11/15) | 0.4750 / 0.4561 (26/57) |
| d. Routed + hosted v19 `choice-topk:3` (5-gram prerank + 5-gram slot) | 120 | 0.3250 [0.2417, 0.4083] | 39 | 0.5417 | 9 / 3, p=0.1460 | 24 / 120 | 0 | 144 | 0.00774 | 11.6 / 28.1 / 42.2 (13) | 0.0833 / 0.7000 (7/10) | 0.0083 / 1.0000 (1/1) |

Hosted v19 39 vs stage-1 winner 41 matches of 120 (only hosted / only winner: 2 / 4, p = 0.6875); hosted wins: False.

**Chosen: b2. Routed + prerank with the 5-gram share as a noisy-OR term** (`hybrid-prerank`).

### Calibration entries fitted for it (VAL only)

| key | n | positives | a | b | abstain threshold | used by the runtime |
|---|---|---|---|---|---|---|
| `prerank-ngram\|prerank\|kall\|llm-opus` | 224 | 67 | 0.656823 | -1.870518 | 0.4887 | yes |
| `prerank-ngram\|prerank\|kall\|llm-sonnet` | 278 | 85 | 0.685211 | -2.132567 | 0.4111 | yes |

## TEST: the deployed configuration, scored once (413 gaps)

| configuration | n | top-1 [95% CI] | top-20 | CER clipped | ECE | coverage | selective acc. |
|---|---|---|---|---|---|---|---|
| **Deployed: b2. Routed + prerank with the 5-gram share as a noisy-OR term** | 413 | 0.6271 [0.5787, 0.6731] | 0.7966 | 0.2964 | 0.1103 | 0.4988 | 0.9078 (187/206) |
| Copy baseline (PR #31 row) | 413 | 0.4722 [0.4237, 0.5206] | 0.6610 | 0.4435 | 0.0771 | 0.1622 | 0.7761 (52/67) |
| Character 5-gram baseline (PR #31 row) | 413 | 0.5666 [0.5182, 0.615] | 0.7458 | 0.3610 | 0.1611 | 0.3705 | 0.9020 (138/153) |
| Routed + local 2B decider (PR #31 measured pipeline) | 413 | 0.4964 [0.4479, 0.5448] | 0.8015 | 0.4193 | 0.1130 | 0.4649 | 0.6354 (122/192) |

Hard subset and age subset (deployed configuration):

| subset | n | top-1 [95% CI] | coverage | selective acc. |
|---|---|---|---|---|
| hard | 317 | 0.5741 [0.5205, 0.6278] | 0.4101 | 0.9077 |
| age | 51 | 0.5686 [0.4314, 0.7059] | 0.3333 | 0.8824 |

Paired exact McNemar on top-1 (same 413 gaps; only deployed right / only the other right):

| vs | n | only deployed | only other | p |
|---|---|---|---|---|
| copy baseline | 413 | 88 | 24 | <0.0001 |
| character 5-gram | 413 | 34 | 9 | 0.0002 |
| PR #31 routed row | 413 | 74 | 20 | <0.0001 |

Top-1 by gap length (Tamil letters), same TEST gaps:

| configuration | 1 letter (n=281) | 2-3 letters (n=81) | 4+ letters (n=51) |
|---|---|---|---|
| Deployed | 0.7367 | 0.5185 | 0.1961 |
| Copy baseline | 0.5445 | 0.3951 | 0.1961 |
| Character 5-gram | 0.6797 | 0.4321 | 0.1569 |
| PR #31 routed + local 2B | 0.5730 | 0.4444 | 0.1569 |

| cost and latency (deployed, TEST) | value |
|---|---|
| LLM calls (Sonnet / Opus) | 122 / 297 |
| gaps that used Opus | 296 |
| gaps filled by the 5-gram gate with no LLM call | 0 |
| hosted decider calls | 0 |
| est. USD (per gap) | 2.4871 (0.00602) |
| latency per gap p50 / p90 / max s (gaps over 27 s) | 3.2 / 5.5 / 16.1 (0) |
| calibration keys applied | `prerank-ngram\|prerank\|kall\|llm-opus`, `prerank-ngram\|prerank\|kall\|llm-sonnet` |

## Notes

- **Cloud runtime before this PR** (unmeasured until now): with the key, `noul-topk:3` on the hosted v19 decider (3
  hosted calls per ranking, up to 6 per gap; at 10 requests a minute that alone is 12-30 s of pacing, so it could not
  fit the 27 s proxy limit); without it, the self-report fallback (variant e: 85 of 280 VAL gaps vs 100 for the
  chosen one). Both ran uncalibrated at the raw 0.5 threshold.
- **Escalation** is unchanged (0.6 on the raw top-1, now the `prerank-ngram` score; 12 letters; no good parallel). It
  was not re-tuned for the new score: on TEST only 5 of the 122 gaps Sonnet answered first went on to Opus.
- **Stage-2 abstain columns** are fitted on the 120 hosted-set gaps alone (small groups, so their thresholds are
  noisy); they are reported for completeness and were not used for any decision.
- **Latency** per gap = local compute + the original latency of each LLM call (cached replies keep the latency of
  the call that produced them) + hosted decider HTTP time. Client-side pacing between different gaps of the eval is
  excluded; within one gap a second hosted call is charged the rest of the 6 s pacing interval. Apple M4 Pro,
  Bedrock us-east-1, throttling retries not included.
- **Cost** is list price (`ezhuthu.agent.llm.PRICE_PER_MTOK`), an estimate, not the bill; the hosted decider's free
  tier is not priced.
- **The 5-gram TEST number** cited for comparison is PR #31's re-scored 0.5666 (after its determinism fix), not the
  first-pass 0.5714.
- **Rows:** `2026-11-02-deployed-config/rows/` (`val-*` VAL runs, `test-deployed` the single TEST run; every row
  carries its LLM calls with tokens and original latency). Decisions and fitted entries:
  `2026-11-02-deployed-config/decisions.json`. Ledgers: `usage-val.json`, `usage-val-hosted.json`, `usage-test.json`.
- **Reproduce** (0 model calls with the reply cache): `python -m ezhuthu.eval.deploy_config choose` and `report`;
  the runs themselves are `val`, `val-hosted` and `test` (see the module docstring).
- Data: `benchmark/` (DHARMA-derived, CC BY-SA 4.0). Models: `us.anthropic.claude-sonnet-4-6`,
  `us.anthropic.claude-opus-4-6-v1`; hosted decider `strands-decider-2b-hobson-v19` (decider-cloud staging). TEST
  run code commit `402a6f1`, clean tree.
