# Fine-tuned restoration decider: chosen on VAL, scored once on TEST (2026-11-02)

> **What this is.** A decider fine-tuned on the restorer's own decision ("which of the top-3 candidate fills, or
> none, matches the expert restoration"), trained on TRAIN only, chosen and calibrated on VAL by a rule committed
> before the restorer-level VAL runs ([`preregistration.md`](2026-11-02-finetuned-decider/preregistration.md), commit
> `2c2f5b2`), then scored **once** on TEST. "Matches the expert" means the fill equals the DHARMA editor's supplied
> text after ISO normalisation (`metrics.canon`); it does not mean "correct". Training details:
> [`2026-11-02-ft-decider.md`](2026-11-02-ft-decider.md); data and leakage controls:
> [`2026-11-02-ft-data.md`](2026-11-02-ft-data.md). Numbers: [`2026-11-02-finetuned-decider.json`](2026-11-02-finetuned-decider.json).

## Answer

**Yes, on full TEST it beats Sonnet self-confidence, the base 2B and hosted v19, and the deployed decider-free
ranking. On the frozen 60-item TEST-hard benchmark it does not: it ties Sonnet self-confidence (0.400) and is below
hosted v19 top-3 (0.450; 1 vs 4 discordant items, p = 0.375).** It is not deployed. It is registered in
`config/models.yaml` with `enabled: false`, because the cloud runtime has no way to serve a local checkpoint.

- **Chosen variant:** `ezhuthu-strands-2b-ft` with the restorer's `choice-topk:3` request (`ft2b-choice3`).
- **TEST, restorer (413 gaps, Sonnet 4.6 candidates replayed from the cache, 0 new Bedrock calls):** top-1 **0.6538**
  (270/413, 95% CI 0.6077-0.6973). The same pipeline ranked by Sonnet self-confidence gets 0.3874 (116 vs 6
  discordant gaps, p < 1e-6). The deployed decider-free pre-rank gets 0.5908 (32 vs 6, p = 2.4e-5). The base 2B
  gets 0.5811 (41 vs 11, p = 3.6e-5). After calibration it fills **57.6%** of gaps, and **92.0%** of those fills match
  the expert (238 fills; ECE 0.070).
- **TEST, decider only (413 recorded requests, top-3 + none, the same requests for every decider):** top-1
  **0.5472** against a ceiling of 0.6029 (the target is among the 3). Sonnet self-confidence 0.3826 (+0.165 [+0.126,
  +0.203], 73 vs 5 discordant), base 2B 0.4165 (+0.131, 56 vs 2), hosted v19 0.4310 (+0.116 [+0.082, +0.153], 53 vs 5,
  p < 1e-8), first candidate 0.4092. All p < 1e-8.
- **Frozen 60-item benchmark (TEST-hard, pre-#31 request shape):** top-3 + none 0.400 (Sonnet self-confidence 0.400,
  hosted v19 top-3 0.450, base 2B 0.217). With all ~20 candidates: 0.350. **It does not beat hosted v19 or Sonnet
  here.** These are 60 items in an older request format that the model was not trained on (see Caveats).

## Data and leakage controls

- Rows (`ezhuthu-ft/data`, outside git; builder `src/ezhuthu/eval/ft_data.py`) are the requests
  `Restorer.rank_and_decide` sends. Labels are the option whose fill equals the expert target, else `none`.
- **TRAIN only for training:** 2,334 `choice3` + 6,936 `noul` rows from 2,337 train items. sha256: `train.choice3`
  `8d7a94df…`, `train.noul` `2a11a648…`.
- **Near-duplicates dropped:** **96 of 2,433** train items (78 matched a TEST item, 18 a VAL item). The specified
  rule (normalised Levenshtein >= 0.9 on the 40-letter context window) dropped **0**, because a shared formula gapped
  at different points shifts the window. A shift-invariant rule (rapidfuzz `partial_ratio` >= 90 of the train
  window inside the VAL/TEST context) dropped the 96. Both rules were applied, and both counts are recorded in
  `build_meta.json`.
- **Cross-fitted train candidates:** retrieval and the 5-gram for a train item are built without its fold (5 folds by
  stone). Audit: 0 of 6,996 train parallels came from the item's own fold.
- **Selection and calibration on VAL only:** the trainer's checkpoint and temperatures, the variant below and the
  calibration were all fixed on VAL. TEST was read once, after the commit that fixed the choice and the calibration
  (`96c05d6`). The TEST code commit is `96c05d6` with a clean tree (the harness refuses a dirty tree).
