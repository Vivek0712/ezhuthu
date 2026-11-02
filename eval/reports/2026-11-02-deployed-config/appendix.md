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
