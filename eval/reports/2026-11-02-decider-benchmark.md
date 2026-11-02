# Decider benchmark: hosted vs local Strands Decider vs LLM self-confidence

> **Measured before issue #26** (gap lengths counted in Tamil letters): the decider saw `length_matches_gap` and `gap_length_chars` computed on ISO characters, and the candidate set is from before the truncation fix. Not re-run in issue #26. Kept as is; the full TEST evaluation with the letter-count fix is [`2026-11-02-test-eval.md`](2026-11-02-test-eval.md) (local 2B decider only; the hosted v19 decider was not part of it).

- Date: 2026-11-02T04:45:16+00:00
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
| sparrow-nano | `sparrow-nano-general-v1.1` | 60 | 0 | 0.017 | 0.029 | 0.018 | 1.000 | - (0) | 4 / 6 |
| sparrow-nano-top3 | `sparrow-nano-general-v1.1` | 60 | 0 | 0.150 | 0.257 | 0.066 | 1.000 | - (0) | 1.500 / 2 |
| sparrow-micro | `sparrow-micro-general-v1.1` | 60 | 0 | 0.000 | 0.000 | 0.044 | 1.000 | - (0) | 5 / 7 |
| sparrow-micro-top3 | `sparrow-micro-general-v1.1` | 60 | 0 | 0.200 | 0.343 | 0.175 | 1.000 | - (0) | 2 / 3 |
| sparrow-tiny | `sparrow-tiny-general-v1.0` | 60 | 0 | 0.033 | 0.057 | 0.071 | 1.000 | - (0) | 209 / 246 |
| sparrow-tiny-top3 | `sparrow-tiny-general-v1.0` | 60 | 0 | 0.067 | 0.114 | 0.265 | 1.000 | - (0) | 205 / 247 |
| sparrow-small | `sparrow-small-general-v1.0` | 60 | 0 | 0.167 | 0.286 | 0.108 | 1.000 | - (0) | 636 / 964 |
| sparrow-small-top3 | `sparrow-small-general-v1.0` | 60 | 0 | 0.050 | 0.086 | 0.274 | 1.000 | - (0) | 477 / 583 |

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
| sparrow-nano | 0.033 / 0.000 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-nano-top3 | 0.500 / 0.133 | 0.033 / 0.000 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-micro | 0.033 / 0.000 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-micro-top3 | 0.250 / 0.067 | 0.083 / 0.000 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-tiny | 0.250 / 0.067 | 0.033 / 0.500 | 0.000 / - | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-tiny-top3 | 1.000 / 0.067 | 1.000 / 0.067 | 0.783 / 0.064 | 0.033 / 0.000 | 0.000 / - | 0.000 / - |
| sparrow-small | 0.100 / 0.167 | 0.017 / 0.000 | 0.017 / 0.000 | 0.000 / - | 0.000 / - | 0.000 / - |
| sparrow-small-top3 | 1.000 / 0.050 | 1.000 / 0.050 | 0.750 / 0.067 | 0.033 / 0.000 | 0.000 / - | 0.000 / - |

Paired comparison on the items both scored (exact McNemar on the discordant items; *different pick* counts items where the chosen fill differs, right or wrong):

