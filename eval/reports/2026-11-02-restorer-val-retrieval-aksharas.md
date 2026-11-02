# Dev-set note: restorer decider variants and calibration (val split)

> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite as restoration quality.

- Date: 2026-11-02T01:26:18+00:00
- Items: 443 (val/full, limit None)
- Router: `none`; ontology: on; decider: strands-decider-2B-qwen3.5-v1-2610
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/w3b-eval/benchmark` (last data commit e83886327ff525f385c6865bd01b8e213fa597a8)
- Code: 5a6c36abc8e9ebe79c7aafade22725d29b5a77f1
- Command: `python -m ezhuthu.eval.calibrate --split val --router none --variants prerank,fallback,choice-topk:3,choice-topk:5,noul-topk:3,choice-all --calibration-out .cache/runs/cal-retrieval-onto.json --name restorer-val-retrieval-aksharas --out .cache/runs/reports --note issue #26: gap lengths counted in Tamil letters; ontology on (train-only build, direct lookup API); supersedes 2026-11-02-restorer-val-calibration-retrieval`

Copy baseline on the same items: top-1 0.2415.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| prerank | 0.2551 | 0.5079 | 7 / 1 | 0.3647 / 1.0 | 0.1116 | 0.0548 | 0.2032 / 0.5222 | 0.1377 / 0.5082 | 0.4116 | 0 / 0 | 69.5 |
| fallback | 0.2619 | 0.5079 | 19 / 10 | 0.1713 / 0.8354 | 0.098 | 0.0446 | 0.0451 / 0.8 | 0.0835 / 0.7838 | 0.5804 | 0 / 0 | 69.9 |
| choice-topk:3 | 0.2393 | 0.5079 | 32 / 33 | 0.3151 / 0.6085 | 0.0776 | 0.0456 | 0.0451 / 0.35 | 0.0158 / 0.1429 | 0.439 | 0 / 0 | 815.0 |
| choice-topk:5 | 0.2415 | 0.5079 | 44 / 44 | 0.2895 / 0.594 | 0.0479 | 0.0194 | 0.0226 / 0.4 | 0.0226 / 0.3 | 0.3792 | 0 / 0 | 1026.9 |
| noul-topk:3 | 0.2483 | 0.5079 | 27 / 24 | 0.5881 / 0.8314 | 0.3405 | 0.0203 | 0.8623 / 0.2827 | 0.0813 / 0.5833 | 0.4704 | 0 / 0 | 2476.6 |
| choice-all | 0.2506 | 0.5079 | 51 / 47 | 0.2781 / 0.5508 | 0.0319 | 0.0189 | 0.0181 / 0.375 | 0.0316 / 0.3571 | 0.4143 | 0 / 0 | 1125.9 |

Variant keys written to the calibration file:

- `prerank|prerank|kall|retrieval`: a=0.76634, b=-0.671803, threshold=0.4116 (n=443)
- `fallback:retrieval-heuristic|fallback|kall|retrieval`: a=1.156394, b=0.865914, threshold=0.5804 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k3|retrieval`: a=0.743281, b=-0.573114, threshold=0.439 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k5|retrieval`: a=0.91299, b=-0.325266, threshold=0.3792 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|retrieval`: a=2.338538, b=-2.145987, threshold=0.4704 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|choice-all|kall|retrieval`: a=0.975895, b=-0.167239, threshold=0.4143 (n=443)

## Notes

- issue #26: gap lengths counted in Tamil letters; ontology on (train-only build, direct lookup API); supersedes 2026-11-02-restorer-val-calibration-retrieval
