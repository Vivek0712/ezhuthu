# Ezhuthu infrastructure (AWS CDK, TypeScript)

Everything that serves Ezhuthu, as code. AWS profile and region come from `config/models.yaml` (`aws_profile`, `region`; the region is `us-east-1`). Commands below write the profile as `<profile>`.

```
Browser ──> CloudFront ──┬── /*      ──> S3 (private, OAC)   React app + /config.json
                         └── /api/*  ──> API Gateway HTTP API ──> Lambda proxy ──┬──> Bedrock AgentCore Runtime
                                          (JWT authorizer on                      │     "ezhuthu_tutor" (Strands agents,
                                           Test + Review routes)                  │      Python 3.12, Direct Code Deploy)
                                                                                  └──> DynamoDB (sessions, corrections, queue)
Cognito user pool (managed login, PKCE) ── group "experts"
```

| Stack | What it creates |
| --- | --- |
| `EzhuthuData` | DynamoDB table (on demand, TTL, PITR) with `gsi1` for the review queue |
| `EzhuthuAuth` | Cognito user pool, `experts` group, public SPA client (code + PKCE), hosted domain |
| `EzhuthuAgent` | AgentCore Runtime `ezhuthu_tutor` from an S3 code asset (with the ontology MCP server), execution role scoped to the model IDs in `config/models.yaml`, the agent's own table keys and, only when it exists, the decider key secret; 14-day runtime log retention |
| `EzhuthuApi` | HTTP API, one route per contract endpoint, JWT authorizer, stage and route throttling, Lambda proxy (Node 22, arm64) |
| `EzhuthuWeb` | Private S3 bucket, CloudFront (SPA rewrite function, security headers, `/api/*` to the HTTP API), `config.json` |

No Lambda Function URLs are used (they are blocked on this account); the proxy is reached only through API Gateway.

## Access rules

| Route | Access | Throttle (rps / burst) |
| --- | --- | --- |
| `POST /api/restore` | public | 5 / 10 |
| `POST /api/read` (photo or file to text; body up to 4.5 MB; `router: "opus"` only with a one-time `reread_token`) | public | 2 / 5 |
| `POST /api/lesson`, `POST /api/answer`, `POST /api/assessment`, `GET /api/progress/{session_id}` | public | stage default 20 / 40 |
| `POST /api/corrections` | public (name is stored as "unverified" unless signed in) | 2 / 5 |
| `POST /api/evaluate` | any signed-in user | 1 / 2 |
| `GET /api/queue`, `POST /api/queue/{id}` | signed-in **and** in group `experts` | stage default |

The JWT authorizer enforces sign-in; the proxy enforces the `experts` group (and re-checks sign-in).

## Prerequisites

- Node 22, `uv`, AWS CLI v2 with a configured profile (`<profile>`; set the same name as `aws_profile` in `config/models.yaml`).
- CDK bootstrapped once: `npx cdk bootstrap aws://<account>/us-east-1 --profile <profile>`.
- The agent entry point `src/ezhuthu/agentcore_app.py` (Agent team) exposing `app = BedrockAgentCoreApp()`.
  `agentcore/agent_runtime.py` imports it; deploying before it exists creates a runtime that fails on start.

## Build and synthesise

```bash
cd infra
npm ci
npm run check            # typecheck + unit tests (proxy logic, stack assertions)
npm run package:agent    # linux/arm64 Python 3.12 bundle -> agentcore/build (~237 MB unpacked, ~67 MB zipped)
npm run smoke:agent      # runs the bundle in linux/arm64 python:3.12-slim (Docker, --network none): MCP ontology, Dynamo store, decider
npx cdk synth --quiet --profile <profile>
npx cdk diff --profile <profile>   # read-only change sets against the live stacks
(cd ../app/web && npm ci && npm run build)   # optional before deploy; the Web stack ships dist/ if present
```

`cdk synth` fails with a clear message if `agentcore/build` is missing, or if it lacks what the ontology MCP server
needs (`lib/bundle.ts`: the `mcp` SDK, Strands' MCP client, `ezhuthu/ontology/mcp_server.py`, `ontology/letters_by_era.json`
and `ontology/lookups/*.json`).

### Hosted decider switch