| pair | N | both right | only first right | only second right | McNemar p | different pick |
|---|---|---|---|---|---|---|
| hosted-v19-top3 vs hosted-v19-cap24 | 60 | 7 | 20 | 1 | 0.000 | 45 |
| hosted-v19-top3 vs 2b | 60 | 11 | 16 | 2 | 0.001 | 42 |
| hosted-v19-top3 vs 2b-fit8k | 60 | 11 | 16 | 2 | 0.001 | 42 |
| hosted-v19-top3 vs e4b | 16 | 3 | 6 | 0 | 0.031 | 12 |
| hosted-v19-top3 vs fallback | 60 | 24 | 3 | 0 | 0.250 | 6 |
| hosted-v19-top3 vs sparrow-nano | 60 | 0 | 27 | 1 | 0.000 | 60 |
| hosted-v19-top3 vs sparrow-nano-top3 | 60 | 8 | 19 | 1 | 0.000 | 46 |
| hosted-v19-top3 vs sparrow-micro | 60 | 0 | 27 | 0 | 0.000 | 58 |
| hosted-v19-top3 vs sparrow-micro-top3 | 60 | 12 | 15 | 0 | 0.000 | 35 |
| hosted-v19-top3 vs sparrow-tiny | 60 | 0 | 27 | 2 | 0.000 | 59 |
| hosted-v19-top3 vs sparrow-tiny-top3 | 60 | 3 | 24 | 1 | 0.000 | 56 |
| hosted-v19-top3 vs sparrow-small | 60 | 10 | 17 | 0 | 0.000 | 40 |
| hosted-v19-top3 vs sparrow-small-top3 | 60 | 2 | 25 | 1 | 0.000 | 55 |
| hosted-v19-cap24 vs 2b | 60 | 7 | 1 | 6 | 0.125 | 47 |
| hosted-v19-cap24 vs 2b-fit8k | 60 | 7 | 1 | 6 | 0.125 | 48 |
| hosted-v19-cap24 vs e4b | 16 | 0 | 2 | 3 | 1.000 | 16 |
| hosted-v19-cap24 vs fallback | 60 | 6 | 2 | 18 | 0.000 | 48 |
| hosted-v19-cap24 vs sparrow-nano | 60 | 0 | 8 | 1 | 0.039 | 60 |
| hosted-v19-cap24 vs sparrow-nano-top3 | 60 | 3 | 5 | 6 | 1.000 | 55 |
| hosted-v19-cap24 vs sparrow-micro | 60 | 0 | 8 | 0 | 0.008 | 59 |
| hosted-v19-cap24 vs sparrow-micro-top3 | 60 | 3 | 5 | 9 | 0.424 | 55 |
| hosted-v19-cap24 vs sparrow-tiny | 60 | 1 | 7 | 1 | 0.070 | 58 |
| hosted-v19-cap24 vs sparrow-tiny-top3 | 60 | 0 | 8 | 4 | 0.388 | 60 |
| hosted-v19-cap24 vs sparrow-small | 60 | 2 | 6 | 8 | 0.790 | 56 |
| hosted-v19-cap24 vs sparrow-small-top3 | 60 | 1 | 7 | 2 | 0.180 | 58 |
| 2b vs 2b-fit8k | 60 | 13 | 0 | 0 | 1.000 | 4 |
| 2b vs e4b | 16 | 0 | 1 | 3 | 0.625 | 9 |
| 2b vs fallback | 60 | 8 | 5 | 16 | 0.027 | 47 |
| 2b vs sparrow-nano | 60 | 0 | 13 | 1 | 0.002 | 58 |
| 2b vs sparrow-nano-top3 | 60 | 5 | 8 | 4 | 0.388 | 45 |
| 2b vs sparrow-micro | 60 | 0 | 13 | 0 | 0.000 | 58 |
| 2b vs sparrow-micro-top3 | 60 | 3 | 10 | 9 | 1.000 | 48 |
| 2b vs sparrow-tiny | 60 | 1 | 12 | 1 | 0.003 | 57 |
| 2b vs sparrow-tiny-top3 | 60 | 2 | 11 | 2 | 0.022 | 50 |
| 2b vs sparrow-small | 60 | 3 | 10 | 7 | 0.629 | 55 |
| 2b vs sparrow-small-top3 | 60 | 2 | 11 | 1 | 0.006 | 48 |
| 2b-fit8k vs e4b | 16 | 0 | 1 | 3 | 0.625 | 9 |
| 2b-fit8k vs fallback | 60 | 8 | 5 | 16 | 0.027 | 47 |
| 2b-fit8k vs sparrow-nano | 60 | 0 | 13 | 1 | 0.002 | 58 |
| 2b-fit8k vs sparrow-nano-top3 | 60 | 5 | 8 | 4 | 0.388 | 46 |
| 2b-fit8k vs sparrow-micro | 60 | 0 | 13 | 0 | 0.000 | 58 |
| 2b-fit8k vs sparrow-micro-top3 | 60 | 3 | 10 | 9 | 1.000 | 49 |
| 2b-fit8k vs sparrow-tiny | 60 | 1 | 12 | 1 | 0.003 | 57 |
| 2b-fit8k vs sparrow-tiny-top3 | 60 | 2 | 11 | 2 | 0.022 | 52 |
| 2b-fit8k vs sparrow-small | 60 | 3 | 10 | 7 | 0.629 | 55 |
| 2b-fit8k vs sparrow-small-top3 | 60 | 2 | 11 | 1 | 0.006 | 49 |
| e4b vs fallback | 16 | 3 | 0 | 6 | 0.031 | 12 |
| e4b vs sparrow-nano | 16 | 0 | 3 | 0 | 0.250 | 14 |
| e4b vs sparrow-nano-top3 | 16 | 0 | 3 | 2 | 1.000 | 12 |
| e4b vs sparrow-micro | 16 | 0 | 3 | 0 | 0.250 | 15 |
| e4b vs sparrow-micro-top3 | 16 | 1 | 2 | 5 | 0.453 | 12 |
| e4b vs sparrow-tiny | 16 | 0 | 3 | 0 | 0.250 | 16 |
| e4b vs sparrow-tiny-top3 | 16 | 1 | 2 | 0 | 0.500 | 11 |
| e4b vs sparrow-small | 16 | 2 | 1 | 3 | 0.625 | 14 |
| e4b vs sparrow-small-top3 | 16 | 0 | 3 | 0 | 0.250 | 12 |
| fallback vs sparrow-nano | 60 | 0 | 24 | 1 | 0.000 | 60 |
| fallback vs sparrow-nano-top3 | 60 | 7 | 17 | 2 | 0.001 | 48 |
| fallback vs sparrow-micro | 60 | 0 | 24 | 0 | 0.000 | 58 |
| fallback vs sparrow-micro-top3 | 60 | 12 | 12 | 0 | 0.001 | 32 |
| fallback vs sparrow-tiny | 60 | 0 | 24 | 2 | 0.000 | 59 |
| fallback vs sparrow-tiny-top3 | 60 | 1 | 23 | 3 | 0.000 | 59 |
| fallback vs sparrow-small | 60 | 10 | 14 | 0 | 0.000 | 39 |
| fallback vs sparrow-small-top3 | 60 | 0 | 24 | 3 | 0.000 | 59 |
| sparrow-nano vs sparrow-nano-top3 | 60 | 0 | 1 | 9 | 0.021 | 59 |
| sparrow-nano vs sparrow-micro | 60 | 0 | 1 | 0 | 1.000 | 50 |
| sparrow-nano vs sparrow-micro-top3 | 60 | 0 | 1 | 12 | 0.003 | 60 |
| sparrow-nano vs sparrow-tiny | 60 | 0 | 1 | 2 | 1.000 | 53 |
| sparrow-nano vs sparrow-tiny-top3 | 60 | 0 | 1 | 4 | 0.375 | 60 |
| sparrow-nano vs sparrow-small | 60 | 0 | 1 | 10 | 0.012 | 57 |
| sparrow-nano vs sparrow-small-top3 | 60 | 0 | 1 | 3 | 0.625 | 60 |
| sparrow-nano-top3 vs sparrow-micro | 60 | 0 | 9 | 0 | 0.004 | 58 |
| sparrow-nano-top3 vs sparrow-micro-top3 | 60 | 5 | 4 | 7 | 0.549 | 35 |
| sparrow-nano-top3 vs sparrow-tiny | 60 | 1 | 8 | 1 | 0.039 | 59 |
| sparrow-nano-top3 vs sparrow-tiny-top3 | 60 | 2 | 7 | 2 | 0.180 | 31 |
| sparrow-nano-top3 vs sparrow-small | 60 | 3 | 6 | 7 | 1.000 | 56 |
| sparrow-nano-top3 vs sparrow-small-top3 | 60 | 2 | 7 | 1 | 0.070 | 29 |
| sparrow-micro vs sparrow-micro-top3 | 60 | 0 | 0 | 12 | 0.001 | 54 |
| sparrow-micro vs sparrow-tiny | 60 | 0 | 0 | 2 | 0.500 | 59 |
| sparrow-micro vs sparrow-tiny-top3 | 60 | 0 | 0 | 4 | 0.125 | 57 |
| sparrow-micro vs sparrow-small | 60 | 0 | 0 | 10 | 0.002 | 58 |
| sparrow-micro vs sparrow-small-top3 | 60 | 0 | 0 | 3 | 0.250 | 58 |
| sparrow-micro-top3 vs sparrow-tiny | 60 | 0 | 12 | 2 | 0.013 | 60 |
| sparrow-micro-top3 vs sparrow-tiny-top3 | 60 | 0 | 12 | 4 | 0.077 | 40 |
| sparrow-micro-top3 vs sparrow-small | 60 | 4 | 8 | 6 | 0.790 | 53 |
| sparrow-micro-top3 vs sparrow-small-top3 | 60 | 0 | 12 | 3 | 0.035 | 46 |
| sparrow-tiny vs sparrow-tiny-top3 | 60 | 1 | 1 | 3 | 0.625 | 59 |
| sparrow-tiny vs sparrow-small | 60 | 0 | 2 | 10 | 0.039 | 48 |
| sparrow-tiny vs sparrow-small-top3 | 60 | 1 | 1 | 2 | 1.000 | 59 |
| sparrow-tiny-top3 vs sparrow-small | 60 | 0 | 4 | 10 | 0.180 | 60 |
| sparrow-tiny-top3 vs sparrow-small-top3 | 60 | 2 | 2 | 1 | 1.000 | 17 |
| sparrow-small vs sparrow-small-top3 | 60 | 0 | 10 | 3 | 0.092 | 59 |

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
| sparrow-nano | `sparrow-nano-general-v1.1` | 0.350 | 0.800 | 9 | {'hint': 19, 'repeat': 1} | 0.900 / 1.100 |
| sparrow-nano-top3 | not run | | | | | |
| sparrow-micro | `sparrow-micro-general-v1.1` | 0.100 | 0.450 | 7 | {'hint': 9, 'advance': 3, 'repeat': 8} | 1.400 / 2 |
| sparrow-micro-top3 | not run | | | | | |
| sparrow-tiny | `sparrow-tiny-general-v1.0` | 0.350 | 0.800 | 9 | {'hint': 19, 'repeat': 1} | 108 / 192 |
| sparrow-tiny-top3 | not run | | | | | |
| sparrow-small | `sparrow-small-general-v1.0` | 0.350 | 0.450 | 2 | {'advance': 13, 'repeat': 7} | 275 / 302 |
| sparrow-small-top3 | not run | | | | | |

