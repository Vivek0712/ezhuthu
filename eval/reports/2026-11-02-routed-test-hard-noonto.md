# Eval: routed-test-hard-noonto

- Date: 2026-11-01T20:39:15+00:00
- Router: `routed`
- Split/subset: test/hard, n = 30
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/evalq/benchmark` (8e5f4a8005e4d5dd6dc2641e2dd7019e4c592f11)
- Decider: strands-decider-2B-qwen3.5-v1-2610
- Ontology constraints/hints: False
- Command: `python -m ezhuthu.eval.run --split test --subset hard --limit 30 --workers 3 --router routed --no-ontology`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 30 | 0.0667 | 0.3667 | 1.0856 | 0.8522 | 1.0 | 0.0137 | 1.0 |
| hard | 30 | 0.0667 | 0.3667 | 1.0856 | 0.8522 | 1.0 | 0.0137 | 1.0 |
| age | 21 | 0.0952 | 0.2381 | 0.8444 | 0.8444 | 1.0 | 0.0384 | 1.0 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.0667 |
| 0.3 | 0.0 | None |
| 0.5 | 0.0 | None |
| 0.6 | 0.0 | None |
| 0.7 | 0.0 | None |
| 0.8 | 0.0 | None |
| 0.9 | 0.0 | None |

Item errors (LLM throttling/truncation; scored as wrong + abstained): 18

LLM usage: 2 live calls, 19 cached; input tokens {'sonnet': 444, 'opus': 444}, output tokens {'sonnet': 164, 'opus': 240}; estimated cost $0.012 (USD/MTok list prices in ezhuthu.agent.llm.PRICE_PER_MTOK).
