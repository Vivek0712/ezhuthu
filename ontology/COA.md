# Context Ontology Accelerator (COA) and the ontology MCP server

**Result, 2026-11-02 (issue #12): COA was not run.** The toolchain COA asks for was installed in a scratch
directory outside the repo, but every attempt to execute COA's own code (its `make generate` build, and then its
ontology-engine validators inside a throwaway Docker container) was denied by this session's permission policy
for code fetched from outside the project ("Code from External"). Per the denial's instructions that was not
worked around. So COA's Scan and Model steps produced **no** ontology draft, there was nothing to reconcile with
`ezhuthu.ttl`, and no part of the Ezhuthu ontology was built, induced, validated or served by COA.
Do not use "built with AWS Context Ontology Accelerator" (charter branding rule) until a run is recorded here.

The rdflib build (`python -m ezhuthu.ontology.build --splits train`, `ontology/ezhuthu.ttl` + `lookups/`) stays the
source of truth. Serving over MCP is done by our own server, `ezhuthu.ontology.mcp_server` (below), which **did**
run and is tested.

## 1. COA attempt: every command, outcome and evidence

Scratch directory: `~/tamil-script/.coa-scratch/` (outside the repo, not committed). Nothing was deployed and no
AWS API was called.

| # | Command (in the scratch dir) | Outcome |
| --- | --- | --- |
| 1 | `git clone --depth 1 --branch v0.3.8 https://github.com/aws/context-ontology-accelerator.git coa` | Worked. Commit `bacd1aa393e31cf2bdbff1bb12186df99479cf71`, `VERSION` 0.3.8, `package.json` `engines.node >=22.23.4`, devDependencies `nx 22.7.10`, `pnpm 10.34.5`. |
| 2 | `source ~/.nvm/nvm.sh && nvm install 22.23.4` | Worked: Node v22.23.4 (npm 10.9.9). nvm created a `default` alias on install; it was removed again with `nvm unalias default`, and a login shell still resolves the global default `/usr/local/bin/node` v22.13.1 (checked). |
| 3 | `corepack enable && corepack prepare pnpm@10.34.5 --activate` (with `COREPACK_HOME` in the scratch dir) | Worked: pnpm 10.34.5, inside the nvm Node 22.23.4 bin dir only. |
| 4 | `export JAVA_HOME=$(brew --prefix openjdk@21)` | Java `openjdk 21.0.13` (COA: 17–24, 21 recommended). Docker server 28.3.2 was already running. COA's `models/gradlew` wrapper replaces a global Gradle; Maven is only for the Databricks connector (not needed). |
| 5 | `python3.12 -m venv uvenv && uvenv/bin/pip install "uv>=0.13.4"` | Worked: uv 0.13.6 in the scratch dir. COA's `pyproject.toml` sets `[tool.uv] required-version = ">=0.13.4"`; the global uv is 0.7.19 and was left alone. |
| 6 | `make generate` (COA `Makefile` → `scripts/smithy-generate.sh`: `models/gradlew clean build`, openapi-generator, `npm install` of the generated TS clients) | **Denied** by the session permission policy before it ran: "Code from External". This is the first step of COA's `make setup`; `uv sync --all-packages` cannot run without it, because `smithy-generated/control-plane-python-server` is a uv workspace member that the ontology engine depends on. |
| 7 | `docker run --rm python:3.12-slim …` with the COA source mounted read-only, installing `rdflib owlready2 pyshacl httpx defusedxml pydantic` + a JRE in the container and running a driver over COA's tier-1/2/3 validators (`ConsistencyValidator` (HermiT), `TaxonomyCycleValidator`, `ConnectivityValidator`, `SHACLValidator`, `DatatypeTokenValidator`, `StructuralMetricsValidator`, `LabelCompletenessValidator`, `CompetencyQuestionValidator`, `AmbiguousMatchValidator`) on a copy of `ezhuthu.ttl` | **Denied** by the same policy ("Code from External"), although sandboxed. Not retried. The driver script is kept at `~/tamil-script/.coa-scratch/drivers/validate.py` for whoever gets approval. |

Not attempted, because they depend on step 6 or on a deployment: `uv sync --all-packages`, `pnpm install
--frozen-lockfile`, `make test`, COA's ontology-engine service (`uvicorn coa_ontology.main:app`), Scan, Model,
and COA's MCP server.