Per state (rules reference / raw choice per decider):

| # | correct | attempts | hint given | rules | 2b | fallback | sparrow-nano | sparrow-micro | sparrow-tiny | sparrow-small |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | True | 1 | False | advance | advance | (advance) | hint | hint | hint | advance |
| 1 | True | 2 | True | advance | advance | (advance) | hint | hint | hint | advance |
| 2 | True | 1 | False | advance | advance | (advance) | hint | hint | hint | advance |
| 3 | True | 3 | True | advance | advance | (advance) | repeat | advance | hint | advance |
| 4 | True | 1 | False | advance | advance | (advance) | hint | hint | hint | advance |
| 5 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | advance |
| 6 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | advance |
| 7 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | repeat |
| 8 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | repeat |
| 9 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | repeat |
| 10 | False | 2 | True | repeat | hint | (repeat) | hint | hint | hint | advance |
| 11 | False | 2 | True | repeat | hint | (repeat) | hint | hint | hint | advance |
| 12 | False | 2 | True | repeat | hint | (repeat) | hint | hint | hint | advance |
| 13 | False | 2 | True | repeat | hint | (repeat) | hint | advance | hint | advance |
| 14 | False | 2 | False | hint | hint | (hint) | hint | repeat | hint | repeat |
| 15 | False | 3 | True | advance | hint | (advance) | hint | hint | hint | repeat |
| 16 | False | 3 | True | advance | hint | (advance) | hint | hint | hint | advance |
| 17 | False | 3 | False | advance | hint | (advance) | hint | repeat | hint | repeat |
| 18 | False | 4 | True | advance | hint | (advance) | hint | advance | repeat | advance |
| 19 | False | 1 | False | hint | hint | (hint) | hint | repeat | hint | repeat |

