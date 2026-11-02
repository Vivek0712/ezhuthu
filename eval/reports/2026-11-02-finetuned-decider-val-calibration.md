# Dev-set note: restorer decider variants and calibration (val split)

> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite as restoration quality.

- Date: 2026-11-02T12:55:29+00:00
- Items: 443 (val/full, limit None)
- Router: `sonnet`; ontology: on; decider: ezhuthu-strands-2b-ft
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/ft-decider/benchmark` (last data commit e83886327ff525f385c6865bd01b8e213fa597a8)
- Code: 2c2f5b2895dcd4082bf06bc1fe5cd6559540366e + uncommitted changes
- Command: `python -m ezhuthu.eval.calibrate --split val --router sonnet --variants choice-topk:3 --decider-url http://127.0.0.1:8791 --max-live-calls 45 --rpm 9 --name finetuned-decider-val-calibration --note Fine-tuned decider ezhuthu-strands-2b-ft (issue #37), chosen on VAL (eval/reports/2026-11-02-finetuned-decider.md). Restorer settings as deployed (5-gram pre-rank term on) with strategy choice-topk:3.`
- Bedrock: 39 live calls, 405 cached, estimated $0.1912 (budget 45, exhausted on 0 requests)

Copy baseline on the same items: top-1 0.2415.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-topk:3 | 0.3905 | 0.5418 | 74 / 8 | 0.4058 / 0.9687 | 0.0395 | 0.0357 | 0.3567 / 0.8291 | 0.3589 / 0.7987 | 0.5228 | 1 / 1 | 843.3 |

Variant keys written to the calibration file:

- `ezhuthu-strands-2b-ft|choice-topk|k3|llm-sonnet`: a=1.218461, b=-0.044221, threshold=0.5228 (n=443)

## Notes

- Fine-tuned decider ezhuthu-strands-2b-ft (issue #37), chosen on VAL (eval/reports/2026-11-02-finetuned-decider.md). Restorer settings as deployed (5-gram pre-rank term on) with strategy choice-topk:3.
