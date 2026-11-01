# Context Ontology Accelerator (COA) and the ontology MCP server

**Result, 2026-11-02 (issue #12, second attempt): COA was not run.** The user asked to "use S3 Vectors instead of
Neptune", and the workflow brief for this attempt relayed approval to run COA's own code locally, with Amazon S3
Vectors as the vector store and FalkorDB (Docker) as the graph store instead of OpenSearch Serverless and Neptune. The storage side is done: a COA v0.3.8 patch for S3 Vectors + FalkorDB
([`coa/patches/`](coa/patches/README.md)), a tagged S3 vector bucket with three indexes sized for COA's embedding
model, and a check of the patch's FalkorDB queries on a real FalkorDB. But COA's `make setup` was **denied again** by
this session's permission classifier ("Code from External"). That denial is not overridden by approvals relayed
through the workflow, and it was not worked around. Without `make setup` there is no COA environment, so Scan, Model,
the export, the reconciliation with `ezhuthu.ttl` and a COA Serve query were **not** run. No ontology was induced,
nothing was imported into `ezhuthu.ttl`, and there is no `coa/RECONCILE.md` (no counts to report).
Do not use "built with AWS Context Ontology Accelerator" (charter branding rule) until a run is recorded here;
`tests/ontology/test_coa_store.py` fails if the READMEs claim it while this file says COA was not run.

The rdflib build (`python -m ezhuthu.ontology.build --splits train`, `ontology/ezhuthu.ttl` + `lookups/`) stays the
source of truth. Serving over MCP is done by our own server, `ezhuthu.ontology.mcp_server` (section 3), which **did**
run and is tested.

## 1. Attempt 2 (2026-11-02): S3 Vectors + FalkorDB. Every command, outcome and evidence

Scratch: `~/tamil-script/.coa-scratch/` (outside the repo). COA clone at v0.3.8 (`bacd1aa393e31cf2bdbff1bb12186df99479cf71`),
local branch `ezhuthu-s3v-falkor` (commit `5d2aa16`, exported as the patch).

| # | Command | Outcome |
| --- | --- | --- |
| 1 | Read COA's storage seams: `packages/sources/.../kg_build/graph_build.py` (Scan writes `neptune-db://` + `aoss://`), `packages/ontology-engine/.../stores/{protocol,ndb_lexical,na_lexical}.py` + `routers/induce_unstructured.py` (Model reads through `LexicalGraphStore`), `packages/context-manager/.../clients/factory.py` + `lexical/{store_factory,strategies}.py` (Serve), `uv.lock` | graphrag-lexical-graph **3.18.7**. Embedding model `us.cohere.embed-v4:0` at **1024** dims (`coa_common.constants`). Tenant = `to_graphrag_tenant_id(namespace)` (UUID, hyphens stripped, 25 hex chars). |
| 2 | Read graphrag-toolkit docs and source (`awslabs/graphrag-toolkit` @ `3dd40de`, cloned to read only) | S3 Vectors is built in (`s3vectors://<bucket>[/<prefix>]`, present since at least 3.17.1). Index name `<prefix>.<index>-<tenant>`, `float32`, cosine, `nonFilterableMetadataKeys=[value, metadata]`. FalkorDB is the contrib package `graphrag-toolkit-lexical-graph-falkordb` 1.0.1 (`falkordb://host:port`, must be registered with `GraphStoreFactory`). Per its docs it supports **semantic-guided search only, not traversal-based search**. |
| 3 | `source env.sh && make setup` in the COA clone | **Denied** by the permission classifier ("Code from External"), as in attempt 1. Not retried, not worked around. Blocks `uv sync`, COA's tests, Scan, Model and Serve. |
| 4 | Wrote the patch on branch `ezhuthu-s3v-falkor` (Scan/Model/Serve URIs from env, `FalkorDBLexicalStore`, local Scan/Model drivers); details in [`coa/patches/README.md`](coa/patches/README.md) | Every patched file parses (`ast.parse`). `git apply --check` of the exported patch on a pristine v0.3.8 worktree is clean. **Not executed** (step 3). |
| 5 | `python -m ezhuthu.ontology.coa_store --create` (first done with an equivalent one-off script that also smoke-tested put/query/delete) | Created vector bucket **`ezhuthu-coa-vectors`** (SSE-S3) and indexes **`ezhuthu.chunk-`/`ezhuthu.statement-`/`ezhuthu.topic-b0310331b8d553b7b3ebfbf51`** (1024, cosine, float32), account 643603452951, us-east-1. Bucket and all three indexes tagged `Project=ezhuthu, Owner=vivekraja, Env=hackathon, CostCenter=hero-credits` (read back with `ListTagsForResource`). Smoke test: 2 synthetic 1024-d vectors put into the chunk index, `QueryVectors` top-2 returned `smoke-1` (distance 0.0) then `smoke-0` (0.9957), then both deleted. The indexes are now empty. Re-running is idempotent. No Bedrock call. |
| 6 | `docker run falkordb/falkordb:latest` (digest `sha256:725b74d4…c8195`, graph module 4.22.3), then the 5 queries `FalkorDBLexicalStore` sends, on a hand-built 2-entity graph with graphrag's tenant-scoped labels; script: [`coa/falkordb_query_check.sh`](coa/falkordb_query_check.sh) | All five returned the expected rows: classes `Ruler 2, Temple 1`; relation `Ruler built Temple 1`; entity `e1 Rajaraja I Ruler`; fact `Rajaraja I built Brihadisvara` with object `Brihadisvara Temple`; topic `t1 Chola temples 1`. Unrewritten `id(e)` returned internal integers (`2`, `3`), which confirms that the `entityId`/`topicId` rewrite is needed. This checks the openCypher dialect only, not graphrag's write path into FalkorDB. Container removed. |
| 7 | Neptune / OpenSearch | Nothing created. |

**Not run** (all blocked by step 3): `uv sync`, COA unit tests, Scan of the train-split DHARMA text +
`ezhuthu.ttl` seed, Model (induction), export, reconciliation (`coa/RECONCILE.md`), COA Serve/MCP query.

**AWS cost of this attempt: about $0.00.** S3 Vectors bills storage ($0.06/GB-month), PUT ($0.20/GB logical)
and queries ($2.50 per million requests plus data processed). This attempt wrote 2 vectors (~8 KB), ran 1 query
and deleted both, so the cost is under $0.0001. Empty indexes cost nothing. No Bedrock calls were made, and
FalkorDB ran locally. To remove the resources, delete the three indexes and then the bucket (`s3vectors
delete-index` / `delete-vector-bucket`, boto3 or AWS CLI ≥ 2.27).

### What finishing needs

1. A permission rule that lets this session run COA's code in `~/tamil-script/.coa-scratch/coa` (`make setup`,
   `uv run …`). It has to be in the user's Claude Code settings: approval text relayed by a workflow does not
   change the classifier's decision.
