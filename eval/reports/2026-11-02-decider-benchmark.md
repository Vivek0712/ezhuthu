# Decider benchmark: hosted vs local Strands Decider vs LLM self-confidence

> **Measured before issue #26** (gap lengths counted in Tamil letters): the decider saw `length_matches_gap` and `gap_length_chars` computed on ISO characters, and the candidate set is from before the truncation fix. Not re-run in issue #26. Kept as is; the full TEST evaluation with the letter-count fix is [`2026-11-02-test-eval.md`](2026-11-02-test-eval.md) (local 2B decider only; the hosted v19 decider was not part of it).

- Date: 2026-11-02T03:26:13+00:00
- Task: restoration `rank_and_decide` on 60 items (test/hard, first 60), one fixed candidate set for every decider (`2026-11-02-decider-benchmark-candidates.jsonl`, sha256 `ab00901f055d`).
- Candidates: us.anthropic.claude-sonnet-4-6 (router `sonnet`, no escalation) + retrieval parallels + character n-gram; ontology off; 60 items have candidates, mean 19.97 candidates per item.
- Abstain threshold: confidence < 0.5 (`routing.abstain_if_confidence_below`).
- Decider request size (state + questions incl. instructions, JSON with ASCII escapes, as decider-cloud counts it): median 6560.5, p95 9280.8, max 9660 characters; 19 of 60 over the 8000-character free-tier limit.
- Per-item rows: `2026-11-02-decider-benchmark/` next to this report (restoration-<label>.jsonl, policy-<label>.jsonl).

## Restoration (same items, same candidates)

| decider | model | N | errors | top-1 | top-1 when target is a candidate | ECE | abstain rate | selective accuracy (n) | latency p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| hosted-v19-top3 | `strands-decider-2b-hobson-v19` | 60 | 0 | 0.450 | 0.771 | 0.158 | 0.833 | 0.500 (10) | 4827 / 6832 |
| hosted-v19-cap24 | `strands-decider-2b-hobson-v19` | 60 | 43 | 0.133 | 0.229 | 0.072 | 0.967 | 0.500 (2) | 9610 / 12794 |
| 2b | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | 60 | 1 | 0.217 | 0.371 | 0.075 | 1.000 | - (0) | 1784 / 2567 |
| 2b-fit8k | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | 60 | 0 | 0.217 | 0.371 | 0.061 | 1.000 | - (0) | 1798 / 2286 |
| e4b | `StrandsAgents/strands-decider-E4B-gemma4-v1-2610` | 16 (partial) | 0 | 0.188 | 0.300 | 0.053 | 1.000 | - (0) | 69816 / 81876 |
| fallback | `fallback:llm-self-report` | 60 | 0 | 0.400 | 0.686 | 0.186 | 0.450 | 0.667 (33) | - / - |

Target among the candidates (ceiling for any decider): 0.583.

Coverage / accuracy if the abstain threshold were moved (confidence >= t):

| decider | t=0.1 | t=0.2 | t=0.3 | t=0.4 | t=0.5 | t=0.7 |
|---|---|---|---|---|---|---|
| hosted-v19-top3 | 1.000 / 0.450 | 0.750 / 0.533 | 0.517 / 0.581 | 0.283 / 0.588 | 0.167 / 0.500 | 0.033 / 0.500 |
| hosted-v19-cap24 | 0.250 / 0.533 | 0.183 / 0.636 | 0.133 / 0.625 | 0.133 / 0.625 | 0.033 / 0.500 | 0.017 / 0.000 |
| 2b | 0.900 / 0.241 | 0.400 / 0.292 | 0.083 / 0.600 | 0.017 / 0.000 | 0.000 / - | 0.000 / - |
| 2b-fit8k | 0.950 / 0.228 | 0.417 / 0.280 | 0.100 / 0.500 | 0.017 / 0.000 | 0.000 / - | 0.000 / - |
| e4b | 0.625 / 0.200 | 0.250 / 0.250 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| fallback | 1.000 / 0.400 | 0.917 / 0.436 | 0.850 / 0.471 | 0.650 / 0.590 | 0.550 / 0.667 | 0.450 / 0.741 |

Paired comparison on the items both scored (exact McNemar on the discordant items; *different pick* counts items where the chosen fill differs, right or wrong):