- Data sha256: val `32bc196e…` / `d8ee7019…`, test `43487c7a…` / `37ed3606…`, test-bench60 `527ab38d…` /
  `511201ff…`, frozen benchmark candidates `ab00901f055d…`.

## Training compute and cost

| model | what was trained | where | time | cost |
|---|---|---|---|---|
| `ezhuthu-strands-2b-ft` (chosen) | continue-from of Strands Decider v1-2610 2B: its LoRA adapter (r 48, 50.5M) + pointer head (3.2M), 1 epoch, 580 steps x 16 rows | vast.ai 1x A100 40 GB (local M4 Pro checked first: ~6 s/row, 15 h; not feasible) | 74 min per variant, 2 variants + VAL scoring, 3.5 h total | **USD 2.26** |
| `sparrow-tiny-ezhuthu-c3base-v0` | Ettin-32M + pointer head on TRAIN choice3 | M4 Pro (mps) | 21 min | 0 |
| `sparrow-nano-ezhuthu-ta-c3-v0` | static model, Tamil WordPiece vocabulary (8k, dim 64) from TRAIN text | M4 Pro | seconds | 0 |

Data build: 1,162 Sonnet 4.6 calls, about USD 4.8 (`2026-11-02-ft-data.md`). This evaluation used 28 new Opus calls
for VAL escalations (USD 0.19) and 39 new Sonnet calls for the full-VAL calibration (USD 0.19). TEST made 0 Bedrock
calls (1,652 replies came from the cache). Hosted v19 received 413 TEST requests from the free tier, with 0 errors.

## VAL selection (restorer, 280 VAL gaps, routed Sonnet -> Opus, ontology on)

These are the deployed-config issue's selection-set gaps. Escalation is unchanged. Decider requests go one at a time.
The rows are in `2026-11-02-finetuned-decider/rows/val-*.jsonl`. The references (deployed, self-report, hosted v19)
are that issue's rows on the same gaps.

| variant | top-1 [95% CI] | matches | vs deployed (only this / only deployed, p) | vs routed self-report (p) | decider calls | p50 / p90 s per gap | coverage / sel. acc. (5-fold OOF) |
|---|---|---|---|---|---|---|---|
| **ft 2B `choice-topk:3` (chosen)** | **0.4000 [0.336, 0.457]** | **112** | 18 / 6, p = 0.023 | 38 / 11, p = 0.0001 | 305 | 4.5 / 10.7 | 0.361 / 0.822 |
| ft 2B `choice-topk:3` + 5-gram slot | 0.3929 | 110 | 17 / 7, p = 0.064 | 37 / 12, p = 0.0005 | 305 | 4.1 / 10.1 | |
| ft 2B `noul-topk:3` | 0.3893 | 109 | 17 / 8, p = 0.108 | 34 / 10, p = 0.0004 | 909 | 8.0 / 12.2 | |
| Sparrow tiny ft `choice-topk:3` | 0.3607 | 101 | 12 / 11, p = 1.0 | 30 / 14, p = 0.023 | 301 | 3.7 / 9.6 | |
| ft 2B `choice-topk:3`, no 5-gram term | 0.3536 | 99 | 19 / 20, p = 1.0 | 25 / 11, p = 0.029 | 304 | 4.1 / 10.2 | |
| Sparrow nano ft `choice-topk:3` | 0.3286 | 92 | 11 / 19, p = 0.20 | 29 / 22, p = 0.40 | 311 | 3.3 / 8.9 | |
| base 2B `noul-topk:3` | 0.3214 | 90 | 10 / 20, p = 0.10 | 26 / 21, p = 0.56 | 879 | 7.8 / 11.0 | |
| base 2B `choice-topk:3` | 0.2964 | 83 | 9 / 26, p = 0.006 | 28 / 30, p = 0.90 | 341 | 4.4 / 11.2 | |
| *deployed: pre-rank + 5-gram term (no decider)* | 0.3571 | 100 | - | | 0 | 3.4 / 7.1 | |
| *routed self-report (Sonnet/Opus self-confidence)* | 0.3036 | 85 | | - | 0 | 3.2 / 7.6 | |
| *hosted v19 `choice-topk:3` + slot (120-gap subset)* | 0.3250 (39/120) | | ft 2B on the same 120: 42 (only ft 6 / only hosted 3, p = 0.51) | | 144 | 11.6 / 28.1 | |

- **Rule outcome:** `ft2b-choice3` has the most matches (112). It is "eligible" under the rule's first condition
  (strictly more than the deployed 100). The second condition, that the cloud runtime can serve it, fails. So the
  deployed default is **not** changed.
