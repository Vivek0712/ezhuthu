# VAL selection for the full test evaluation (2026-11-02, issue #26)

> **VAL split only (development data).** Everything the TEST run uses was chosen here, by the rules stated below, before TEST was scored. These numbers are not restoration quality and must not be cited as such; in-sample calibration numbers are optimistic.

- LLM runs: seeded VAL sample of 120 items (seed 26), ontology on (train-only build), gap lengths in Tamil letters. Per-item rows: `2026-11-02-val-selection/rows/*.jsonl`.
- Data commit `e83886327ff525f385c6865bd01b8e213fa597a8`; code commits `12cf9d7`; code_dirty=false.
- Decider: `strands-decider-2B-qwen3.5-v1-2610` (local, strands-decider 0.2.0).

## 1. Retrieval-only gaps (no LLM): strategy

Full VAL, n = 443, retrieval + copy floor + 5-gram + ontology candidates. Copy baseline top-1 0.2415. Rule: highest full-VAL top-1 (n=443, retrieval candidates); ties go to the variant listed first.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | vs chosen (only / only, p) |
|---|---|---|---|---|
| prerank | 0.2551 | 0.5079 | 7 / 1 | 9 / 12, p=0.6636 |
| fallback | 0.2619 | 0.5079 | 19 / 10 | chosen |
| choice-topk:3 | 0.2393 | 0.5079 | 32 / 33 | 21 / 31, p=0.2116 |
| choice-topk:5 | 0.2415 | 0.5079 | 44 / 44 | 33 / 42, p=0.3557 |
| noul-topk:3 | 0.2483 | 0.5079 | 27 / 24 | 21 / 27, p=0.4709 |
| choice-all | 0.2506 | 0.5079 | 51 / 47 | 40 / 45, p=0.6646 |

`fallback` is restorer strategy `self-report` with no LLM fill: each retrieval candidate scores best parallel match x share of parallels agreeing (halved when the length is off); no decider call.

Chosen: **fallback**. Best decider variant (scored on TEST as the decider row): **choice-all**.

## 2. Gaps where an LLM answered: strategy

Sonnet 4.6 candidate pools on the VAL sample (the Sonnet replies are cached, so every variant ranks the same pools). Rule: highest VAL top-1 on the Sonnet candidate pools; ties go to the decider-free strategy listed first (self-report, then prerank).

| strategy | top-1 [95% CI] | top-20 | ECE (raw) | vs self-report (only / only, p) |
|---|---|---|---|---|
| self-report | 0.1167 [0.0667, 0.175] | 0.5 | 0.4182 | - |
| prerank | 0.15 [0.0917, 0.2083] | 0.5 | 0.4082 | 4 / 0, p=0.1250 |
| choice-topk:3 | 0.1667 [0.1, 0.2333] | 0.5 | 0.1593 | 10 / 4, p=0.1796 |
| choice-topk:5 | 0.1583 [0.0917, 0.225] | 0.5 | 0.131 | 11 / 6, p=0.3323 |
| noul-topk:3 | 0.1917 [0.125, 0.2583] | 0.5 | 0.3861 | 11 / 2, p=0.0225 |

Chosen: **noul-topk:3**. Best decider variant on LLM pools: **noul-topk:3**.

## 3. Escalation threshold (Sonnet 4.6 -> Opus 4.6)

Simulated exactly from two runs on the same items: Sonnet only, and routed with escalation after every Sonnet answer (threshold 1.01); a gap that pre-escalates (no parallel scoring >= 50, or a gap over 12 letters) goes to Opus first whatever the threshold. Rule: fewest Opus calls among thresholds whose VAL top-1 is within 1 percentage point of the best threshold's.

Sonnet only: top-1 0.1917; Opus only: 0.3167.

| raw threshold | top-1 | gaps that use Opus | pre-escalated | est. USD per gap | vs copy (only / only, p) |
|---|---|---|---|---|---|
| 0.0 | 0.2917 (35/120) | 96 (0.8) | 96 | 0.00637 | 18 / 4, p=0.0043 |
| 0.3 | 0.2917 (35/120) | 96 (0.8) | 96 | 0.00637 | 18 / 4, p=0.0043 |
| 0.4 | 0.2917 (35/120) | 96 (0.8) | 96 | 0.00637 | 18 / 4, p=0.0043 |
| 0.5 | 0.2917 (35/120) | 96 (0.8) | 96 | 0.00637 | 18 / 4, p=0.0043 |
| 0.6 (chosen) | 0.3 (36/120) | 100 (0.8333) | 96 | 0.00665 | 19 / 4, p=0.0026 |
| 0.7 | 0.3083 (37/120) | 113 (0.9417) | 96 | 0.00737 | 20 / 4, p=0.0015 |
| 0.8 | 0.3083 (37/120) | 120 (1.0) | 96 | 0.00774 | 20 / 4, p=0.0015 |
| 0.9 | 0.3083 (37/120) | 120 (1.0) | 96 | 0.00774 | 20 / 4, p=0.0015 |
| 1.01 | 0.3083 (37/120) | 120 (1.0) | 96 | 0.00774 | 20 / 4, p=0.0015 |

Chosen: **0.6** (config/models.yaml `routing.escalate_if_confidence_below`; was 0.6). At 0.6, 100 of 120 VAL gaps (0.8333) use Opus, 96 of them by pre-escalation.

## 4. Calibration entries written to `src/ezhuthu/agent/calibration.json`

| key | n | positives | a | b | abstain threshold | used by the restorer |
|---|---|---|---|---|---|---|
| `prerank|prerank|kall|llm-sonnet` | 120 | 18 | 1.021665 | -2.296331 | 0.5779 | yes |
| `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k3|llm-sonnet` | 120 | 20 | 1.125323 | -0.7731 | 0.5663 | yes |
| `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k5|llm-sonnet` | 120 | 19 | 0.838629 | -0.875664 | 1.0 | yes |
| `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|llm-opus` | 100 | 28 | 2.431386 | -1.430561 | 0.3772 | yes |
| `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|llm-sonnet` | 120 | 23 | 1.648963 | -1.976991 | 0.4001 | yes |

Baseline abstain thresholds (raw confidence, fitted on full VAL, used for coverage on TEST): baseline-copy 0.6012 (VAL top-1 0.2415, n=443); baseline-ngram 0.9103 (VAL top-1 0.298, n=443).

## Notes

- VAL picked noul-topk:3 for LLM gaps: the escalation grid and the LLM calibration below use its rows (val-sonnet-noul-topkk3, val-routed-always-noul-topkk3, val-opus-noul-topkk3; replayed from the cache, 0 Bedrock calls). Its raw top-1 is the decider's probability.
- Re-scored after the 5-gram determinism fix (QA on PR #31; `CharNgram.fill` had depended on PYTHONHASHSEED), from the reply cache with 0 Bedrock calls (`usage-rescore.json`): the full-VAL retrieval report and every VAL row were re-run, and every choice above is unchanged. Every VAL row has the same top-1 and fill/abstain as before; the Sonnet pools gained one target in the candidates (top-20 0.4917 -> 0.5); the 5-gram baseline's full-VAL top-1 is 0.298 (threshold 0.9103; one earlier process gave 0.3002 / 0.9104); the four decider retrieval calibration entries moved slightly (e.g. choice-all threshold 0.4143 -> 0.4121), the prerank, self-report and LLM entries did not.
