# Hosted fine-tuned decider: live check on VAL (2026-11-03)

> **What this is.** The restorer, as shipped in this branch, ranking with the fine-tuned restoration decider
> (`ezhuthu-strands-2b-ft`, PR #43, chosen on VAL by the pre-registered rule) now that decider-cloud serves it next to
> v19 on its existing instances. This is a latency and plumbing check on 20 VAL gaps, not an accuracy measurement:
> the accuracy numbers are PR #43's ([`2026-11-02-finetuned-decider.md`](2026-11-02-finetuned-decider.md)). TEST was not
> touched. "Matches" means the top fill equals the DHARMA editors' restoration after ISO normalisation.

## Setup

- Script: [`training/ft-decider/hosted_live_check.py`](../../training/ft-decider/hosted_live_check.py), `EZHUTHU_LIVE=1
  EZHUTHU_DECIDER_BACKEND=hosted`, the first 20 VAL gaps (`load_items("val")`), each restored as a one-gap
  `/api/restore` would be: shipped restorer settings, a 25 s request budget, routed Sonnet 4.6 -> Opus 4.6 with live
  Bedrock calls (no cache), then `choice-topk` over the pre-rank's top 3 + none on the hosted fine-tune.
- Server: decider-cloud staging (2x c7i.xlarge, CPU, bf16). The fine-tune shares v19's base weights on each instance
  and one worker; a fine-tune request takes ~15-20% longer than the same v19 request.

## Results

| run | decider_timeout_s / decider_min_remaining_s | ranked by the hosted fine-tune | pre-rank fallback (unavailable / time_budget) | decider call p50 / p90 / max (client, s) | gap wall p50 / p90 / max (s) | over 25 s | fills | top-1 matches |
|---|---|---|---|---|---|---|---|---|
| 1 | 12 / 4 | 13 / 20 | 5 / 2 | 9.7 / 12.0 / 12.2 | 14.8 / 16.1 / 25.3 | 2 | 3 | 3 |
| **2 (shipped)** | **18 / 10** | **18 / 20** | **0 / 2** | **10.4 / 14.3 / 14.6** | **15.3 / 17.8 / 20.2** | **0** | 5 | 4 |

Both runs: 22 Bedrock calls, 19 of 20 gaps escalated to Opus (PR #43's routed VAL run escalated 244 of 280 with this
decider). Server time per fine-tune call: p50 9.0 s (run 1) and 9.6 s (run 2).

- **Run 1** capped each call at 12 s. Five calls hit the cap. The server still finishes a call the client gave up on,
  so the next call queued behind it and hit the cap too. Those gaps fell back to the pre-rank (`decider_fallback:
  unavailable`). Two gaps had too little budget left and ran 0.3 s past 25 s (the proxy allows 27 s).
- **Run 2** (shipped): a call may take up to 18 s and starts only with 10 s of the budget left. Every call finished,
  18 of 20 gaps were ranked by the fine-tune, the other 2 by the pre-rank (`time_budget`), and no gap passed 25 s.

## What it means for the runtime

- A one-gap restore now takes ~15 s (p50) instead of ~3.4 s for the decider-free pre-rank (PR #43: 3.4 s p50 per gap
  on VAL). Most of it is the decider call on CPU (~10 s on these prompts). A multi-gap request will rank its later gaps
  with the pre-rank once the budget runs low (`decider_fallback: time_budget`), as the budget design intends.
- Faster serving (a GPU, or the fine-tune's delta in bf16) would cut the decider call; neither is done here.
- If decider-cloud is down, slow or refuses, every gap falls back to the deployed pre-rank and says so.

Rows: [`2026-11-03-hosted-ft-live/`](2026-11-03-hosted-ft-live/) (`val-live-check-t12.*`, `val-live-check-t18.*`).