`bin/ezhuthu.ts` runs a read-only `aws secretsmanager describe-secret --secret-id ezhuthu/decider-api-key` with the
profile from `config/models.yaml` on every synth. Only a definite answer picks a backend: the secret's ARN (hosted), or
`ResourceNotFoundException` / a secret scheduled for deletion (fallback). Any other failure (no AWS CLI, the 20 s
timeout, throttling, a missing profile or credentials) stops the synth with a hint to pass the context override below,
so a deploy cannot quietly drop the hosted decider once the secret exists. If the secret exists (it does: the
2026-11-04 deploy output is `DeciderBackend = hosted (Secrets Manager ezhuthu/decider-api-key)`), the runtime gets
`EZHUTHU_DECIDER_BACKEND=hosted` and `secretsmanager:GetSecretValue` on that one secret ARN: the restorer ranks with
the fine-tuned `ezhuthu-strands-2b-ft` (`restorer.strategy_llm: choice-topk`, the decider-free pre-rank as the
fallback when the decider is unavailable or the request is short of time) and the tutor policy calls the hosted
general model. If it does not, the runtime gets `EZHUTHU_DECIDER_BACKEND=fallback` and no Secrets Manager permission:
restoration ranks with the pre-rank alone (`decider_fallback: unavailable`) and tutor decisions carry
`decider_source: rules` with `decider_confidence: null`, which the app shows as "decided by rules". The
`DeciderBackend` stack output says which one was synthesised. Override with
`-c ezhuthu:deciderSecretArn=<arn>` or force the fallback with `-c ezhuthu:deciderSecretArn=none`. Nothing here
creates the secret.

## Deploy (two passes, because Cognito needs the CloudFront URL)

```bash
# 1st pass: everything; the Cognito client only allows http://localhost:5173 callbacks for now
npx cdk deploy --all --profile <profile> --require-approval broadening

# read the web URL, then allow it as a Cognito callback and CORS origin
WEB=$(aws cloudformation describe-stacks --stack-name EzhuthuWeb --profile <profile> \
  --query "Stacks[0].Outputs[?OutputKey=='WebUrl'].OutputValue" --output text)
npx cdk deploy EzhuthuAuth EzhuthuApi --profile <profile> -c ezhuthu:webUrl=$WEB
```

Keep passing `-c ezhuthu:webUrl=$WEB` on later deploys (or set it in `cdk.json`). Set
`-c ezhuthu:cognitoDomainPrefix=<name>` if the default `ezhuthu-<account>` prefix is taken.

### Custom domain

The live app is served at **https://ezhuthu.sparrowdecider.com**; the CloudFront URL
https://d3jz2k92ne5puo.cloudfront.net keeps working. `cdk.json` sets:

| Context | Value | Effect |
| --- | --- | --- |
| `ezhuthu:webUrl` | `https://d3jz2k92ne5puo.cloudfront.net` | CloudFront URL, still allowed by Cognito and CORS |
| `ezhuthu:domainName` | `ezhuthu.sparrowdecider.com` | CloudFront alias; `https://<domainName>` is added to Cognito and CORS |
| `ezhuthu:hostedZoneId` | `Z02568233IVWQFY5MJ13V` | existing Route 53 zone (imported, never created) |
| `ezhuthu:hostedZoneName` | `sparrowdecider.com` | its name |

With all three domain values set, `EzhuthuWeb` creates a DNS-validated ACM certificate (us-east-1, as CloudFront
requires; the stack already deploys there), adds the domain and certificate to the distribution, and creates the A and
AAAA alias records for that one name. No other record in the zone is touched. The `WebUrl` output becomes the custom
domain; `CloudFrontUrl` keeps the `*.cloudfront.net` URL. Set none of them to keep the CloudFront-only setup; a
partial set fails the synth. Extra origins can be added with `-c ezhuthu:webUrls=https://a,https://b`; every origin
from `webUrl`, `webUrls` and `domainName` is allowed as a Cognito callback (`/auth/callback`), logout URL (`/`) and
API CORS origin.

```bash
npx cdk deploy EzhuthuAuth EzhuthuApi EzhuthuWeb --profile heisenberg \
  -c ezhuthu:budgetEmail=<address> --require-approval broadening
```

The certificate waits for its DNS validation record, so the first deploy with the domain takes a few minutes.