- No decider call failed on VAL or TEST (0 fallback rows), and there were 0 Bedrock budget refusals.
- **Row-level VAL** (the trainer's own selection, 443 VAL requests, top-3 + none; from `2026-11-02-ft-decider.md` and
  the Sparrow `MANIFEST.json`): ft 2B 0.325, Sparrow tiny ft 0.314, Sparrow nano ft 0.298, hosted v19 0.266, base 2B
  0.246, first candidate 0.244, Sonnet self-confidence 0.210, Sparrow general nano 0.185, Sparrow general small 0.084.
  The ceiling is 0.373.

### Calibration (VAL only)

| key | source | n | positives | a | b | abstain threshold |
|---|---|---|---|---|---|---|
| `ezhuthu-strands-2b-ft\|choice-topk\|k3\|llm-sonnet` | `python -m ezhuthu.eval.calibrate --router sonnet` on full VAL ([dev note](2026-11-02-finetuned-decider-val-calibration.md)) | 443 | 173 | 1.2185 | -0.0442 | 0.5228 |
| `ezhuthu-strands-2b-ft\|choice-topk\|k3\|llm-opus` | routed VAL run, Opus-answered gaps (`ft_decider_eval calibrate`) | 244 | 79 | 1.2529 | 0.1125 | 0.4975 |

On full VAL (Sonnet candidates) at the raw 0.5 threshold it fills 0.357 of gaps at 0.829 accuracy; at the fitted
threshold, out of fold (5-fold), it fills 0.359 at 0.799, with calibrated ECE 0.036. Both entries are in `src/ezhuthu/agent/calibration.json`. They apply only when a
decider that answers as `ezhuthu-strands-2b-ft` is active, so the deployed restorer is unaffected. The Sonnet-only
280-gap fit (n = 280, threshold 0.488) is recorded in `2026-11-02-finetuned-decider/calibration.json` and was not
written.

## TEST (scored once)

### 1. Restorer, full TEST, Sonnet candidates from the cache (413 gaps)

Router `sonnet`, ontology on, and the same restorer settings for every row (deployed settings, with the strategy
for LLM-answered gaps varied). The run refuses any new Bedrock call: 0 were made and 0 were refused. Rows are in
`2026-11-02-finetuned-decider/rows/test-sonnet-*.jsonl`.

| ranking of the same candidates | top-1 [95% CI] | matches | hard (317) | coverage / selective acc. (VAL thresholds) | ECE | vs ft 2B (only ft / only other, p) |
|---|---|---|---|---|---|---|
| **fine-tuned 2B `choice-topk:3`** | **0.6538 [0.6077, 0.6973]** | **270** | **0.5962** | **0.5763 / 0.9202** | 0.070 | - |
| deployed pre-rank + 5-gram term (no decider) | 0.5908 [0.5424, 0.6392] | 244 | 0.5363 | 0.4939 / 0.9167 | 0.125 | 32 / 6, p = 2.4e-5 (hard 24 / 5, p = 0.0005) |
| base 2B `choice-topk:3` | 0.5811 [0.5327, 0.6295] | 240 | 0.5016 | 0.0024 / 1.0 | 0.422 | 41 / 11, p = 3.6e-5 (hard 38 / 8) |
| Sonnet self-confidence (self-report) | 0.3874 [0.3414, 0.4334] | 160 | 0.2934 | 0.7554 / 0.5000 (raw 0.5) | 0.270 | 116 / 6, p < 1e-6 (hard 99 / 3) |

By gap length (Tamil letters) for ft 2B / deployed / base / self-report: 1 letter (n = 281) 0.754 / 0.705 / 0.683 /
0.456; 2-3 letters (n = 81) 0.543 / 0.457 / 0.444 / 0.296; 4+ letters (n = 51) 0.275 / 0.176 / 0.235 / 0.157.

For context only, not a paired comparison: the deployed configuration as deployed (routed, Opus on 296 gaps) scored
0.6271 on TEST ([`2026-11-02-deployed-config.md`](2026-11-02-deployed-config.md)). The fine-tuned decider was not
run routed on TEST. That would have needed new Opus calls for its escalations, and the pre-registered TEST protocol
replays cached Sonnet replies only.

### 2. Decider only, on the recorded TEST requests (`test.choice3`, 413; `test.noul`, 1,239)

