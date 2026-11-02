# Fine-tuned Strands Decider for the restorer (VAL only)

- Date: 2026-11-02. Issue #37 (fine-tuning data in `2026-11-02-ft-data.md`). Code: `training/ft-decider/`.
- Question: does a decider fine-tuned on the restorer's own decision ("which of the top-3 fills, or none, is the
  expert restoration") beat Sonnet self-confidence, the base 2B and hosted v19?
- **VAL answer: yes, on every comparison.** TEST has **not** been scored; it should be scored once, next.

## Headline (VAL, 443 items, the same requests for every decider)

`top-1` = the highest-probability fill among `c0..c2` equals the expert target (the `decider_bench` rule: `none`
is never the pick). Ceiling (target among the three) 0.373. Paired differences: bootstrap 95 % interval over
items, and exact McNemar on the items where the two disagree.

| decider | top-1 | top-1 when the target is a candidate | 4-way accuracy (incl. `none`) | 4-way NLL | fills at conf >= 0.5 | accuracy of those fills |
|---|---:|---:|---:|---:|---:|---:|
| first candidate (`c0`) | 0.244 | 0.655 | - | - | - | - |
| Sonnet 4.6 self-confidence | 0.210 | 0.564 | - | - | 0.634 | 0.310 |
| base 2B (`strands-decider-2B-qwen3.5-v1-2610`, local mps) | 0.246 | 0.661 | 0.530 | 1.101 | 0.045 | 0.300 |
| hosted v19 (`strands-decider-2b-hobson-v19`, decider-cloud) | 0.266 | 0.715 | 0.623 | 0.947 | 0.059 | 0.769 |
| **fine-tuned 2B (`strands-2b-ft`, served on mps)** | **0.325** | **0.873** | **0.865** | **0.391** | 0.343 | **0.822** |

| fine-tuned minus ... | top-1 delta | 95 % interval | only the other right / only fine-tuned right | McNemar p |
|---|---:|---|---|---:|
| base 2B | +0.079 | [+0.050, +0.108] | 6 / 41 | 2e-7 |
| hosted v19 | +0.059 | [+0.036, +0.084] | 2 / 28 | 9e-7 |
| Sonnet self-confidence | +0.115 | [+0.084, +0.147] | 2 / 53 | 9e-14 |

For context (not significant): hosted v19 minus base 2B +0.020 [-0.011, +0.050]; base 2B minus Sonnet
self-confidence +0.036 [0.000, +0.072].

The fine-tuned model reaches 0.325 of a 0.373 ceiling (87 %). The larger change is that its probabilities can now
be trusted. At the restorer's abstain threshold (0.5) it fills 34 % of VAL items at 82 % accuracy; Sonnet's
self-confidence fills 63 % at 31 %; the base 2B fills 4.5 %. Its `none` probability carries real
information: 4-way accuracy rises from 0.53 to 0.87 while VAL's `none` share is 0.63.

Coverage / accuracy of the top fill at confidence >= t (VAL choice3):

| decider | t=0.1 | t=0.2 | t=0.3 | t=0.4 | t=0.5 | t=0.7 |
|---|---|---|---|---|---|---|
| Sonnet self-confidence | 0.995 / 0.209 | 0.953 / 0.218 | 0.935 / 0.222 | 0.675 / 0.294 | 0.634 / 0.310 | 0.431 / 0.403 |
| base 2B (mps) | 1.000 / 0.246 | 0.941 / 0.254 | 0.546 / 0.310 | 0.219 / 0.320 | 0.045 / 0.300 | 0.002 / 1.000 |
| hosted v19 | 1.000 / 0.266 | 0.928 / 0.285 | 0.569 / 0.369 | 0.217 / 0.479 | 0.059 / 0.769 | 0.005 / 1.000 |
| fine-tuned (served) | 0.492 / 0.642 | 0.451 / 0.685 | 0.400 / 0.746 | 0.372 / 0.776 | 0.343 / 0.822 | 0.293 / 0.885 |