### What a local Scan → Model would have needed (from reading COA v0.3.8 source, not from a run)

* **Scan of documents** is the `sources` package: document preprocessing (PDF, TXT, DOCX, HTML, max 50 MB) feeding a
  graphrag-toolkit **lexical graph** (entities, facts, topics, classifications) that is extracted with Bedrock and
  stored in Neptune (`inducer/unstructured/stores/na_lexical.py`, `ndb_lexical.py`).
* **Model (unstructured induction)** is `coa_ontology.inducer.unstructured.services.pipeline.UnstructuredInductionPipeline`:
  `QUERYING_NEPTUNE → SAMPLING → GENERATING_DESCRIPTIONS (Bedrock) → RESOLVING_IRIS → APPLYING_RULES → ENTAILMENT →
  SERIALIZING`. It reads only through the `LexicalGraphStore` protocol (`stores/protocol.py`: `get_class_nodes`,
  `get_class_relations`, `get_entities_by_class`, `get_facts_for_entities`, `get_topics`), so a local run would need
  either Neptune or an in-memory implementation of that protocol plus Bedrock calls for extraction and descriptions.
  COA ships no local lexical-graph backend.
* **Seeding with an existing ontology** is COA's ontology upload (Turtle accepted), which goes to the deployed
  ontology engine (DynamoDB proposals + Neptune), not to a local file.
* **Input**: DHARMA editions are TEI XML, which Scan does not accept; they would be exported to TXT per edition with
  `ezhuthu.ontology.tei` (train split only, `coverage.json` → `splits`, so no val/test text reaches an artefact used
  in evaluation).

So even with execution approved, a COA "Scan → Model" without the 17-stack deployment means writing an in-memory
lexical store and calling Bedrock from a local process; that is a design decision for the lead, not a docs-only
local workflow.

### What to approve to finish this (smallest honest steps)

1. Allow running COA's code locally (permission rule for `make generate` / `uv sync` in `~/tamil-script/.coa-scratch/coa`,
   or for the Docker run in step 7). Then run step 7 and record HermiT consistency, structural metrics and label
   completeness for `ezhuthu.ttl` here. That would justify "validated with COA's ontology-engine validators", still
   not "built with COA".
2. For Scan → Model: either the COA dev deploy (about $930/month idle per COA's docs; lead's spend decision) or an
   approved local in-memory `LexicalGraphStore` with Bedrock extraction. Import only additions that survive review
   into our seeds; `ezhuthu.ttl` stays the source of truth, and the diff goes in this file.

## 2. COA's MCP server: can it serve our ontology locally? No.

`packages/mcp-server` (v0.3.8) is a thin adapter: `list_metrics`/`describe_schema` invoke deployed Lambdas
(`METRIC_SERVICE_LAMBDA_ARN`, `ONTOLOGY_PROXY_LAMBDA_ARN`), and `query`, `translate_sparql`, `rag_retrieval`,
`graph_traversal` call the deployed Context Manager runtime (`CM_RUNTIME_ARN`), which reads Neptune, Athena,
OpenSearch and Bedrock. Its own "Running Locally" section needs all of those deployed. It has no mode that serves a
local Turtle file, so it cannot serve `ezhuthu.ttl` without a COA deployment (and it was not run here, see above).

## 3. Serving over MCP: `ezhuthu.ontology.mcp_server` (ran, tested)

Our own stdio server, built on the official `mcp` Python SDK (2.x, `MCPServer`):

```bash
.venv/bin/python -m ezhuthu.ontology.mcp_server               # the shipped train-only build in ontology/
.venv/bin/python -m ezhuthu.ontology.mcp_server --root DIR    # another build (or EZHUTHU_ONTOLOGY_ROOT=DIR)
```

| Tool | Arguments | Result (`structuredContent`, same JSON as text) |
| --- | --- | --- |
| `find_entities` | `text` | `{"entities": [...]}` |
| `valid_letters` | `stage` (L1–L5 or a stage id) | `{"stage", "letters": [...]}` |
| `formulas_for` | `ruler` (id) | `{"ruler", "formulas": [...]}` |
| `entity` | `id` | `{"entity": {...} \| null}` |
| `hints_for_gap` | `left`, `right`, `gap_chars?`, `limit?` | `{"hints": [...]}` |

