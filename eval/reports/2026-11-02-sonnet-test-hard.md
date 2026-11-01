# Eval: sonnet-test-hard

- Date: 2026-11-01T20:32:32+00:00
- Router: `sonnet`
- Split/subset: test/hard, n = 30
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/evalq/benchmark` (8e5f4a8005e4d5dd6dc2641e2dd7019e4c592f11)
- Decider: strands-decider-2B-qwen3.5-v1-2610
- Ontology constraints/hints: True (ezhuthu.ontology.lookup)
- Command: `python -m ezhuthu.eval.run --split test --subset hard --limit 30 --workers 3 --router sonnet`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 30 | 0.1333 | 0.5 | 1.0513 | 0.7513 | 1.0 | 0.125 | 1.0 |
| hard | 30 | 0.1333 | 0.5 | 1.0513 | 0.7513 | 1.0 | 0.125 | 1.0 |
| age | 21 | 0.1429 | 0.381 | 0.7083 | 0.7083 | 0.8667 | 0.1545 | 1.0 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.1333 |
| 0.3 | 0.0667 | 0.0 |
| 0.5 | 0.0 | None |
| 0.6 | 0.0 | None |
| 0.7 | 0.0 | None |
| 0.8 | 0.0 | None |
| 0.9 | 0.0 | None |

Item errors (LLM throttling/truncation; scored as wrong + abstained): 6

LLM usage: 13 live calls, 11 cached; input tokens {'sonnet': 8463}, output tokens {'sonnet': 6288}; estimated cost $0.1197 (USD/MTok list prices in ezhuthu.agent.llm.PRICE_PER_MTOK).