By the DATA_CARD `hard` flag (top-1): hard (401 items, ceiling 0.332): c0 0.217, Sonnet 0.187, base 0.222, hosted
0.239, fine-tuned **0.282**. Not hard (42, ceiling 0.762): 0.500 / 0.429 / 0.476 / 0.524 / **0.738**.

### noul (one yes/no row per top-3 candidate; 1,329 rows, 12.5 % yes)

| decider | AUC | ECE | Brier | NLL | top-1 when ranking the three by P(yes) |
|---|---:|---:|---:|---:|---:|
| base 2B (own temperatures) | 0.788 | 0.402 | 0.258 | 0.711 | 0.255 |
| base 2B (2-fold cross-fitted temperature) | 0.789 | 0.383 | 0.250 | 0.693 | 0.255 |
| fine-tuned, served temperature (fitted on all VAL, in-sample) | 0.962 | 0.014 | 0.042 | 0.149 | 0.325 |
| fine-tuned, 2-fold cross-fitted temperature (honest) | 0.960 | 0.014 | 0.042 | 0.150 | 0.325 |

Hosted v19 was asked only the `choice` rows (the free tier's 10 rpm put 1,329 noul rows at over 2 h).

## What was trained

- Base: Strands Decider v1-2610 `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` (rev `216d1ccb`, StrandsAgents),
  on `Qwen/Qwen3.5-2B-Base` (rev `b1485b2f`, Qwen, Apache-2.0). This is the same checkpoint as the "base 2B" row.
- **Continue-from fine-tune**: the checkpoint's own LoRA adapter (r 48, 50.5M parameters, upcast to fp32 for
  training) and its pointer head (3.2M) are trained; the torso is frozen; nothing is re-initialised.
- Rows: TRAIN only, `train.choice3.jsonl` (2,334, sha256 `8d7a94df…`) + `train.noul.jsonl` (6,936, sha256
  `2a11a648…`), weight 1 each, one epoch = 580 steps of 16 rows (micro-batch 1, gradient checkpointing).
  Cross-entropy over the row's options at temperature 1. No option shuffling: the restorer always sends
  `c0, c1, c2, none` in pre-rank order, and the order is information the model may use.
- Variants (both one epoch, seed 0): **A** lr 5e-5 adapter / 5e-4 head; **B** 1e-4 / 1e-3. Checkpoints at steps
  145, 290, 435 and 580 of each; all 8, plus the base, scored on VAL (choice3 + noul).
- Selection (`training/ft-decider/SELECTION_RULE.txt`, written after A's VAL scores and before any B score was
  read): highest VAL top-1; ties within 0.005 go to the lower 2-fold cross-fitted VAL choice NLL. All 8
  checkpoints fell within 0.005 (0.321 to 0.325), so NLL decided: **A step 580** (0.393; next A-435 0.402).
- Served temperatures: choice 1.30, noul 1.45, fitted by NLL on all of VAL (cross-fitted halves: 1.25 to 1.35 and
  1.35 to 1.50). Top-1 does not depend on them.

Per-checkpoint VAL (GPU scoring, temperature 1; cv = 2-fold cross-fitted temperature):

| ckpt | top-1 | 4-way acc | choice NLL (cv) | noul AUC | noul ECE (cv) |
|---|---:|---:|---:|---:|---:|
| base | 0.246 | 0.530 | 1.056 | 0.788 | 0.383 |
| A-145 | 0.321 | 0.628 | 0.724 | 0.938 | 0.042 |
| A-290 | 0.323 | 0.844 | 0.439 | 0.954 | 0.011 |
| A-435 | 0.325 | 0.853 | 0.402 | 0.960 | 0.012 |
| **A-580** | **0.325** | 0.865 | **0.393** | 0.962 | 0.012 |
| B-145 | 0.323 | 0.700 | 0.653 | 0.934 | 0.024 |
| B-290 | 0.325 | 0.824 | 0.482 | 0.948 | 0.017 |
| B-435 | 0.323 | 0.860 | 0.444 | 0.948 | 0.013 |
| B-580 | 0.323 | 0.856 | 0.412 | 0.953 | 0.007 |