Records are exactly those of `ezhuthu.ontology.lookup` (tests compare them). Input errors (Tamil script instead of
ISO-15919, over-long text, `gap_chars < 1`, unknown stage) come back as MCP tool errors carrying the API's
`ValueError`/`KeyError` message. The server reads the same train-only artefacts as the direct API, so it adds no
leakage path.

Evidence: `tests/ontology/test_mcp_server.py` (in-process `mcp.Client` and a real stdio subprocess) and
`tests/agent/test_ontology_mcp.py` (Strands `MCPClient` over stdio, restorer and agentic Restorer). A local
`/api/restore` on `svasti śrī maturai koṇṭa kō-p-para[?7]rkku yāṇṭu` returned hints `ez:title/parakesarivarman` …
with `/health` reporting `"ontology": "mcp:ezhuthu-ontology (stdio)"`. One stdio tool call took about 0.9 ms
locally (50 `entity` calls), server start about 0.3 s.

Making the server and the agent agree exposed a determinism bug, now fixed: `hints_for_gap` tie-breaks and
`alt_fills` order depended on the Python hash seed (the variant index iterated a set), so two processes could
disagree. `hint_eval` on the current benchmark is unchanged by the fix (val 14/344, test 18/280, in-corpus 96/1,450)
and is byte-identical across seeds.

### How the agent uses it

`ezhuthu.agent.ontology_port.get_ontology()` (env `EZHUTHU_ONTOLOGY`):

| Mode | Backend | `name` (in `/health`) |
| --- | --- | --- |
| unset / `mcp` (default) | `McpOntology`: Strands `MCPClient` → `stdio_client` → `sys.executable -m ezhuthu.ontology.mcp_server` | `mcp:ezhuthu-ontology (stdio)` |
| MCP fails to start | direct `ezhuthu.ontology.lookup` (offline fallback, logged as a warning) | `fallback:direct (mcp unavailable)` |
| MCP server dies after start | the next call restarts the server once and retries; if that fails, direct `ezhuthu.ontology.lookup` (logged as an error) | `mcp:ezhuthu-ontology (stdio)` after a restart, else `fallback:direct (mcp died)` |
| `direct` | direct `ezhuthu.ontology.lookup` | `direct:ezhuthu.ontology.lookup` |
| `stub`, or `EZHUTHU_FIXTURES=1` with no mode | fixture stub (synthetic corpus) | `stub` |

`build_restorer_agent()` also hands the server's five tools (from the same running `MCPClient` session) to the
agentic Restorer.

### AgentCore runtime bundle: what it needs

* **No extra service.** The server is a stdio subprocess of the agent, started with the same interpreter
  (`sys.executable`). It needs no port, no network, no IAM permission and no AWS resource.
* **Same Python environment.** The `mcp` SDK (now a direct dependency, `mcp>=2.0,<2.4`) is in the bundle's wheels.
  Because the bundle installs wheels with `--target` and AgentCore runs `agent_runtime.py` from the bundle root, the
  agent passes its own import roots (the dirs holding `ezhuthu` and `mcp`) to the child on `PYTHONPATH`, so the
  child imports work from any working directory (`test_server_runs_in_this_environment_from_any_cwd`). Not yet
  tested inside a real AgentCore bundle.
* **Ontology files in the bundle**: `ontology/letters_by_era.json` and `ontology/lookups/*.json` next to the
  package (fast/deploy's `package.sh` copies them; `lookup.DEFAULT_DIR` must resolve the bundle layout, as
  fast/deploy's `_default_dir()` does), or set `EZHUTHU_ONTOLOGY_ROOT`. `ezhuthu.ttl` is not needed at runtime.
* **Subprocess allowed** in the runtime (expected in AgentCore Runtime's microVM; not yet verified there). If spawning
  fails, the agent logs a warning and runs on the flagged direct fallback; `/health` shows which one is live.
* **Env passed to the child**: only the MCP SDK's safe defaults plus `PYTHONPATH`, `EZHUTHU_ONTOLOGY_ROOT`,
  `EZHUTHU_MCP_LOG` (no credentials).

## 4. Earlier attempt (2026-11-01, PR #9)

COA v0.3.8 was cloned and its docs reviewed; installing its packages was denied by the same permission policy;
nothing ran. The notes above on COA's deployed MCP server (AgentCore `--protocol MCP`, Cognito PKCE bearer tokens,
`mcp-proxy` for IDEs, six tools) still hold; see `packages/mcp-server/README.md` and
`external-docs/content/agent-access.md` in the COA repo.