The `EzhuthuData` stack creates a USD 50 monthly budget for resources tagged `Project=ezhuthu`. To get an email at
80% of it, pass `-c ezhuthu:budgetEmail=<address>` (or set `EZHUTHU_BUDGET_EMAIL`) on every deploy; without one the
budget has no email notification.

Make someone an expert reviewer:

```bash
aws cognito-idp admin-add-user-to-group --user-pool-id <UserPoolId> --username <email> \
  --group-name experts --profile <profile>
```

### AgentCore CLI alternative

The runtime can also be managed by the AgentCore CLI (`npm i -g @aws/agentcore`) or the Python starter toolkit
instead of the `EzhuthuAgent` stack, for fast iteration on the agent alone. Pass its ARN as context and CDK skips
the Agent stack (and the code bundle) and points the proxy at it:

```bash
npx cdk deploy --all --profile <profile> -c ezhuthu:agentRuntimeArn=arn:aws:bedrock-agentcore:us-east-1:<acct>:runtime/<id>
```

Give that runtime's execution role read/write on the `EzhuthuData` table yourself. CDK remains the source of truth
for everything else.

## Verify

```bash
API=$WEB/api
# public restore through CloudFront -> HTTP API -> Lambda -> AgentCore (one Bedrock call)
curl -s -X POST $API/restore -H 'content-type: application/json' \
  -d '{"text":"svasti śrī kōp[?4]kēcaripaṉmaṟku","script":"iso15919","max_candidates":3}' | jq '.gaps[0].decision'
# protected route without a token -> 401 from the JWT authorizer
curl -s -o /dev/null -w '%{http_code}\n' $API/queue
# SPA deep link -> index.html
curl -s -o /dev/null -w '%{http_code}\n' $WEB/learn
# proxy logs
aws logs tail /aws/lambda/<ProxyFunctionName> --since 10m --profile <profile>
```

## Teardown

```bash
npx cdk destroy --all --profile <profile>
```