Top-1 saturates within a quarter epoch; the rest of training sharpens the `none` decision and calibration. Train
loss kept falling (A: 0.48 over steps 1 to 50, 0.19 over steps 540 to 580) while VAL NLL still improved at 580,
so a second epoch might help NLL; it was not tried.

## Why not `strands-decider train` / decider-lab `finetune`

- The `strands-decider==0.2.0` wheel (what serves the v1-2610 checkpoints) ships no trainer.
- The trainers on this machine (`~/.venvs/decider-3e94e9d`, `~/vision-decider/sd-next`, `sd-series`) predate the
  v1-2610 export: 3e94e9d has no `continue_from` (only `init_from`, which freezes the adapter and trains a new
  head); sd-next/sd-series have `continue_from` but render prompts with an older prompting module than 0.2.0
  serves, and the v1-2610 checkpoint is a 3-seed soup (LoRA r 48, pointer dim 768) that those configs do not
  describe. decider-lab's `finetune` drives one of those trainers.
- So `training/ft-decider/ft_decider.py` is a small trainer on strands-decider 0.2.0's own code: `StrandsDeciderModel.load`,
  `render_question` / `render_state`, the engine's `_fit` (window fitting, question-first truncation) and option
  positions, and `model(...)`'s loss. Training rows therefore tokenise exactly as `strands-decider serve` tokenises
  the restorer's requests, and the saved checkpoint loads in `strands-decider serve` unchanged (verified: all
  1,772 VAL rows sent to `strands-decider serve` on port 8791 over HTTP. Top-1 is 0.325 and noul AUC 0.962,
  the same as the in-process GPU scores).

## Compute and cost

- Local check first (M4 Pro 24 GB, mps): about 6 s per row with gradient checkpointing (4 h for choice3 alone,
  15 h for the mix); without checkpointing a step did not finish in 10 minutes (memory pressure). Not feasible.
- vast.ai: 1x A100 PCIe 40 GB (offer 58658629, Estonia), instance 58789087, image
  `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`, strands-decider 0.2.0 + flash-linear-attention 0.6.0, torch
  2.7.1+cu128, transformers 5.22.1, peft 0.21.2. About 7.6 s per 16-row step (74 min per variant); VAL scoring
  about 2 min per checkpoint.
- A local watchdog was set to destroy the instance at a fixed deadline (5.1 h, under USD 3). The instance was
  destroyed by hand after the run and checked to be gone (11:23 UTC).
- **Actual cost: USD 2.26** (3.5 h at USD 0.638/h including storage; vast credit 53.85 to 51.59).
- Hosted v19 on VAL: 443 requests to decider-cloud staging through `HostedDecider` (key from Secrets Manager, not
  logged), 0 errors, 0 trimmed. No Bedrock calls were made in this run (the Sonnet numbers come from the cached
  candidates in the data rows).

## Leakage and honesty notes

- Training used TRAIN rows only. VAL picked the variant, the step and the temperatures. TEST was not read by any
  script in this run (the vast instance received only the train and val files).
- Selection on VAL makes the VAL number slightly optimistic. Here the 8 candidates are within 0.004 of each
  other on top-1, so the choice barely affects it. The served temperatures are fitted on VAL; the cross-fitted
  rows above are the honest calibration numbers, and they are the same to 0.002.
- The train/VAL candidate mix differs: VAL candidates all come from Sonnet + retrieval, while two thirds of
  TRAIN items are retrieval-only. The model was not given the source.
- Devices: training and checkpoint selection ran on an A100. The headline numbers come from the checkpoint served
  on mps. Between the two devices the picked fill differs on 1 of 443 VAL rows for the base 2B (5 on the 4-way
  pick; noul probabilities move by at most 0.012) and on 3 of 443 for the fine-tuned model. Top-1 is the same on
  both devices for both models.
- The comparison with hosted v19 here is on VAL rows, top-3 + `none`, the same requests. The earlier TEST-hard
  bench60 number (0.450) is on other items and must not be compared with these.
