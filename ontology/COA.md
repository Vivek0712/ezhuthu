# Context Ontology Accelerator (COA) attempt

**Result: not run.** COA was cloned at a tagged release and its source and docs were reviewed, but no
COA code was executed and nothing was deployed. The rdflib path (`ontology/ezhuthu.ttl`, built by
`python -m ezhuthu.ontology.build`) is the source of truth and does not depend on COA.

Time box: about 20 minutes on 2026-11-01/02 (UTC), in a scratch directory outside the repo.

## What was done

| Step | Outcome |
| --- | --- |
| Pick a release | `gh release list -R aws/context-ontology-accelerator`: latest tag **v0.3.8** (2026-10-29). The release has no binary assets; COA is installed from source. |
| Clone the tag | `git clone --depth 1 --branch v0.3.8 https://github.com/aws/context-ontology-accelerator.git` (commit `bacd1aa393e31cf2bdbff1bb12186df99479cf71`) into a scratch dir. Worked. |
| Toolchain check | Python 3.12 + uv: present. Node 22.13.1: present, but COA asks for **Node 22.23.4+**. **pnpm: not installed.** Docker: required by COA. Java 21: present (`brew --prefix openjdk@21`, 21.0.13), within COA's 17–24 range. Gradle/Maven: needed for Smithy codegen and the Databricks connector; not checked. |
| Local install of the ontology-engine validators | **Blocked.** Creating a venv and installing COA's packages (`uv pip install -e libs/common …`) was denied by this session's permission policy for running code fetched from outside the project. Per instructions, that was not worked around. |
| Scan / Model on our documents | **Not attempted.** See "Why Scan/Model needs a deployment" below. |

## What COA v0.3.8 is (from its README and `external-docs/`)

* A deployed AWS platform following **Scan → Model → Serve**: data sources and documents are scanned,
  an OWL ontology is induced (Bedrock Claude for concept extraction, Cohere Embed v4 for grounding),
  stored in Neptune (Analytics or Database + OpenSearch Serverless), and served to agents over MCP.
* `make deploy-dev` provisions **17 CDK stacks** (network, Neptune storage, VKG/Ontop, DataZone
  namespaces, AgentCore Runtime serve layer, data layer, API, CloudFront web app, Cognito auth, …).
  COA's own docs give **about 40 minutes** for a fresh deploy.
* The ontology engine has a three-tier validator (`packages/ontology-engine/src/coa_ontology/validation/`):
  tier 1 HermiT consistency, taxonomy cycles, connectivity, SHACL, datatype tokens; tier 2 structural
  metrics; tier 3 OoPS! pitfalls, label completeness, competency questions. This is the piece that
  would be most useful to run on `ezhuthu.ttl` locally (HermiT needs the Java 21 we have).

## Why Scan/Model needs a deployment

* **Model (induction)** runs inside the ontology-engine service against Neptune, DynamoDB and
  Bedrock (`/induce`, `/induce/unstructured/`); `rigor_ontology` and `table_to_ontology` induce from
  relational schemas, and document induction reads a Neptune lexical graph built by document ingestion.
* **Scan of documents** accepts PDF, TXT, DOCX and HTML (max 50 MB each). DHARMA editions are TEI XML,
  so they would need exporting to TXT/HTML first (our `ezhuthu.ontology.tei` reader produces the
  line text needed for that).
* **Upload of an existing ontology** is supported (Turtle, RDF/XML, OWL/XML, JSON-LD), so
  `ezhuthu.ttl` could be loaded as-is and grounded against COA's foundational ontologies.

None of this can run without the 17-stack deployment, which is a spend and security decision for
the lead (Neptune, OpenSearch Serverless and CloudFront in account `heisenberg`), not something to
start inside an ontology time box.

## How the agent would connect if COA is deployed (MCP)

From `packages/mcp-server/README.md` and `external-docs/content/agent-access.md` (v0.3.8):

* The COA MCP server runs on **Bedrock AgentCore Runtime** (`--protocol MCP`, Streamable HTTP, port 8000)
  and exposes six tools: `list_metrics`, `describe_schema`, `query`, `translate_sparql`,
  `rag_retrieval`, `graph_traversal`.
* Auth is delegated user identity only: an OIDC Authorization Code + PKCE token from COA's Cognito,
  sent as `Authorization: Bearer <token>`. There are no machine-to-machine credentials; the acting
  user's namespace grants (Cedar) apply to every tool call.
* IDEs use COA's `mcp-proxy` (stdio → Streamable HTTP; PKCE login, refresh token cached in
  `~/.scl/tokens.json`, runtime ARN discovered from SSM under `/coa`).
* A Strands agent would use `strands.tools.mcp.MCPClient` with
  `mcp.client.streamable_http.streamablehttp_client(<AgentCore MCP endpoint>, headers={"Authorization": f"Bearer {token}"})`,
  with the token minted for a real Ezhuthu operator. This has **not** been tested.

## Recommendation

1. Keep the rdflib ontology and `ezhuthu.ontology.lookup` as the runtime path (offline, ~20 ms load,
   no AWS dependency).
2. If the lead wants the "built with AWS Context Ontology Accelerator" claim, the smallest honest step
   is to run COA's **local validators** (HermiT + structural metrics + OoPS!) on `ezhuthu.ttl` once
   running COA code is approved, and record the report here. Do not claim COA built the ontology:
   it did not.
3. A full deploy (Upload `ezhuthu.ttl` → MCP `describe_schema`/`graph_traversal` from the agent) is a
   separate, budgeted task.