The DynamoDB table and the Cognito user pool use `RETAIN` so learner progress and reviewer accounts survive a
destroy. Delete them by hand when you really mean it (`aws dynamodb delete-table`, `aws cognito-idp delete-user-pool`,
after deleting the pool's domain). The site bucket is emptied and deleted automatically.

## Proxy to agent contract (for `src/ezhuthu/agentcore_app.py`)

For every tutor, restore and evaluate route the proxy calls `InvokeAgentRuntime` with this JSON payload:

```json
{
  "version": 1,
  "route": "/api/answer",                  // the API Gateway route path from contracts/restore-api.md
  "method": "POST",
  "path_params": {"session_id": "..."},     // only for /api/progress/{session_id}
  "body": { ...request body exactly as in the contract... },
  "session_id": "s-<uuid>",                 // tutor routes only (see below)
  "user": {"sub": "...", "name": "...", "groups": ["experts"]} | null,
  "request_id": "..."
}
```

- `POST /api/lesson`: the **proxy mints `session_id`** (`s-<uuid>`) and sends it in the payload. The agent must use
  that id as the response's `session_id`.
- `answer`, `assessment`, `progress`: `session_id` is taken from the body or path and forwarded. All requests for one
  learner session use the same AgentCore `runtimeSessionId` (`ezhuthu-sess-<sha256(session_id)>`), so warm in-memory
  state is reused, but microVMs can be recycled: persist tutor state in DynamoDB (`EZHUTHU_TABLE`, item
  `pk=SESSION#<session_id>`, `sk=` your choice other than `META`, which the proxy writes).
- JSONL uploads to `/api/evaluate` arrive as `"body": {"jsonl": "<raw text>"}`; built-in runs arrive as the JSON body.
- **Return** `{"status": <http status>, "body": <contract response or {"error": {"code", "message"}}>}`. A bare contract
  body is accepted as status 200.
- **Time budget:** the HTTP API integration limit is 30 s and the proxy gives AgentCore 27 s. Restores that escalate
  to Opus and `/api/evaluate` with large `limit` must fit, or the app needs an async job pattern (would be a contract
  change).
- Corrections and the review queue are handled by the proxy in DynamoDB (`pk=QUEUE#<id>`, `sk=ITEM`,
  `gsi1pk=STATUS#<status>`). To queue an abstention for experts, the agent can write the same item shape with
  `status=pending`, `gsi1pk=STATUS#pending`, `gsi1sk=<ISO time>`.

Runtime environment variables: `EZHUTHU_TABLE`, `EZHUTHU_STORE=dynamodb` (tutor sessions `SESSION#<id>/STATE`,
corrections `CORRECTION#<id>/ITEM`, queue `QUEUE#<id>/ITEM` in that table), `EZHUTHU_ONTOLOGY=mcp` (the bundled stdio
MCP server; `/health` reports `mcp:ezhuthu-ontology (stdio)` or a flagged `fallback:direct (...)`),
`EZHUTHU_DECIDER_BACKEND=hosted|fallback` (see "Hosted decider switch"), `EZHUTHU_MODELS_FILE=config/models.yaml`
(bundled), `EZHUTHU_MODEL_DEFAULT`, `EZHUTHU_MODEL_ESCALATE`, `EZHUTHU_MODEL_CHEAP` (all from `config/models.yaml`).

The execution role's table access is `dynamodb:GetItem`/`PutItem` on the table, limited by `dynamodb:LeadingKeys` to
`SESSION#*`, `CORRECTION#*` and `QUEUE#*`, plus `dynamodb:Query` on `index/gsi1` (the queue listing). IAM cannot
condition on the sort key, so the role can also write the proxy-owned `SESSION#<id>/META` item; the agent code only
writes `sk=STATE` there and relies on that, not IAM, to leave `META` alone. No API path makes any other call.
`DynamoStore.list("session")` and `list("correction")` (admin/debug only, never called by the API) use a `Scan`, which
the role is not granted, so they fail with `AccessDenied` inside the runtime; run them with your own credentials.

## Monthly cost estimate (not measured; check current AWS pricing pages before relying on it)

Assumed pilot: 100 learners, each doing 4 lessons of about 30 API calls, so about 12,000 agent requests a month,
with about one model call per request averaging 1,500 input and 300 output tokens on the default model.

| Item | Basis (us-east-1 list prices at time of writing) | Estimate |
| --- | --- | --- |
| Bedrock model tokens | 18 M input x $3/M + 3.6 M output x $15/M (Sonnet-class pricing) | about $108 |
| AgentCore Runtime | billed per active vCPU-second ($0.0895/vCPU-h) and GB-second ($0.00945/GB-h); 12k requests x a few seconds | under $5 |
| API Gateway HTTP API | $1.00 per million requests | under $0.10 |
| Lambda (arm64, 512 MB) | 12k invocations x a few seconds | under $0.50 |
| DynamoDB on demand | a few thousand reads and writes | under $0.10 |
| CloudFront + S3 | within the CloudFront always-free tier (1 TB, 10 M requests) | about $0 |
| Cognito (Essentials) | first 10,000 monthly active users free | $0 |
| CloudWatch Logs | well under 1 GB ingested | under $0.50 |
| **Total** | dominated by model tokens; scales linearly with usage | **about $115** |

Every escalation to Opus raises the token line; the routing thresholds live in `config/models.yaml`. Real numbers
belong in `eval/reports/` once the pilot runs.

### `POST /api/read` cost controls

The route is public, and a photo read is one or two Bedrock vision calls on the hero-credits account. Limits:

- Stage throttle 2 rps / burst 5 (above). There is no per-IP limit or daily cap at the API layer.
- A caller cannot choose Opus 4.6: `router: "opus"` is refused (403 `reread_token_invalid`) unless it carries the
  one-time `reread_token` that the agent issued for that same photo after a read ran out of time (15-minute TTL, one
  use, stored as `READTOKEN#<id>` in the data table, which the agent role may write: `AGENT_KEY_PREFIXES`). The only
  Opus calls are therefore the agent's own escalations (reader confidence under 0.6, with at least 15 s of the 25 s
  budget left) and one re-read per such token.
- Every model call, including retries and back-off, is bounded by the request's 25 s budget, so a slow Bedrock
  answer is abandoned rather than billed twice behind a proxy 504.
- Kill switch: unset `EZHUTHU_LIVE` on the runtime (or redeploy without it) and `/api/read` answers photos with 503
  `reader_unavailable` while text and EpiDoc uploads keep working.
