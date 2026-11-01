# Eval: baseline-copy-test-full

- Date: 2026-11-01T20:24:15+00:00
- Router: `baseline-copy`
- Split/subset: test/full, n = 413
- Data: `/Users/vivekrajaps/tamil-script/ezhuthu-wt/evalq/benchmark` (8e5f4a8005e4d5dd6dc2641e2dd7019e4c592f11)
- Decider: none (fallback confidence)
- Ontology constraints/hints: True (ezhuthu.ontology.lookup)
- Command: `python -m ezhuthu.eval.run --router baseline-copy --split test --no-decider`

| subset | n | top-1 | top-20 | CER (mean) | CER (clipped 1.0) | CER (median) | ECE | abstain |
|---|---|---|---|---|---|---|---|---|
| full | 413 | 0.4165 | 0.5569 | 0.4736 | 0.4494 | 0.5 | 0.0734 | 0.0315 |
| hard | 317 | 0.3407 | 0.4795 | 0.5505 | 0.5221 | 0.5 | 0.072 | 0.041 |
| age | 51 | 0.2745 | 0.4706 | 0.6286 | 0.5501 | 0.5385 | 0.2164 | 0.0784 |

Coverage-accuracy (full):

| threshold | coverage | accuracy |
|---|---|---|
| 0.0 | 1.0 | 0.4165 |
| 0.3 | 0.6901 | 0.5439 |
| 0.5 | 0.2615 | 0.7037 |
| 0.6 | 0.1477 | 0.8033 |
| 0.7 | 0.0872 | 0.7778 |
| 0.8 | 0.0412 | 0.7647 |
| 0.9 | 0.0242 | 0.7 |
