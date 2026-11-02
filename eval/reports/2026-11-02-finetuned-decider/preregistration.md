# Pre-registration: fine-tuned restoration decider, restorer-level VAL selection and the single TEST score

Written 2026-11-02, committed before any restorer-level VAL run of these variants and before any TEST score of a
fine-tuned decider. Row-level VAL scores of the fine-tuned models already exist (`../2026-11-02-ft-decider.md`,
Sparrow `MANIFEST.json`); they picked each trainer's checkpoint and are not re-used for the choice below.

## Candidates (`src/ezhuthu/eval/ft_decider_eval.py` `VARIANTS`)

| variant | decider | restorer settings for LLM-answered gaps |
|---|---|---|
| `ft2b-choice3` | `ezhuthu-strands-2b-ft` (served, mps) | `choice-topk:3`, deployed settings (5-gram pre-rank term on, no 5-gram slot) |
| `ft2b-noul3` | same | `noul-topk:3`, deployed settings |
| `ft2b-choice3-slot` | same | `choice-topk:3` + 5-gram slot (the hosted-v19 VAL run's settings) |
| `ft2b-choice3-plain` | same | `choice-topk:3`, no 5-gram term (the settings the training rows were recorded with) |
| `sparrow-tiny-ft-choice3` | `sparrow-tiny-ezhuthu-c3base-v0` | `choice-topk:3`, deployed settings |
| `sparrow-nano-ft-choice3` | `sparrow-nano-ezhuthu-ta-c3-v0` | `choice-topk:3`, deployed settings |

References run the same way: base 2B v1-2610 `choice-topk:3` and `noul-topk:3`. References read from the
deployed-config rows (same 280 gaps, same router): deployed `hybrid-prerank` (100/280), routed self-report
(Sonnet/Opus self-confidence, 85/280), routed prerank, hosted v19 `choice-topk:3` + slot (120-gap subset, 39/120).

## VAL protocol

The deployed-config selection set (280 VAL gaps, seed 26), router `routed` (Sonnet 4.6 -> Opus 4.6), ontology on,
escalation unchanged (0.6 on the raw top-1, 12 letters, no good parallel). Cached Bedrock replies first; new calls
capped. Decider requests one at a time.

## Rule

Chosen fine-tuned variant: among the candidates, the most top-1 matches on the 280; ties go to fewer decider calls,
then the lower p50 latency per gap. Rows where the decider failed and the restorer fell back to self-report count as
misses. The deployed default (hybrid-prerank, 100/280) would change only if the chosen variant had strictly more VAL
matches AND the cloud runtime could serve it; the runtime cannot serve a local checkpoint, so the model goes into
`config/models.yaml` disabled in either case and the report says whether it was eligible.

Calibration of the chosen variant, VAL only: `|llm-opus` from its routed run, `|llm-sonnet` from a Sonnet-only run
on the same 280 (deployed-config method), plus `python -m ezhuthu.eval.calibrate` (router sonnet, full VAL,
ontology on) for the `|llm-sonnet` key.

## TEST (once, chosen variant only, after the choice is committed)

1. Frozen 60-item benchmark: `decider_bench score --top-k 3` and the 24-option request, `policy`, report with every
   existing label.
2. Row-level on the ft-data TEST rows (413 choice3, 1,239 noul; cached Sonnet candidates): chosen model, base 2B,
   hosted v19 (choice3 only), Sonnet self-confidence and first-candidate from the rows.
3. Restorer, router `sonnet` on the full TEST split with cached Sonnet replies only (any new Bedrock call is
   refused and counted): chosen variant, base 2B `choice-topk:3`, self-report, deployed pre-rank; exact McNemar vs
   the chosen variant, bootstrap CIs.

Primary metric everywhere: top-1 matches the expert restoration (`metrics.canon`).
