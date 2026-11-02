# Eval: restorer-val-routed-sanity

- Date: 2026-11-01T22:35:51+00:00
- Router: `routed`
- Split/subset: val/full, n = 6
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/w3-restorer/benchmark` (last data commit 20584c8)
- Code: not in any commit (uncommitted changes on top of 6a4449c)
- Provenance note: Provenance corrected (QA on PR #25): the original data_commit field held the checkout HEAD 6a4449c (main), but the run used uncommitted restorer changes that predate 585bbad, so no commit contains the exact code. data_commit is now the last commit touching benchmark/. Replaying from .cache/llm at 575f3ab (budget 0, 0 Bedrock calls) gives the same top-1 (0.1667), top-20 and abstain rate (0.6667) but CER 0.5946 instead of 0.5385; treat the CER here as superseded.
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