| pair | N | both right | only first right | only second right | McNemar p | different pick |
|---|---|---|---|---|---|---|
| hosted-v19-top3 vs hosted-v19-cap24 | 60 | 7 | 20 | 1 | 0.000 | 45 |
| hosted-v19-top3 vs 2b | 60 | 11 | 16 | 2 | 0.001 | 42 |
| hosted-v19-top3 vs 2b-fit8k | 60 | 11 | 16 | 2 | 0.001 | 42 |
| hosted-v19-top3 vs e4b | 16 | 3 | 6 | 0 | 0.031 | 12 |
| hosted-v19-top3 vs fallback | 60 | 24 | 3 | 0 | 0.250 | 6 |
| hosted-v19-cap24 vs 2b | 60 | 7 | 1 | 6 | 0.125 | 47 |
| hosted-v19-cap24 vs 2b-fit8k | 60 | 7 | 1 | 6 | 0.125 | 48 |
| hosted-v19-cap24 vs e4b | 16 | 0 | 2 | 3 | 1.000 | 16 |
| hosted-v19-cap24 vs fallback | 60 | 6 | 2 | 18 | 0.000 | 48 |
| 2b vs 2b-fit8k | 60 | 13 | 0 | 0 | 1.000 | 4 |
| 2b vs e4b | 16 | 0 | 1 | 3 | 0.625 | 9 |
| 2b vs fallback | 60 | 8 | 5 | 16 | 0.027 | 47 |
| 2b-fit8k vs e4b | 16 | 0 | 1 | 3 | 0.625 | 9 |
| 2b-fit8k vs fallback | 60 | 8 | 5 | 16 | 0.027 | 47 |
| e4b vs fallback | 16 | 3 | 0 | 6 | 0.031 | 12 |

## Tutor policy (20 scripted learner states)

Reference = the rule policy (`tutor/policy.py rules`). *Raw* is the decider's choice before guardrails; *final* is after the guardrails (never drill a correct item, never loop past 3 attempts).

| decider | model | raw agrees with rules | final agrees with rules | guardrail overrides | raw choices | latency p50 / p95 ms |
|---|---|---|---|---|---|---|
| hosted-v19-top3 | not run | | | | | |
| hosted-v19-cap24 | not run | | | | | |
| 2b | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | 0.600 | 0.800 | 4 | {'advance': 5, 'hint': 15} | 167 / 218 |
| 2b-fit8k | not run | | | | | |
| e4b | not run | | | | | |
| fallback | `rules` | - | 1.000 | 0 | {} | - / - |

Per state (rules reference / raw choice per decider):

| # | correct | attempts | hint given | rules | 2b | fallback |
|---|---|---|---|---|---|---|
| 0 | True | 1 | False | advance | advance | (advance) |
| 1 | True | 2 | True | advance | advance | (advance) |
| 2 | True | 1 | False | advance | advance | (advance) |
| 3 | True | 3 | True | advance | advance | (advance) |
| 4 | True | 1 | False | advance | advance | (advance) |
| 5 | False | 1 | False | hint | hint | (hint) |
| 6 | False | 1 | False | hint | hint | (hint) |
| 7 | False | 1 | False | hint | hint | (hint) |
| 8 | False | 1 | False | hint | hint | (hint) |
| 9 | False | 1 | False | hint | hint | (hint) |
| 10 | False | 2 | True | repeat | hint | (repeat) |
| 11 | False | 2 | True | repeat | hint | (repeat) |
| 12 | False | 2 | True | repeat | hint | (repeat) |
| 13 | False | 2 | True | repeat | hint | (repeat) |
| 14 | False | 2 | False | hint | hint | (hint) |
| 15 | False | 3 | True | advance | hint | (advance) |
| 16 | False | 3 | True | advance | hint | (advance) |
| 17 | False | 3 | False | advance | hint | (advance) |
| 18 | False | 4 | True | advance | hint | (advance) |
| 19 | False | 1 | False | hint | hint | (hint) |

## Caveats

- hosted-v19-top3 (added 2026-11-02 after the key was minted): the hosted Strands Decider API given only the first 3 candidates (best-first) plus 'none', as the restorer's choice-topk strategy sends them. With all ~20 candidates the hosted model's prompt is truncated through the option list (422 'option span has no tokens left') on 43/60 items; that run is kept as hosted-v19-cap24 for the record.
- Caveat: these 60 items are the TEST hard subset frozen for this benchmark before any hosted run. Do not use this table to pick the deployed decider; the deployment choice must be confirmed on VAL.
