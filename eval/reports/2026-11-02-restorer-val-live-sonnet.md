# Dev-set note: restorer decider variants and calibration (val split)

> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite as restoration quality.

- Date: 2026-11-01T22:35:14+00:00
- Items: 20 (val/full, limit 20)
- Router: `sonnet`; ontology: off; decider: strands-decider-2B-qwen3.5-v1-2610
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/w3-restorer/benchmark` (6a4449cbd1b0efda325a69658aa79cf5166e8fa9)
- Command: `python -m ezhuthu.eval.calibrate --split val --limit 20 --router sonnet --no-ontology --max-live-calls 26 --rpm 20 --variants choice-topk:3,choice-topk:5,noul-topk:3,choice-all,prerank,fallback --calibration-out /private/tmp/claude-501/-Users-vivekrajaps-tamil-script/310306a5-bec0-4456-b84a-fd0e629aed33/scratchpad/w3r/cal-llm.json --name restorer-val-live-sonnet --note Live sanity run: us.anthropic.claude-sonnet-4-6 (router sonnet, no Opus escalation) on the first 20 VAL items; the first variant makes the Bedrock calls, every later variant reuses the cached replies (identical prompts), so all variants score the same LLM candidates. --note Ontology off (the shipped ontology build reads val/test inscriptions). --note n=20: calibration parameters fitted on 20 items are weak; the llm-keyed entries are provisional.`
- Bedrock: 20 live calls, 100 cached, estimated $0.0906 (budget 26, exhausted on 0 requests)

Copy baseline on the same items: top-1 0.0.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.3125 / 0.6614 | 0.3125 | 0.098 | 0.1 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 3517.2 |
| choice-topk:5 | 0.05 | 0.25 | 1 / 0 | 0.3115 / 0.605 | 0.2615 | 0.0843 | 0.05 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 2095.3 |
| noul-topk:3 | 0.0 | 0.25 | 0 / 0 | 0.5725 / 0.7164 | 0.5725 | 0.1277 | 0.75 / 0.0 | 0.0 / - | 1.0 | 0 / 0 | 5476.3 |
| choice-all | 0.05 | 0.25 | 1 / 0 | 0.2005 / 0.4719 | 0.1505 | 0.0725 | 0.0 / - | 0.0 / - | 1.0 | 0 / 0 | 3060.1 |
| prerank | 0.15 | 0.25 | 3 / 0 | 0.4839 / 0.944 | 0.3395 | 0.1072 | 0.45 / 0.2222 | 0.0 / - | 0.6502 | 0 / 0 | 73.0 |
| fallback | 0.15 | 0.25 | 3 / 0 | 0.496 / 0.92 | 0.354 | 0.0754 | 0.45 / 0.2222 | 0.0 / - | 0.6373 | 0 / 0 | 74.6 |

Variant keys written to the calibration file:

- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k3|llm`: a=1.477813, b=-1.555953, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k5|llm`: a=1.375921, b=-1.148827, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|llm`: a=0.269836, b=-2.184105, threshold=1.0 (n=20)
- `strands-decider-2B-qwen3.5-v1-2610|choice-all|kall|llm`: a=1.336674, b=-0.660092, threshold=1.0 (n=20)
- `prerank|prerank|kall|llm`: a=0.711188, b=-1.388671, threshold=0.6502 (n=20)
- `fallback:llm-self-report|fallback|kall|llm`: a=0.802801, b=-1.396845, threshold=0.6373 (n=20)

## Notes

- Live sanity run: us.anthropic.claude-sonnet-4-6 (router sonnet, no Opus escalation) on the first 20 VAL items; the first variant makes the Bedrock calls, every later variant reuses the cached replies (identical prompts), so all variants score the same LLM candidates.
- Ontology off (the shipped ontology build reads val/test inscriptions).
- n=20: calibration parameters fitted on 20 items are weak; the llm-keyed entries are provisional.
