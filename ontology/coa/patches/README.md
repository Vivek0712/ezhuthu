# COA v0.3.8 patch: S3 Vectors + FalkorDB storage

`0001-coa-v0.3.8-s3-vectors-falkordb.patch` lets the AWS Context Ontology Accelerator (COA) use
**Amazon S3 Vectors** as its vector store (instead of OpenSearch Serverless) and **FalkorDB** as its
graph store (instead of Neptune), chosen by environment variables. Without those variables COA behaves
exactly as before.

**Status: written from source reading, not executed.** `make setup` in COA (and so `uv sync`, COA's
tests and any COA run) was denied by this session's permission policy ("Code from External"), and
`uv sync --all-packages` was denied again in attempt 3. What
*was* verified is listed in [`../../COA.md`](../../COA.md): the patch applies cleanly to v0.3.8, every
patched file parses, the S3 vector bucket and indexes exist and accept/query vectors, and the
FalkorDB lexical-store queries return the expected rows on FalkorDB (`../falkordb_query_check.sh`,
which exits non-zero on a wrong row), and the embedding model `us.cohere.embed-v4:0` returns 1024-d
vectors on heisenberg.

## Apply

```bash
git clone --depth 1 --branch v0.3.8 https://github.com/aws/context-ontology-accelerator.git coa
cd coa                                   # commit bacd1aa393e31cf2bdbff1bb12186df99479cf71
git checkout -b ezhuthu-s3v-falkor
git am /path/to/ezhuthu/ontology/coa/patches/0001-coa-v0.3.8-s3-vectors-falkordb.patch
make setup                               # COA's own: smithy generate + uv sync + pnpm install
uv pip install falkordb \
  "graphrag-toolkit-lexical-graph-falkordb @ git+https://github.com/awslabs/graphrag-toolkit@3dd40de16683521c03c054014625b19e0c36aa3e#subdirectory=lexical-graph-contrib/falkordb"
```

The FalkorDB store is a graphrag-toolkit *contrib* package (v1.0.1), not on PyPI and not in COA's
`uv.lock`, so it is installed into the synced environment rather than added to `pyproject.toml`
(which would invalidate the lockfile). S3 Vectors support is built into `graphrag-lexical-graph`
3.18.7, the version COA pins (present since at least 3.17.1).

## What the patch changes (6 files)

| File | Change |
| --- | --- |
| `packages/sources/.../kg_build/graph_build.py` (Scan) | `GRAPH_STORE_URI` / `VECTOR_STORE_URI` override the Neptune/AOSS URIs (`NEPTUNE_ENDPOINT`/`OPENSEARCH_ENDPOINT` are then not required); registers `FalkorDBGraphStoreFactory` for `falkordb://host:port` (a URI without host:port is rejected with a clear error); the vector health check calls `s3vectors:GetVectorBucket` for `s3vectors://` instead of an AOSS `_cat/indices`. |
| `packages/ontology-engine/.../stores/falkordb_lexical.py` (Model, new) | `FalkorDBLexicalStore`: the Neptune DB `LexicalGraphStore` queries, sent over the FalkorDB client, with `id(e)`/`id(subj)`/`id(t)` rewritten to `e.entityId`/`subj.entityId`/`t.topicId` (graphrag stores node ids as plain properties on non-Neptune stores; FalkorDB's `id()` is an internal integer). |
| `packages/ontology-engine/.../routers/induce_unstructured.py` (Model) | `LEXICAL_GRAPH_STORE_URI=falkordb://...` (server-side config only, like the Neptune endpoint) selects `FalkorDBLexicalStore`; graph name from `FALKORDB_GRAPH_NAME` (default `graphrag`). |
| `packages/context-manager/.../clients/factory.py` (Serve) | Same `GRAPH_STORE_URI` / `VECTOR_STORE_URI` override for the graphrag lexical retriever, plus FalkorDB registration. |
| `scripts/ezhuthu_local/scan_local.py` (new) | Runs Scan's own functions (`_setup_graphrag`, `_build_indexing_config`, `_check_backend_health`, `_run_continuous`) on a local folder of `.txt` files, with an in-memory stand-in for the DynamoDB status table. |
| `scripts/ezhuthu_local/model_local.py` (new) | Builds the same `UnstructuredInductionConfig` the router builds and runs `UnstructuredInductionPipeline`, writing the induced Turtle to a file (no DynamoDB job/proposal rows, no grounding). |

## Run (intended; not yet executed)

```bash
docker run -d --name falkordb -p 127.0.0.1:6379:6379 \
  falkordb/falkordb@sha256:725b74d400124862c9e0f318c56bfb3c55b97cd7f301d9dfe8685980fb3c8195
python -m ezhuthu.ontology.coa_store --create   # in Ezhuthu: create/verify bucket + chunk/topic indexes
export AWS_PROFILE=heisenberg AWS_REGION=us-east-1
# host:port is required: graphrag's FalkorDB factory returns no store for a bare falkordb://
export GRAPH_STORE_URI=falkordb://localhost:6379 LEXICAL_GRAPH_STORE_URI=falkordb://localhost:6379
export VECTOR_STORE_URI=s3vectors://ezhuthu-coa-vectors/ezhuthu
# EMBEDDING_INDEXES is left at COA's default (chunk,topic): nothing in COA v0.3.8 or this patch reads a
# statement index, so embedding statements would only add Bedrock cost.
export BEDROCK_MODEL_ARN=<extraction model / inference profile> NAMESPACE_LANGUAGE=en
uv run python scripts/ezhuthu_local/scan_local.py --docs <train-split .txt dir> --tenant b0310331b8d553b7b3ebfbf51
uv run python scripts/ezhuthu_local/model_local.py --namespace b0310331-b8d5-53b7-b3eb-fbf516c7c9ad --out induced.ttl
```

Input must be **train-split** DHARMA editions only (`ontology/coverage.json` -> `splits`), exported to
text with `ezhuthu.ontology.tei`, so nothing held out reaches an artefact used in evaluation.

## Known gaps

* **Serve strategies vs FalkorDB.** graphrag-toolkit documents the FalkorDB store as supporting
  semantic-guided search only, not traversal-based search. COA v0.3.8 removed its semantic-guided
  strategy: every `coa_serve/lexical/strategies.py` strategy (`chunk_based_semantic` default, `chunk_based`,
  `entity_*`, `topic_*`, `traversal`, `topic_beam`) is built with `for_traversal_based_search` or a
  traversal retriever. So COA's Serve/MCP graphrag retrieval has no FalkorDB-compatible strategy; adding one
  (`for_semantic_guided_search` plus a result mapper for its node shape) is not in this patch. COA's MCP
  server also needs deployed Lambdas and the Context Manager runtime (see `../../COA.md`).
* `progress_monitor=None` is passed to `extract_and_build`, and the extraction model must be one this
  account can call. The embedding model can: one `InvokeModel` of `us.cohere.embed-v4:0` on heisenberg
  (2026-11-02) returned a 1024-d vector, although `GetFoundationModelAvailability` reports
  `agreementAvailability: NOT_AVAILABLE` (authorization `AUTHORIZED`, entitlement `AVAILABLE`). Re-check
  with one call before a large Scan.
* A semantic-guided Serve strategy would also need a `statement` index (`EMBEDDING_INDEXES=chunk,statement,topic`
  at Scan time); add it together with that strategy, not before.
* COA's own tests for the patched modules were not run (blocked with `make setup`).
