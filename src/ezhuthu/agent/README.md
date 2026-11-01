# ezhuthu.agent: restoration engine and tutor

Built with Strands Agents. Model IDs come only from `config/models.yaml`.

## Restoration (`restorer.py`)

For each `[?]` / `[?N]` gap:

1. `retrieve_parallels`: BM25 over character 3-grams of `benchmark/corpus_lines.jsonl` (train lines), re-ranked by
   exact anchor length and rapidfuzz; each parallel also yields the text aligned with the gap.
2. Candidates from parallels, ontology completions (the ontology is reached over MCP, see "Ontology" below) (an entity that starts in the left context and runs into
   the gap), a character 5-gram model, and `propose_fills` (a Strands `Agent` on Bedrock, `llm.py`).
3. `check_constraints`: drops candidates with non-ISO characters or Grantha letters in early-Tamil contexts,
   flags length outside `max(2, 34%)` of `[?N]`.
4. `rank_and_decide`: Strands Decider `choice` over the candidates plus a `none` option, via
   `POST /v1/systemone` on a local `strands-decider serve`. If the decider is unreachable the confidence falls
   back to the LLM's self-report (or a retrieval heuristic) and `decider_model` says `fallback:...`.
5. Router (`config/models.yaml` `routing`): `routed` starts on `llm.default` (Sonnet 4.6); it goes straight to
   `llm.escalate` (Opus 4.6) when the gap is over 12 characters or there is no good parallel, and escalates
   after Sonnet when the best confidence is under 0.6. Gaps under 0.5 are `abstain` ("experts are unsure").

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
Graph routes to `explain_template` instead. `/api/answer` grades the reading, then the decider chooses
`advance | repeat | hint` with rule guardrails (`tutor/policy.py`); pre/post tests never hint or reveal.

Levels: L1 modern Tamil, L2 Chola orthography (no e/ē, o/ō contrast, no pulli), L3 Grantha (Noto Sans Grantha),
L4 Vatteluttu (`glyph_svg: "vatteluttu:<iso>"`, the app draws it), L5 Tamil-Brahmi (Noto Sans Brahmi).

## Running

```bash
make setup && make check                                    # offline, uses fixtures until benchmark/ lands
.venv/bin/strands-decider serve StrandsAgents/strands-decider-2B-qwen3.5-v1-2610 --device mps --port 8765
EZHUTHU_DECIDER_URL=http://127.0.0.1:8765 .venv/bin/uvicorn ezhuthu.api.app:app --port 8080
EZHUTHU_LIVE=1 python -m ezhuthu.eval.run --split test --limit 300 --router routed   # live, cached in .cache/
python -m ezhuthu.agentcore_app                             # AgentCore runtime locally on :8080
```

Environment: `EZHUTHU_LIVE=1` (allow Bedrock), `EZHUTHU_DECIDER_URL`, `EZHUTHU_DECIDER=off`,
`EZHUTHU_ONTOLOGY=mcp|direct|stub` (default `mcp`), `EZHUTHU_ONTOLOGY_ROOT` (ontology build dir for the MCP server),
`EZHUTHU_STORE=memory|sqlite:<path>|dynamodb:<table>`, `EZHUTHU_BENCHMARK_DIR`, `EZHUTHU_FIXTURES=1`,
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
`EZHUTHU_STORE=dynamodb:<table>` (single table: `pk` string hash key, GSI `kind-index` on `kind`), Bedrock
invoke permission for the two model IDs, and optionally `EZHUTHU_DECIDER_URL` if a decider endpoint is reachable
from the runtime. Without a decider, confidences use the flagged fallback.
