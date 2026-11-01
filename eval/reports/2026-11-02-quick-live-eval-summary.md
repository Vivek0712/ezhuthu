# Quick live eval summary (2026-11-02, fast-track)

> **Caveat: N is small and the LLM runs are contaminated by harness failures.** LLM routers ran on only the first
> 30 items of the test-hard split (planned 60; cut for Bedrock throttling and the time box). Many items failed with
> `MaxTokensReachedException` (restorer `max_tokens=800`) and are scored as wrong + abstained. These numbers measure
> the current pipeline *including that bug*; they are not a quality estimate of Sonnet/Opus restoration and must not
> be cited as one.

- Data: `benchmark/` at main 8e5f4a8 (test 413 items, test-hard 317). DHARMA-derived, CC BY-SA 4.0.
- Decider (LLM routers): `strands-decider-2B-qwen3.5-v1-2610` (strands-decider 0.2.0, local mps, `strands-decider serve`).
- Models (config/models.yaml): default `us.anthropic.claude-sonnet-4-6`, escalate `us.anthropic.claude-opus-4-6-v1`.
- Abstain threshold: 0.5 (`routing.abstain_if_confidence_below`). Coverage below = share of items with top-1 confidence >= 0.5.

| router | split | n | item errors | top-1 | top-20 | CER mean | CER clipped | ECE | coverage@0.5 |
|---|---|---|---|---|---|---|---|---|---|
| baseline-copy | test full | 413 | 0 | 0.4165 | 0.5569 | 0.4736 | 0.4494 | 0.0734 | 0.2615 (acc 0.7037) |
| baseline-ngram | test full | 413 | 0 | 0.2567 | 0.3172 | 0.6296 | 0.6296 | 0.4924 | 0.8015 (acc 0.3172) |
| baseline-copy | same 30 hard items | 30 | 0 | 0.2333 | 0.4667 | - | - | - | - |
| baseline-ngram | same 30 hard items | 30 | 0 | 0.1667 | 0.2667 | - | - | - | - |
| sonnet | test-hard, first 30 | 30 | 6 (MaxTokens) | 0.1333 | 0.5000 | 1.0513 | 0.7513 | 0.1250 | 0.0 |
| routed | test-hard, first 30 | 30 | 18 (MaxTokens) | 0.1000 | 0.3667 | 1.0744 | 0.8411 | 0.0471 | 0.0 |
| routed --no-ontology | test-hard, first 30 | 30 | 18 (17 MaxTokens, 1 throttle) | 0.0667 | 0.3667 | 1.0856 | 0.8522 | 0.0137 | 0.0 |

baseline-zeroshot (full test, 413 Bedrock calls) was **not run**: Bedrock throttled at 5 concurrent Sonnet calls and it did
not fit the time box.

## Findings for the agent team

1. **Truncation bug dominates.** `Restorer` calls the LLM with `max_tokens=800` (src/ezhuthu/agent/restorer.py:168);
   18/30 routed items die with `MaxTokensReachedException` (the escalation path is worse than Sonnet-only, 6/30).
   Raise the limit and/or catch the exception and parse partial output before any quality claim.
2. **No coverage at the abstain threshold**: every LLM-router item had top-1 confidence < 0.5, so the decider-ranked
   pipeline abstains on everything at 0.5. ECE looks low only because confidences are uniformly low.
3. On the 30 items, the ontology ablation moves top-1 from 0.1000 to 0.0667 (1 item); not significant at this N.
4. Harness change in this PR: one failing item no longer crashes a live run; it is recorded with `error` and counted.

## Cost

Estimated (list prices, ezhuthu.agent.llm.PRICE_PER_MTOK) for the final N=30 runs: sonnet $0.1197 (13 live, 11 cached),
routed $0.0147 (2 live, 19 cached), no-ontology $0.0120. Earlier aborted N=60 attempts (crashed on throttling before the
fix) made roughly 20-25 more Sonnet/Opus calls that are not in these ledgers; total spend for this wave is well under $2.