2. Then follow [`coa/patches/README.md`](coa/patches/README.md) → *Run*. Export the 862 train-split editions to
   `.txt` with `ezhuthu.ontology.tei` (`coverage.json` → `splits`), add `ezhuthu.ttl` as a seed (Scan accepts
   text, so it would go in as a document; COA's Turtle upload targets the deployed engine), and run `scan_local.py`
   with a small `--limit` first to size Bedrock spend. Then run `model_local.py`, reconcile into
   `coa/RECONCILE.md`, and only then add the "built with" line.
3. Serve: COA's retriever strategies are all traversal-based, which the FalkorDB store does not support (see the
   patch README, *Known gaps*), and COA's MCP server needs deployed Lambdas. Our own MCP server stays the
   serving path.

## 1b. Attempt 1 (2026-11-02, PR #17): toolchain only

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
| 7 | `docker run --rm python:3.12-slim …` with the COA source mounted read-only, installing `rdflib owlready2 pyshacl httpx defusedxml pydantic` + a JRE in the container and running a driver over COA's tier-1/2/3 validators (`ConsistencyValidator` (HermiT), `TaxonomyCycleValidator`, `ConnectivityValidator`, `SHACLValidator`, `DatatypeTokenValidator`, `StructuralMetricsValidator`, `LabelCompletenessValidator`, `CompetencyQuestionValidator`, `AmbiguousMatchValidator`) on a copy of `ezhuthu.ttl` | **Denied** by the same policy ("Code from External"), although sandboxed. Not retried. (Correction, 2026-11-02: the driver script this row said was kept at `~/tamil-script/.coa-scratch/drivers/validate.py` is not there.) |

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

Superseded by attempt 2 (section 1): S3 Vectors + FalkorDB replace a deployment, and the
in-memory store idea became `FalkorDBLexicalStore` in the patch. Note that Model also calls Bedrock for class
descriptions and embeddings (Cohere Embed v4), and Scan calls it for extraction.

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
