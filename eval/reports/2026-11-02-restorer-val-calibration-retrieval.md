# Dev-set note: restorer decider variants and calibration (val split)

> **SUPERSEDED (issue #26, 2026-11-02).** Measured before gap lengths were counted in Tamil letters: the length check, copy floor, copy baseline, n-gram fill length and LLM prompt counted ISO characters against a letter count (130/443 VAL targets failed the length check). Ontology was off. Kept unchanged below as history; do not cite these numbers. Current numbers: [`2026-11-02-val-selection.md`](2026-11-02-val-selection.md) and [`2026-11-02-restorer-val-retrieval-aksharas.md`](2026-11-02-restorer-val-retrieval-aksharas.md).

> **VAL split only (development data).** Calibration is fitted on these items; the in-sample columns are optimistic, the cv5 columns are 5-fold cross-validated within VAL. Not a test-set result; do not cite as restoration quality.

- Date: 2026-11-01T23:46:36+00:00
- Items: 443 (val/full, limit None)
- Router: `none`; ontology: off; decider: strands-decider-2B-qwen3.5-v1-2610
- Data: `benchmark` (last data commit 20584c8)
- Code: 575f3ab
- Provenance note: Provenance corrected (QA on PR #25): the original data_commit field held the checkout HEAD 585bbad, but these numbers came from the uncommitted copy-floor pre-rank fix later committed as 575f3ab. data_commit is now the last commit touching benchmark/. Re-running the prerank and fallback variants at 575f3ab (router none, no Bedrock) on 2026-11-02 reproduced their rows exactly (prerank top-1 0.2348, fallback 0.2167); the decider variants were not re-run.
- Command: `python -m ezhuthu.eval.calibrate --split val --router none --no-ontology --name restorer-val-calibration-retrieval --note Router none: candidates are retrieval parallels (train-only corpus_lines), the copy-floor fill and the character 5-gram; no LLM, no Bedrock calls. --note Ontology off: the shipped ontology build reads val/test inscriptions (QA gotcha), so it is excluded from any eval.`

Copy baseline on the same items: top-1 0.228.

| variant | top-1 | target in candidates | vs copy (only variant / only copy) | raw mean / max top-1 conf | ECE raw | ECE cal (cv5) | fill@raw 0.5: cov / acc | fill@fitted (cv5): cov / acc | threshold | trunc / retries | p50 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| choice-all | 0.1648 | 0.3499 | 18 / 46 | 0.2648 / 0.617 | 0.1 | 0.031 | 0.0181 / 0.25 | 0.0 / - | 1.0 | 0 / 0 | 1025.1 |
| choice-topk:3 | 0.1874 | 0.3499 | 16 / 34 | 0.2978 / 0.6608 | 0.1105 | 0.0094 | 0.0293 / 0.1538 | 0.0 / - | 1.0 | 0 / 0 | 787.8 |
| choice-topk:5 | 0.1716 | 0.3499 | 18 / 43 | 0.2723 / 0.617 | 0.1008 | 0.0082 | 0.0158 / 0.2857 | 0.0 / - | 1.0 | 0 / 0 | 985.2 |
| noul-topk:3 | 0.2009 | 0.3499 | 12 / 24 | 0.5932 / 0.833 | 0.3931 | 0.0418 | 0.8623 / 0.2225 | 0.0271 / 0.5833 | 0.5609 | 0 / 0 | 1643.5 |
| prerank | 0.2348 | 0.3499 | 3 / 0 | 0.3619 / 1.0 | 0.1342 | 0.0514 | 0.1851 / 0.5244 | 0.1038 / 0.5435 | 0.4025 | 0 / 0 | 56.3 |
| fallback | 0.2167 | 0.3499 | 10 / 15 | 0.1827 / 0.7455 | 0.041 | 0.0229 | 0.0406 / 0.7778 | 0.0406 / 0.6111 | 0.675 | 0 / 0 | 55.7 |

Variant keys written to the calibration file:

- `strands-decider-2B-qwen3.5-v1-2610|choice-all|kall|retrieval`: a=1.178036, b=-0.444669, threshold=1.0 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k3|retrieval`: a=0.843488, b=-0.74249, threshold=1.0 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|choice-topk|k5|retrieval`: a=1.027207, b=-0.574342, threshold=1.0 (n=443)
- `strands-decider-2B-qwen3.5-v1-2610|noul-topk|k3|retrieval`: a=2.112848, b=-2.349079, threshold=0.5609 (n=443)
- `prerank|prerank|kall|retrieval`: a=0.83603, b=-0.747474, threshold=0.4025 (n=443)
- `fallback:retrieval-heuristic|fallback|kall|retrieval`: a=1.234968, b=0.543032, threshold=0.675 (n=443)

## Notes

- Router none: candidates are retrieval parallels (train-only corpus_lines), the copy-floor fill and the character 5-gram; no LLM, no Bedrock calls.
- Ontology off: the shipped ontology build reads val/test inscriptions (QA gotcha), so it is excluded from any eval.
