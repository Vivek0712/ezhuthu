# ezhuthu.agent: restoration engine and tutor

Built with Strands Agents. Model IDs come only from `config/models.yaml`.

## Restoration (`restorer.py`)

For each `[?]` / `[?N]` gap:

1. `retrieve_parallels`: BM25 over character 3-grams of `benchmark/corpus_lines.jsonl` (train lines), re-ranked by
   exact anchor length and rapidfuzz; each parallel also yields the text aligned with the gap.
2. Candidates (deduplicated): fills aligned in the top 5 parallels; the **copy floor** (the copy baseline's top-1:
   the best-scoring parallel fill within the length tolerance, searched over `restorer.parallels_k` = 20 parallels);
   ontology completions (the ontology is reached over MCP, see "Ontology" below; an entity that starts in the left
   context and runs into the gap); the character 5-gram's top `ngram_k`; and `propose_fills` (a Strands `Agent` on
   Bedrock, `llm.py`). Each candidate carries its evidence as features (`llm_probability`, `best_parallel_match`,
   `parallel_support`, `copy_baseline`, `ngram_rank`, `prerank`), returned under `candidates[].features`.
   `propose_fills` asks for `restorer.llm_candidates` (8) fills as one line of compact JSON
   (`{"fills": [["<gap text>", p], ...]}`) with an output budget that scales with k x gap length (capped at
   `restorer.llm_max_tokens`); a reply cut at max_tokens keeps every complete fill that arrived and is re-asked once
   with a stricter, shorter prompt (`retry_on_truncation`).
