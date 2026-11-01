# Eval: restorer-val-routed-sanity

- Date: 2026-11-01T22:35:51+00:00
- Router: `routed`
- Split/subset: val/full, n = 6
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/w3-restorer/benchmark` (6a4449cbd1b0efda325a69658aa79cf5166e8fa9)
- Decider: none (fallback confidence)
- Ontology constraints/hints: False
- Command: `python -m ezhuthu.eval.run --split val --limit 6 --router routed --no-ontology --no-decider --calibration none --max-live-calls 7 --rpm 20 --name restorer-val-routed-sanity`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 6 | 0.1667 | 0.1667 | 0.5385 | 0.5385 | 0.5924 | 0.3667 | 0.6667 |
| hard | 6 | 0.1667 | 0.1667 | 0.5385 | 0.5385 | 0.5924 | 0.3667 | 0.6667 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.1667 |
| 0.3 | 0.5 | 0.3333 |
| 0.5 | 0.3333 | 0.5 |
| 0.6 | 0.3333 | 0.5 |
| 0.7 | 0.3333 | 0.5 |
| 0.8 | 0.1667 | 0.0 |
| 0.9 | 0.0 | None |

LLM usage: 6 live calls, 1 cached; input tokens {'opus': 6071}, output tokens {'opus': 712}; estimated cost $0.0482 (USD/MTok list prices in ezhuthu.agent.llm.PRICE_PER_MTOK).
