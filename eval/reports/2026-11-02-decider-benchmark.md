# Decider benchmark: hosted vs local Strands Decider vs LLM self-confidence

- Date: 2026-11-01T21:05:25+00:00
- Task: restoration `rank_and_decide` on 60 items (test/hard, first 60), one fixed candidate set for every decider (`2026-11-02-decider-benchmark-candidates.jsonl`, sha256 `ab00901f055d`).
- Candidates: us.anthropic.claude-sonnet-4-6 (router `sonnet`, no escalation) + retrieval parallels + character n-gram; ontology off; 60 items have candidates, mean 19.97 candidates per item.
- Abstain threshold: confidence < 0.5 (`routing.abstain_if_confidence_below`).
- Decider request size (state + options, JSON with ASCII escapes): median 6249.5, p95 8969.8, max 9349 characters.

## Restoration (same items, same candidates)

| decider | model | N | errors | top-1 | top-1 when target is a candidate | ECE | abstain rate | selective accuracy (n) | latency p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|---|
| hosted-v19 | not run | | | | | | | | |
| 2b | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | 60 | 1 | 0.217 | 0.371 | 0.075 | 1.000 | - (0) | 1784 / 2567 |
| 2b-fit8k | `StrandsAgents/strands-decider-2B-qwen3.5-v1-2610` | 60 | 0 | 0.217 | 0.371 | 0.061 | 1.000 | - (0) | 1798 / 2286 |
| e4b | not run | | | | | | | | |
| fallback | `fallback:llm-self-report` | 60 | 0 | 0.400 | 0.686 | 0.186 | 0.450 | 0.667 (33) | - / - |

Target among the candidates (ceiling for any decider): 0.583.

Coverage / accuracy if the abstain threshold were moved (confidence >= t):

| decider | t=0.1 | t=0.2 | t=0.3 | t=0.4 | t=0.5 | t=0.7 |
|---|---|---|---|---|---|---|
| 2b | 0.900 / 0.241 | 0.400 / 0.292 | 0.083 / 0.600 | 0.017 / 0.000 | 0.000 / - | 0.000 / - |
| 2b-fit8k | 0.950 / 0.228 | 0.417 / 0.280 | 0.100 / 0.500 | 0.017 / 0.000 | 0.000 / - | 0.000 / - |
| fallback | 1.000 / 0.400 | 0.917 / 0.436 | 0.850 / 0.471 | 0.650 / 0.590 | 0.550 / 0.667 | 0.450 / 0.741 |

## Tutor policy (20 scripted learner states)

Reference = the rule policy (`tutor/policy.py rules`). *Raw* is the decider's choice before guardrails; *final* is after the guardrails (never drill a correct item, never loop past 3 attempts).

| decider | model | raw agrees with rules | final agrees with rules | guardrail overrides | raw choices | latency p50 / p95 ms |
|---|---|---|---|---|---|---|
| hosted-v19 | not run | | | | | |
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

- hosted-v19 (strands-decider-2b-hobson-v19 on https://da25tnxy06gjk.cloudfront.net) NOT RUN: the 'ezhuthu' API key was not minted. The documented path is POST /platform/v1/users with the platform token from Secrets Manager dcloud-staging/app; the session's permission policy denied reading that token, so no key exists and Secrets Manager ezhuthu/decider-api-key was not created. 0 hosted calls were made. After the key exists: python -m ezhuthu.eval.decider_bench score --cands eval/reports/2026-11-02-decider-benchmark-candidates.jsonl --decider hosted --label hosted-v19 (and policy --decider hosted --label hosted-v19); at 10 rpm that is about 8 minutes and 80 decisions of the 2,000/month free quota.
- e4b (StrandsAgents/strands-decider-E4B-gemma4-v1-2610) NOT RUN: not a load failure. Its LoRA/head were cached but the base weights google/gemma-4-E4B-it (bf16) were not; strands-decider serve --device mps started the download at 02:27 IST at about 8 MB/s and it had not finished when the time box ran out. Whether it fits in 24 GB on mps is untested. mlx was not tried (the mlx extra is not installed).
- N = 60 (the first 60 test-hard items, 14 inscriptions from 3 collections; items within an inscription are correlated). Paired exact McNemar, fallback vs 2b: 16 items only the fallback got right, 5 only the 2b got right, p = 0.027. 2b vs 2b-fit8k: identical top-1 on every item.
- Candidates were frozen once: restorer pipeline with router sonnet (us.anthropic.claude-sonnet-4-6, no Opus escalation), retrieval parallels from train-only corpus_lines, character 5-gram, ontology OFF (QA found the ontology build reads val/test inscriptions). LLM output budget 2,048 tokens (the pipeline's 800 truncates; see the quick live eval). 60 Sonnet calls, 0 errors, estimated USD 0.73. The target is among the candidates on 58.3% of items, which caps every decider.
- fallback = the restorer's own flagged fallback on the same candidates: Sonnet's self-reported confidence, else the retrieval heuristic. Sonnet produced those confidences together with the candidates, so this is Sonnet ranking its own list. For the tutor policy, fallback = the rule policy, which is also the reference, so it agrees 100% by construction.
- The 2b abstains on 100% of items at the configured threshold (0.5): the restorer uses each option's raw probability over up to 24 options (mean top confidence 0.19), and 0.5 was not calibrated for the decider. Selective accuracy at 0.5 is therefore undefined for the 2b; the coverage table shows other thresholds. Its low ECE reflects uniformly low confidence plus low accuracy, not useful calibration.
- 2b: 1 of 60 requests returned 422 from strands-decider serve (the prompt exceeded the 4,096-token window and truncated the option list); in production that gap silently uses the fallback. 2b-fit8k sends the same requests trimmed to the hosted free tier's 8,000-character limit (tail candidates dropped, never 'none'; 19 items trimmed) and had no errors; this is what the hosted backend would send on the free tier.
- Latency: wall time per decider request, sequential, local strands-decider serve on an Apple M4 Pro (mps, 24 GB) while another 2B server from a different worktree was also resident. Hosted latency would add network and queueing.
- Tutor policy: the reference is the existing rule policy, not ground truth about learning; 'raw' is the decider's choice before guardrails (in parentheses: the final action when no decider ran).