3. `check_constraints`: drops candidates with non-ISO characters or Grantha letters in early-Tamil contexts,
   flags length outside `max(2, 34%)` of `[?N]`. **Every gap length is in Tamil letters** (uyir, mey, uyirmey;
   `text.akshara_len`, the benchmark's own counter): `[?N]`/`gap_chars`, the length check, the copy floor and copy
   baseline, the n-gram fill length, the one-anchor alignment window, the unknown-length estimate and the LLM prompt
   ("about N Tamil letters"). Before issue #26 the checks counted ISO characters and 130/443 VAL expert targets
   failed them.
4. Pre-rank (cheap, no model call): `prerank = 1 - (1 - llm_probability) x (1 - parallel support)`, halved for a
   length mismatch, small epsilons for ontology and n-gram proposals.
5. `rank_and_decide`, by `restorer.strategy` for retrieval-only gaps and `restorer.strategy_llm` once an LLM
   answered (config/models.yaml; both chosen on VAL in issue #26, see below); `eval.run --strategy/--top-k` and
   `EZHUTHU_RESTORER_STRATEGY` set both:

   | strategy | decider calls | confidence |
   |---|---|---|
   | `choice-all` | 1 `choice` over up to 23 candidates + `none` (pre-#22 behaviour) | option probability |
   | `choice-topk` | 1 `choice` over the top `top_k` + `none`; the copy floor always gets a slot | option probability |
   | `noul-topk` | `top_k` `noul` calls ("is this the restoration?") | P(yes) per candidate |
   | `prerank` | none | the pre-rank score |
   | `self-report` | none | LLM fills: the LLM's own probability; other candidates: parallel agreement |

   Shipped (chosen on VAL by highest top-1, `eval/reports/2026-11-02-val-selection.md`): `self-report` for
   retrieval-only gaps (the parallel-agreement heuristic; full VAL n=443: 0.2619 vs prerank 0.2551, not a
   significant difference) and `noul-topk` with `top_k` 3 once an LLM answered (Sonnet pools on a 120-item VAL
   sample: 0.1917 vs self-report 0.1167, prerank 0.15, choice-top3 0.1667). Without a reachable decider (the cloud
   runtime today) LLM gaps fall back to `self-report`. The TEST result of each choice is in
   `eval/reports/2026-11-02-test-eval.md`.

   Then **calibration**: the confidences of the active variant
   (`<decider model>|<strategy>|k<k>|<llm-sonnet|llm-opus|retrieval>`; `llm-opus` whenever Opus answered, alone or
   after Sonnet) go through the Platt parameters fitted on the **VAL split** (`calibration.json` next to this README,
   written by `python -m ezhuthu.eval.calibrate`, which refuses any other split), and the gap abstains under that
   variant's own fitted threshold. A variant with no calibration keeps raw confidences and
   `routing.abstain_if_confidence_below`. **Minimum-sample guard:** an entry fitted on fewer than
   `restorer.calibration_min_n` (100) VAL items or `calibration_min_positives` (10) correct top-1s is provisional:
   it stays in the file but is not used. Since issue #26 every entry has n >= 100: retrieval-only entries on full VAL
   (n=443), `|llm-sonnet` entries on 120 VAL gaps and the `noul-topk|k3|llm-opus` entry on the 100 VAL gaps where
   Opus answered (`python -m ezhuthu.eval.full_eval decide`). A fallback (no decider) LLM gap has no entry and keeps
   raw confidences and the 0.5 threshold.
   Gaps report `strategy`, `calibration` (the key used, or null) and `abstain_below`. If the decider is unreachable
   or refuses the request, the confidence falls back to the LLM's self-report (or a retrieval heuristic),
   `decider_model` says `fallback:...` and each candidate's `decider_source` says `fallback`.
6. Router (`config/models.yaml` `routing`): `routed` starts on `llm.default` (Sonnet 4.6); it goes straight to
   `llm.escalate` (Opus 4.6) when the gap is over 12 letters or there is no good parallel, and escalates
   after Sonnet when the best **raw** confidence is under `escalate_if_confidence_below` (0.6). The threshold is on
   the raw scale; a calibrated score (fitted for fill/abstain) is never compared with it. 0.6 was kept on VAL (issue
   #26): on the 120-item VAL sample 96 gaps pre-escalate and 4 more escalate after Sonnet, so 100/120 use Opus;
   higher thresholds bought one more matching gap for 13-20 more Opus calls. Cost and latency on TEST:
   `eval/reports/2026-11-02-test-eval.md`.

Bedrock robustness (`llm.py`): Strands' built-in throttling retry (fixed doubling, no jitter) is off; `complete`
retries throttling and transient faults with exponential backoff and full jitter (5 attempts, base 2 s, cap 30 s)
behind a process-wide rate limiter (`EZHUTHU_LLM_RPM`, or `--rpm` on the eval CLIs). The account's on-demand
quotas (heisenberg, us-east-1 cross-region, 2026-11-02) are **10 requests/min for Sonnet 4.6 and 5 for Opus 4.6**;
`ezhuthu.eval.full_eval` paces each model at its quota (`PacedBedrockLLM`). `BudgetedLLM`
(`--max-live-calls`) hard-caps uncached calls in eval runs.

`tools.py` exposes the same steps as Strands `@tool`s and `build_restorer_agent()` builds an agentic Restorer.
Baselines (`baselines.py`): copy-from-best-parallel, character n-gram, zero-shot LLM.

## Ontology (`ontology_port.py`, `ontology_mcp.py`)

`get_ontology()` starts `python -m ezhuthu.ontology.mcp_server` as a stdio subprocess of the same interpreter and
talks to it with a Strands `MCPClient` (`McpOntology`). `build_restorer_agent()` also gives the agentic Restorer the
server's tools (`find_entities`, `valid_letters`, `formulas_for`, `entity`, `hints_for_gap`) from that session.
The in-process `ezhuthu.ontology.lookup` API is only an offline fallback and is flagged in `/health` `ontology`:
`EZHUTHU_ONTOLOGY=direct` gives `direct:ezhuthu.ontology.lookup`, a failed MCP start gives
`fallback:direct (mcp unavailable)`. If the server process dies later, the next call restarts it once and retries;
if it stays dead, the same instance answers from the direct API and `/health` shows `fallback:direct (mcp died)`.
`EZHUTHU_ONTOLOGY=stub` (or `EZHUTHU_FIXTURES=1` with no mode) uses the
fixture stub. Runtime needs: `ontology/COA.md` section 3.

## Tutor (`tutor/`)

A Strands **Graph**: `restore` -> `lesson_builder` -> `tutor_team`, where `tutor_team` is a Strands **Swarm**
(Tutor + Assessor agents) that writes the explanation from the lesson facts only. Offline (no live LLM), the
Graph routes to `explain_template` instead.

`EZHUTHU_LESSON_EXPLAIN=async` (default, issue #22): the Graph ends at `explain_template` so `/api/lesson` answers in
well under a second for a gap-free inscription (measured 0.66 s cold / 0.04-0.08 s warm vs 35.3 s / 16.1 s with the
Swarm inline, `eval/reports/2026-11-02-restorer-quality-dev-note.md`), with `context.explanation_status: "pending"`.
The same Swarm then runs in a background thread (the AgentCore app reports HealthyBusy meanwhile); its explanation
is returned once as `context_update` on the next `/api/answer`, and later lessons on the same facts get it directly
(`explained_by: "tutor_team-cached"`). Delivery is **best effort**: `context_update` arrives only if that lesson
is still the session's latest when an `/api/answer` comes in after the Swarm finished (a newer `/api/lesson`
supersedes it), and the
explanation lives in a per-process LRU, so a recycled microVM / restarted process loses it (the learner keeps the
template explanation). The latency figures above are for a lesson whose inscription has 0 gaps; a lesson with gaps
still pays for restoration on its first request (pre-restoring lesson inscriptions offline is the planned
follow-up). Restored inscriptions are cached per text in-process, so repeat lessons skip
restoration (`graph.restoration_cached`). `EZHUTHU_LESSON_EXPLAIN=sync` restores the inline Swarm. When the pedagogy
decision comes from the rules (`decider_source: "rules"`), `decider_confidence` is `null`. `/api/answer` grades the reading, then the decider chooses
`advance | repeat | hint` with rule guardrails (`tutor/policy.py`); pre/post tests never hint or reveal.

Levels: L1 modern Tamil, L2 Chola orthography (no e/ē, o/ō contrast, no pulli), L3 Grantha (Noto Sans Grantha),
L4 Vatteluttu (`glyph_svg: "vatteluttu:<iso>"`, the app draws it), L5 Tamil-Brahmi (Noto Sans Brahmi).

## Decider backends (`decider.py`)

`EZHUTHU_DECIDER_BACKEND` = `local` (default) | `hosted` | `fallback`.

| backend | endpoint | model | notes |
|---|---|---|---|
| `local` | `POST {EZHUTHU_DECIDER_URL}/v1/systemone` (`strands-decider serve`) | v1-2610 (`decider.fast` / `decider.local`) | evaluation and laptop dev |
| `hosted` | `POST {decider.cloud.url}/v1/decide`, bearer key | `decider.cloud.model` (`strands-decider-2b-hobson-v19`) | cloud runtime; key from `$EZHUTHU_DECIDER_API_KEY` or Secrets Manager `decider.cloud.secret_name` |
| `fallback` | none | none | LLM self-report (restoration) and rules (pedagogy) |

The hosted client paces itself to `decider.cloud.rpm` (free tier 10/min), retries 429/503 once after
`Retry-After` (seconds or an HTTP date; anything unparseable waits 5 s, capped at 20 s), treats
401/402/403/413/422 as "unavailable" (flagged fallback) and never logs the key. Any unusable reply (non-JSON
body, missing `answers[<name>]`, non-numeric probabilities) is also "unavailable", for the local backend too, so
`/restore` and the tutor never 500 on a decider fault. The pacing is **per process**: several AgentCore sessions
(or the API plus a benchmark run) share one key and together can exceed 10/min. The server then answers 429, the
client retries once, and if that is refused too the request uses the flagged fallback, so it fails safe but
loses the decider for that call. On the
free tier a request may be at most 8,000 characters (state + questions, JSON with ASCII escapes, so ISO-15919
diacritics count 6 each); `decider.cloud.max_input_chars` makes the client drop tail candidates (never `none`) to
fit; candidates dropped that way get confidence 0 with `confidence_source: decider-trimmed` (the decider never
saw them), and those beyond the 23 decider slots get `decider-overflow`. Outputs carry `decider_model` and `decider_source` (`hosted` | `local` | `fallback`; tutor answers also carry
`decider_backend`). Benchmark of the backends: `python -m ezhuthu.eval.decider_bench` and
`eval/reports/*-decider-benchmark.md`.

## Running

```bash
make setup && make check                                    # offline, uses fixtures until benchmark/ lands
.venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --device mps --port 8765
EZHUTHU_DECIDER_URL=http://127.0.0.1:8765 .venv/bin/uvicorn ezhuthu.api.app:app --port 8080
EZHUTHU_LIVE=1 python -m ezhuthu.eval.run --split test --limit 300 --router routed   # live, cached in .cache/
python -m ezhuthu.eval.run --split val --router none --strategy choice-topk --top-k 3       # compare variants
python -m ezhuthu.eval.calibrate --split val --router none --no-ontology                    # fit calibration.json (VAL only)
python -m ezhuthu.agentcore_app                             # AgentCore runtime locally on :8080
```

Environment: `EZHUTHU_LIVE=1` (allow Bedrock), `EZHUTHU_DECIDER_BACKEND=local|hosted|fallback`,
`EZHUTHU_DECIDER_URL` (local), `EZHUTHU_DECIDER_API_KEY` or the Secrets Manager secret (hosted),
`EZHUTHU_DECIDER_CLOUD_URL` (override), `EZHUTHU_DECIDER=off`,
`EZHUTHU_ONTOLOGY=mcp|direct|stub` (default `mcp`), `EZHUTHU_ONTOLOGY_ROOT` (ontology build dir for the MCP server),
`EZHUTHU_STORE=memory|sqlite:<path>|dynamodb:<table>|dynamodb` (bare `dynamodb` reads `EZHUTHU_TABLE`),
`EZHUTHU_LESSON_EXPLAIN=async|sync`, `EZHUTHU_LLM_RPM`, `EZHUTHU_CALIBRATION=<path>|none`, `EZHUTHU_RESTORER_STRATEGY` (overrides `restorer.strategy`), `EZHUTHU_BENCHMARK_DIR`, `EZHUTHU_FIXTURES=1`,
`EZHUTHU_CONFIG` (path to models.yaml when the bundle is not a checkout).

## AgentCore invoke shape

`POST /invocations` body `{"action": "<name>", ...fields of the matching endpoint}`; the response is that
endpoint's JSON body, or `{"error": {"status": 404|422|500, "detail": "..."}}`.

| action | fields | HTTP equivalent |
|---|---|---|
| `restore` | `text`, `script?`, `max_candidates?`, `allow_escalation?` | `POST /api/restore` |
| `lesson` | `inscription_id?`, `text?`, `level`, `lang?`, `session_id?` | `POST /api/lesson` |
| `answer` | `session_id`, `item_id`, `answer` | `POST /api/answer` |
| `assessment` | `session_id?`, `phase` | `POST /api/assessment` |
| `progress` | `session_id` | `GET /api/progress/{id}` |
| `evaluate` | `benchmark?`, `limit?`, `router?`, `records?` | `POST /api/evaluate` |
| `corrections` | `gap_ref`, `accepted_candidate?`, `corrected_text?`, `user?` | `POST /api/corrections` |
| `queue` | none | `GET /api/queue` |
| `review` | `id`, `review_action` (approve/edit/reject), `text?` | `POST /api/queue/{id}` |
| `health` | none | `GET /health` |

The runtime needs `config/models.yaml` in the bundle (or `EZHUTHU_CONFIG`), `EZHUTHU_LIVE=1`,
`EZHUTHU_STORE=dynamodb` with `EZHUTHU_TABLE` (the deployed EzhuthuData table, `infra/lib/data-stack.ts`: `pk` +
`sk`, GSI `gsi1` = `gsi1pk`/`gsi1sk`, TTL `ttl`; sessions are `SESSION#<id>`/`STATE` next to the proxy's
`SESSION#<id>`/`META`, corrections `CORRECTION#<id>`/`ITEM`, review queue `QUEUE#<id>`/`ITEM` with
`gsi1pk = STATUS#<status>` exactly as the proxy writes it; `tests/agent/test_dynamo_store.py` checks this against the
CDK source), Bedrock
invoke permission for the two model IDs, and for the hosted decider `EZHUTHU_DECIDER_BACKEND=hosted` plus
`secretsmanager:GetSecretValue` on `ezhuthu/decider-api-key`. Without a decider, confidences use the flagged
fallback.