- Serve the model behind the post-#31 restorer: the training rows use `gap_length_tamil_letters`, which main does
  not send yet.

## Artefacts (outside git: `/Users/vivekrajaps/tamil-script/ezhuthu-ft/`)

- Checkpoint: `strands-2b-ft/` (224 MB: `lora/adapter_model.safetensors` sha256 `eea859fa…`, `slot_head.pt`
  `7fc7d4fd…`, `strands_decider_config.json`, README with credits, `finetune.json`, `SHA256SUMS`).
- Scores: `scores-mps/{base,ft-served}.val.jsonl`, `scores-gpu/{base,A-*,B-*}.val.jsonl`,
  `scores-hosted-v19.val.choice3.jsonl`, `scores-sonnet-selfconf.val.choice3.jsonl`. Metrics:
  `logs/val_final_vs_*.{json,txt}`, `logs/val_metrics_all.json`. Training logs: `logs/train_{A,B}.log.jsonl`,
  `logs/logs_train_{A,B}.log`. vast ledger: `logs/vast-ledger.log`.
- Data: `data/` as built in `2026-11-02-ft-data.md` (val.choice3 `32bc196e…`, val.noul `d8ee7019…`).

## Serve

```bash
HF_HUB_OFFLINE=1 strands-decider serve /Users/vivekrajaps/tamil-script/ezhuthu-ft/strands-2b-ft \
    --device mps --port 8791 --model-name ezhuthu-strands-2b-ft
# ezhuthu: EZHUTHU_DECIDER_BACKEND=local EZHUTHU_DECIDER_URL=http://127.0.0.1:8791
```

(`strands-decider` from `pip install "strands-decider[mps]==0.2.0"`; the env used here is
`/Users/vivekrajaps/tamil-script/ezhuthu-ft/venv-ft`.) About 0.75 s per choice and 0.65 s per noul request on the
M4 Pro.

## Reproduce

```bash
F=/Users/vivekrajaps/tamil-script/ezhuthu-ft; PY=$F/venv-ft/bin/python   # strands-decider[mps]==0.2.0
# train (GPU; training/ft-decider/remote_setup.sh + remote_run.sh do this on vast)
python ft_decider.py train --device cuda --train train.choice3.jsonl train.noul.jsonl --out runs/A \
    --lr 5e-5 --head-lr 5e-4 --accum 16 --epochs 1 --save-at 145,290,435 --grad-ckpt --seed 0
python ft_decider.py score --device cuda --ckpt runs/A/checkpoint-580 --temps '{"choice":1.0,"noul":1.0}' \
    --out A-580.val.jsonl val.choice3.jsonl val.noul.jsonl
# metrics, curves, hosted v19
python3 training/ft-decider/val_metrics.py --choice-data $F/data/val.choice3.jsonl --noul-data $F/data/val.noul.jsonl \
    --baseline base_mps base_mps=... ft_served=... hosted_v19=... sonnet_sc=...
python3 training/ft-decider/val_curves.py $F/data/val.choice3.jsonl name=path[:T] ...
.venv/bin/python training/ft-decider/hosted_val.py $F/data/val.choice3.jsonl out.jsonl   # from the worktree
$PY training/ft-decider/http_score.py http://127.0.0.1:8791 out.jsonl $F/data/val.choice3.jsonl $F/data/val.noul.jsonl
```

## Next

1. Done: [`2026-11-02-finetuned-decider.md`](2026-11-02-finetuned-decider.md) (restorer-level VAL selection, then
   TEST scored once: full-TEST top-1 0.547 vs hosted v19 0.431 and Sonnet self-confidence 0.383 on the same requests;
   the frozen 60-item benchmark 0.400 vs hosted v19 0.450).
2. Then decide whether the restorer uses this decider (`strategy` choice-topk with top-3) behind the post-#31 restorer.
3. Optional: E4B on the same recipe (not done: 2B already reaches 87 % of the top-3 ceiling; most of the
   remaining loss is the candidate pool, 0.373 of VAL items).
