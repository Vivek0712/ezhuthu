# Dev-set note: restorer decider variants and calibration (val split)

> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite as restoration quality.

- Date: 2026-11-01T23:11:12+00:00
- Items: 20 (val/full, limit 20)
- Router: `sonnet`; ontology: off; decider: strands-decider-2B-qwen3.5-v1-2610
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/w3-restorer/benchmark` (585bbad4953b91f0dd7c6a7c3d7dbaf03f99efd1)
- Command: `python -m ezhuthu.eval.calibrate --split val --limit 20 --router sonnet --no-ontology --max-live-calls 0 --variants choice-topk:3,choice-topk:5,noul-topk:3,choice-all,prerank,fallback --calibration-out src/ezhuthu/agent/calibration.json --name restorer-val-live-sonnet --note Live sanity run: us.anthropic.claude-sonnet-4-6 (router sonnet, no Opus escalation) on the first 20 VAL items (all from 2 inscriptions, correlated). The 20 Bedrock calls were made once (20 live, 0 truncated, 0 retries, est. $0.0906); this re-scoring after the copy-floor pre-rank fix replays them from .cache/llm with a live-call budget of 0. --note Ontology off (the shipped ontology build reads val/test inscriptions). --note n=20: the llm-keyed calibration entries are provisional.`
- Bedrock: 0 live calls, 120 cached, estimated $0.0 (budget 0, exhausted on 0 requests)

Copy baseline on the same items: top-1 0.0.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.2874 / 0.5334 | 0.2874 | 0.0772 | 0.05 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 877.2 |
| choice-topk:5 | 0.05 | 0.25 | 1 / 0 | 0.3019 / 0.4953 | 0.2519 | 0.092 | 0.0 / - | 0.0 / - | 1.0 | 0 / 0 | 1078.1 |
| noul-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.5725 / 0.7164 | 0.5725 | 0.1277 | 0.75 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 1790.7 |
| choice-all | 0.05 | 0.25 | 1 / 0 | 0.1886 / 0.3276 | 0.1386 | 0.0605 | 0.0 / - | 0.0 / - | 1.0 | 0 / 0 | 2110.1 |
| prerank | 0.1 | 0.25 | 2 / 0 | 0.5361 / 0.944 | 0.4417 | 0.1618 | 0.5 / 0.2 | 0.0 / - | 0.6329 | 0 / 0 | 61.7 |
| fallback | 0.15 | 0.25 | 3 / 0 | 0.496 / 0.92 | 0.354 | 0.0754 | 0.45 / 0.2222 | 0.0 / - | 0.6373 | 0 / 0 | 58.5 |

Variant keys written to the calibration file:

- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k3|llm`: a=1.742495, b=-1.302177, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k5|llm`: a=1.480608, b=-1.044759, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|llm`: a=0.269836, b=-2.184105, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|choice-all|kall|llm`: a=1.426776, b=-0.49769, threshold=1.0 (n=20)
- `prerank|prerank|kall|llm`: a=0.828938, b=-1.796305, threshold=0.6329 (n=20)
- `fallback:llm-self-report|fallback|kall|llm`: a=0.802801, b=-1.396845, threshold=0.6373 (n=20)

## Notes

- Live sanity run: us.anthropic.claude-sonnet-4-6 (router sonnet, no Opus escalation) on the first 20 VAL items (all from 2 inscriptions, correlated). The 20 Bedrock calls were made once (20 live, 0 truncated, 0 retries, est. $0.0906); this re-scoring after the copy-floor pre-rank fix replays them from .cache/llm with a live-call budget of 0.
- Ontology off (the shipped ontology build reads val/test inscriptions).
- n=20: the llm-keyed calibration entries are provisional.
