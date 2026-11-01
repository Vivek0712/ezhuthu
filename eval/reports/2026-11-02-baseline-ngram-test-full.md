# Eval: baseline-ngram-test-full

- Date: 2026-11-01T20:20:24+00:00
- Router: `baseline-ngram`
- Split/subset: test/full, n = 383
- Data: `/private/tmp/claude-501/-Users-vivekrajaps-tamil-script/310306a5-bec0-4456-b84a-fd0e629aed33/scratchpad/bench/benchmark` (team/data/v1@fd69669 (PR #6))
- Decider: none (fallback confidence)
- Ontology constraints/hints: True (lookups-json, team/onto/v1@7d85a30 (PR #9, train-only build))
- Command: `python -m ezhuthu.eval.run --split test --router baseline-ngram --no-decider --data-ref team/data/v1@fd69669 (PR #6) --ontology-ref team/onto/v1@7d85a30 (PR #9, train-only build)`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 383 | 0.282 | 0.3446 | 0.5944 | 0.5944 | 0.7273 | 0.466 | 0.0 |
| hard | 301 | 0.2525 | 0.3223 | 0.6175 | 0.6175 | 0.75 | 0.4796 | 0.0 |
| age | 42 | 0.1905 | 0.2143 | 0.6471 | 0.6471 | 0.7646 | 0.4851 | 0.0 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.282 |
| 0.3 | 0.9661 | 0.2919 |
| 0.5 | 0.812 | 0.3473 |
| 0.6 | 0.6997 | 0.3955 |
| 0.7 | 0.6031 | 0.4459 |
| 0.8 | 0.5039 | 0.513 |
| 0.9 | 0.4021 | 0.6039 |
