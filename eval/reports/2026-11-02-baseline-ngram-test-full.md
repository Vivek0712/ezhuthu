# Eval: baseline-ngram-test-full

- Date: 2026-11-01T20:24:17+00:00
- Router: `baseline-ngram`
- Split/subset: test/full, n = 413
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/evalq/benchmark` (8e5f4a8005e4d5dd6dc2641e2dd7019e4c592f11)
- Decider: none (fallback confidence)
- Ontology constraints/hints: True (ezhuthu.ontology.lookup)
- Command: `python -m ezhuthu.eval.run --router baseline-ngram --split test --no-decider`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 413 | 0.2567 | 0.3172 | 0.6296 | 0.6296 | 0.7692 | 0.4924 | 0.0 |
| hard | 317 | 0.2366 | 0.3028 | 0.6454 | 0.6454 | 0.8 | 0.4995 | 0.0 |
| age | 51 | 0.1373 | 0.1765 | 0.7095 | 0.7095 | 0.8 | 0.5364 | 0.0 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.2567 |
| 0.3 | 0.9782 | 0.2624 |
| 0.5 | 0.8015 | 0.3172 |
| 0.6 | 0.7094 | 0.3584 |
| 0.7 | 0.6053 | 0.4 |
| 0.8 | 0.4891 | 0.4851 |
| 0.9 | 0.3923 | 0.5494 |