## Caveats

- hosted-v19-top3 (added 2026-11-02 after the key was minted): the hosted Strands Decider API given only the first 3 candidates (best-first) plus 'none', as the restorer's choice-topk strategy sends them. With all ~20 candidates the hosted model's prompt is truncated through the option list (422 'option span has no tokens left') on 43/60 items; that run is kept as hosted-v19-cap24 for the record.
- Caveat: these 60 items are the TEST hard subset frozen for this benchmark before any hosted run. Do not use this table to pick the deployed decider; the deployment choice must be confirmed on VAL.
- Sparrow Decider 0.2.0 (sparrow-decider/sparrow-decider, numpy; same /v1/systemone contract) served locally: nano-general-v1.1 (static embeddings from potion-base-8M / Model2Vec, MinishLab, MIT), micro-general-v1.1, tiny-general-v1.0 (Ettin-32M, JHU, MIT), small-general-v1.0 (Ettin-68M). Reference points on these items: always pick candidate 1 = 0.400; target in the top 3 = 0.483; a uniform random pick among the top 3 = 0.161. Every Sparrow restoration run is at or near random-of-top-3 and abstains on every item: their English-trained vocabularies do not cover ISO-15919 Tamil. For the tutor policy, nano and tiny reach 0.80 agreement after guardrails (same as the local 2B) at ~1 ms (nano), but raw agreement is 0.35 vs 0.60, so the guardrails do most of the work; n=20 scripted states.
