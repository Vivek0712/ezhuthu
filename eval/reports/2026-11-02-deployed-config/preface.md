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
  (the "VAL is harder" bullet above), and this mismatch could move it either way on other data.
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