These are the requests the restorer sent (Sonnet candidates, ontology off, the PR #31 letter-count shape). Every
decider got identical requests, and the probabilities are used as served (nothing is fitted on TEST). Script:
`training/ft-decider/heldout_metrics.py`. Per-request scores: `2026-11-02-finetuned-decider/decider-scores/`.

| decider | top-1 | top-1 when target in top-3 | 4-way acc. | 4-way NLL | coverage / acc. at p >= 0.5 | ECE (top fill) |
|---|---|---|---|---|---|---|
| **fine-tuned 2B** | **0.5472** | **0.908** | **0.869** | **0.397** | 0.535 / 0.923 | 0.036 |
| hosted v19 (decider-cloud) | 0.4310 | 0.715 | 0.513 | 1.031 | 0.078 / 0.844 | 0.104 |
| base 2B v1-2610 | 0.4165 | 0.691 | 0.477 | 1.119 | 0.058 / 0.625 | 0.082 |
| first candidate (c0) | 0.4092 | 0.679 | - | - | - | - |
| Sonnet self-confidence | 0.3826 | 0.635 | - | - | 0.760 / 0.494 | 0.280 |

The ceiling (target among the 3) is 0.6029. Paired differences (fine-tuned minus the other, bootstrap 95% interval,
discordant counts):

| vs | full TEST (413) | TEST-hard (317) |
|---|---|---|
| Sonnet self-confidence | +0.165 [+0.126, +0.203], 73 / 5 | +0.161 [+0.120, +0.205], 54 / 3 |
| hosted v19 | +0.116 [+0.082, +0.153], 53 / 5 | +0.110 [+0.073, +0.148], 38 / 3 |
| base 2B | +0.131 [+0.099, +0.167], 56 / 2 | +0.133 [+0.092, +0.174], 44 / 2 |
| first candidate | +0.138 [+0.102, +0.174], 63 / 6 | +0.133 [+0.092, +0.174], 46 / 4 |

All McNemar p < 1e-7. On `noul` (one yes/no per candidate, 20.1% yes), the fine-tuned model has AUC 0.971, ECE
0.015 and Brier 0.044, against the base 2B's 0.793, 0.352 and 0.259. Hosted v19 was asked only the choice rows.

### 3. Frozen 60-item TEST-hard decider benchmark

`decider_bench score` on `2026-11-02-decider-benchmark-candidates.jsonl` with label `ft2b-top3` (`--top-k 3`) and
`ft2b` (all candidates). The report is regenerated with every existing label
([`2026-11-02-decider-benchmark.md`](2026-11-02-decider-benchmark.md); earlier rows unchanged).

| decider | top-1 | top-1 when target is a candidate | coverage / selective acc. at 0.5 | latency p50 ms |
|---|---|---|---|---|
| hosted v19 top-3 | 0.450 | 0.771 | 0.167 / 0.500 | 4,827 |
| **fine-tuned 2B top-3** | **0.400** | 0.686 | 0.350 / 0.857 | 471 |
| Sonnet self-confidence (fallback) | 0.400 | 0.686 | 0.550 / 0.667 | - |
| fine-tuned 2B, all ~20 candidates | 0.350 | 0.600 | 0.283 / 0.824 | 1,745 |
| base 2B (all candidates) | 0.217 | 0.371 | 0 / - | 1,784 |

Fine-tuned top-3 vs hosted v19 top-3: 1 / 4 discordant items, p = 0.375. vs Sonnet self-confidence: 3 / 3, p = 1.0.
vs base 2B: 14 / 3, p = 0.013. Reference points on these items: first candidate 0.400, uniform random among the top 3
0.161, target in the top 3 0.483. The ft-data `test-bench60` rows (the same requests) reproduce 0.400 through
`strands-decider serve`.

**Tutor policy** (20 scripted learner states, `decider_bench policy`): the fine-tuned model agrees with the rules on
0.60 of states raw and 0.80 after guardrails, the same as the base 2B (0.60 / 0.80). Restoration fine-tuning did not
change this small check.

## Latency and size

- Fine-tuned 2B on the M4 Pro (mps, `strands-decider serve`, one request at a time): decider HTTP time per gap
  0.83 s p50 and 1.12 s p90 on TEST. Per gap including the LLM it is 4.5 s p50 on VAL, against 3.4 s for the
  deployed pre-rank. `noul-topk:3` costs 3 calls per ranking (8.0 s p50 per gap).
- The checkpoint is 224 MB (LoRA adapter + pointer head) on top of the Qwen3.5-2B base, which `strands-decider` loads
  from the Hub cache. Sparrow tiny ft is 12.8 MB at about 0.37 s per request on CPU (numpy). Sparrow nano ft is
  0.74 MB at about 1 ms.

## Caveats

- **Router:** the TEST restorer comparison uses Sonnet-only candidates (replayed). The deployed system routes most
  gaps to Opus. The fine-tuned decider's routed TEST number is unknown. On VAL, routed, it beat the deployed
  ranking 112 vs 100.
- **Distribution:** the model was trained on Sonnet + retrieval candidates with ontology off (two thirds of train items
  were retrieval-only). The restorer runs here use ontology on and the 5-gram pre-rank term. The frozen 60-item
  benchmark uses the pre-#31 request (`gap_length_chars`, ISO-character length flags), which the model never saw.
  That benchmark is the one place it does not beat Sonnet or hosted v19. It is only 60 items, and the differences
  there are not significant.
- **Formulaic text:** DHARMA formulae repeat across inscriptions. Near-duplicates of VAL/TEST were dropped from
  TRAIN, but formulae shared only among train inscriptions remain (the legitimate parallels retrieval uses).
- **Selection bias on VAL:** six variants were compared, so the chosen variant's VAL number is slightly optimistic.
  TEST is the unbiased estimate.
- **Hosted v19 on TEST** is the decider-cloud staging model as of 2026-11-02, called through `HostedDecider` (key
  from Secrets Manager, never logged).

## Serve (not enabled)

```bash
HF_HUB_OFFLINE=1 strands-decider serve /Users/vivekrajaps/tamil-script/ezhuthu-ft/strands-2b-ft \
    --device mps --port 8791 --model-name ezhuthu-strands-2b-ft      # strands-decider[mps]==0.2.0
# ezhuthu: EZHUTHU_DECIDER_BACKEND=local EZHUTHU_DECIDER_URL=http://127.0.0.1:8791, restorer.strategy_llm: choice-topk
```

Deploying it would need a serving host for a 2B model next to the AgentCore runtime, or a decider-cloud model slot.
Both are out of scope here: no deployment, and decider-cloud is not touched.

## Reproduce (0 model calls with the caches)

```bash
# servers: ft 2B :8791, base 2B :8771, Sparrow tiny ft :8793, nano ft :8794 (one request at a time)
EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval val --decider ft2b=http://127.0.0.1:8791 \
    --decider base2b=http://127.0.0.1:8771 --decider sparrow-tiny-ft=http://127.0.0.1:8793 \
    --decider sparrow-nano-ft=http://127.0.0.1:8794
python -m ezhuthu.eval.ft_decider_eval choose
EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval val-sonnet --decider ft2b=http://127.0.0.1:8791
EZHUTHU_LIVE=1 python -m ezhuthu.eval.calibrate --split val --router sonnet --variants choice-topk:3 \
    --decider-url http://127.0.0.1:8791 --name finetuned-decider-val-calibration
python -m ezhuthu.eval.ft_decider_eval calibrate --write-calibration --keys llm-opus
EZHUTHU_LIVE=1 python -m ezhuthu.eval.ft_decider_eval test --decider ft2b=http://127.0.0.1:8791 \
    --decider base2b=http://127.0.0.1:8771
python -m ezhuthu.eval.ft_decider_eval summary
python -m ezhuthu.eval.decider_bench score --cands eval/reports/2026-11-02-decider-benchmark-candidates.jsonl \
    --decider local=http://127.0.0.1:8791 --label ft2b-top3 --top-k 3     # and --label ft2b; policy --label ft2b
python training/ft-decider/http_score.py http://127.0.0.1:8791 ft2b.test.jsonl test.choice3.jsonl test.noul.jsonl
python training/ft-decider/hosted_val.py test.choice3.jsonl hosted-v19.test.choice3.jsonl
python3 training/ft-decider/heldout_metrics.py --choice-data test.choice3.jsonl --noul-data test.noul.jsonl \
    ft2b=ft2b.test.jsonl base2b=base2b.test.jsonl hosted_v19=hosted-v19.test.choice3.jsonl
```

## Credits

Strands Decider v1-2610 (`StrandsAgents/strands-decider-2B-qwen3.5-v1-2610`, StrandsAgents) on Qwen3.5-2B-Base
(Qwen, Apache-2.0); Sparrow Decider fine-tunes on Ettin-32M (JHU, MIT); the Sparrow general nano baseline on
potion/Model2Vec (MinishLab, MIT). Data: DHARMA (CC BY-SA 4.0). LLM: `us.anthropic.claude-sonnet-4-6`,
`us.anthropic.claude-opus-4-6-v1`. Hosted decider: `strands-decider-2b-hobson-v19` (decider-cloud staging).
