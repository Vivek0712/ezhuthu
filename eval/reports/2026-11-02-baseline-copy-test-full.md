# Eval: baseline-copy-test-full

- Date: 2026-11-01T20:20:22+00:00
- Router: `baseline-copy`
- Split/subset: test/full, n = 383
- Data: `/private/tmp/claude-501/-Users-vivekrajaps-tamil-script/310306a5-bec0-4456-b84a-fd0e629aed33/scratchpad/bench/benchmark` (team/data/v1@fd69669 (PR #6))
- Decider: none (fallback confidence)
- Ontology constraints/hints: True (lookups-json, team/onto/v1@7d85a30 (PR #9, train-only build))
- Command: `python -m ezhuthu.eval.run --split test --router baseline-copy --no-decider --data-ref team/data/v1@fd69669 (PR #6) --ontology-ref team/onto/v1@7d85a30 (PR #9, train-only build)`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 383 | 0.4125 | 0.5614 | 0.4946 | 0.4606 | 0.5 | 0.072 | 0.0339 |
| hard | 301 | 0.3322 | 0.485 | 0.5754 | 0.5322 | 0.5 | 0.0613 | 0.0432 |
| age | 42 | 0.2857 | 0.4524 | 0.6571 | 0.5619 | 0.6682 | 0.1519 | 0.0952 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.4125 |
| 0.3 | 0.6658 | 0.549 |
| 0.5 | 0.2559 | 0.7347 |
| 0.6 | 0.141 | 0.7963 |
| 0.7 | 0.0783 | 0.8 |
| 0.8 | 0.0444 | 0.8235 |
| 0.9 | 0.0261 | 0.8 |
