< COVER IMAGE: upload blog/img/p2-00-cover.png in the cover field (1200x675, no text) >

By Vivek Raja, AWS AI Hero

In part 1 I introduced Ezhuthu, an apprenticeship tool for the Tamil inscriptions on the temple walls of Tamil Nadu, and walked through the live site. This part opens the pipeline that runs behind it: six specialist agents built with Strands Agents, a custom ontology of Tamil epigraphy served over MCP, Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock, and the whole thing deployed on Amazon Bedrock AgentCore Runtime.

I set three hard requirements before writing any agent code. Every answer has to arrive inside the API proxy's time limit. Every fill has to carry a calibrated confidence, so the assistant can abstain honestly. And no held-out inscription may leak into anything the agents can read. The result is the system that matches the editors' restoration on 62.7% of 413 held-out test gaps, and part 3 shows how that number was earned.

< FIGURE 1 of 7: upload blog/img/p2-01-architecture.png here >
Alt text: The Ezhuthu architecture: a React PWA on Amazon CloudFront calls an API Gateway HTTP API with a JWT authorizer and a Lambda proxy into the AgentCore Runtime; inside the runtime sit the Strands Graph with its Tutor and Assessor Swarm, the Restorer with five tools, the Reader, the Interpreter and the ontology MCP server; Claude Sonnet 4.6 and Claude Opus 4.6 run on Amazon Bedrock

*The whole system on one page: five CDK stacks, one AgentCore runtime, two Claude models.*

## One request, end to end

A learner on a phone in Madurai opens a lesson. The React app, served from private Amazon S3 through Amazon CloudFront, calls an Amazon API Gateway HTTP API. Signed-in routes pass a JWT authorizer backed by Amazon Cognito. A Node 22 Lambda proxy forwards the call to the Amazon Bedrock AgentCore Runtime, where the Strands agents run and call Claude on Amazon Bedrock. Sessions, corrections and the expert review queue live in Amazon DynamoDB.

## Six specialist agents

The Restorer proposes fills for damaged text. The Lesson Builder turns a restoration into lesson facts. The Tutor writes the explanation, and the Assessor checks it. The Reader turns a photo or an EpiDoc file into an editable transcription, using Sonnet 4.6 vision and escalating to Opus 4.6. The Interpreter turns letters into words, a phrase in today's Tamil and a plain meaning.

## A Strands Graph runs every lesson, and a Swarm teaches inside it

Each lesson is a Strands Graph with three nodes: restore, then lesson_builder, then tutor_team. The first two are deterministic function nodes that share one lesson context through the Graph's invocation state. The third is a Strands Swarm in which the Tutor and the Assessor hand the explanation back and forth: the Tutor writes it from the lesson facts, in Tamil first, and the Assessor checks it against the same facts before it reaches the learner.

When no model is available, the Graph takes an offline branch to a template explanation, so a learner always gets feedback.

< FIGURE 2 of 7: upload blog/img/p2-02-graph-swarm.png here >
Alt text: The lesson Graph: restore feeds lesson_builder, which feeds tutor_team, a Swarm where the Tutor drafts the explanation and the Assessor checks it; a dashed branch from lesson_builder goes to an offline template explanation

*Deterministic nodes where the facts are fixed, a Swarm where the words are written and checked.*

The Tutor's next move (advance, repeat or hint) comes from a policy built on Strands Decider with rule guardrails. In the cloud it calls the hosted Strands Decider only when the decider key is configured; otherwise the rules decide and the app says "decided by rules". I have not measured its effect on learners yet.

## The Restorer: a tool-using Strands agent

The Restorer carries most of the weight. It is a Strands agent with 5 tools:

| Tool | What it does |
|---|---|
| retrieve_parallels | finds parallel passages in the train corpus |
| propose_fills | asks Sonnet 4.6, or Opus 4.6 on escalation, for candidate fills |
| check_constraints | checks each fill against the gap length and the letters valid for its era |
| rank_and_decide | runs the full pass for one gap and returns a fill or an abstention, with ranked candidates |
| ontology_hints | looks up rulers, places, grants and formulas mentioned in the text |

The public API runs the same steps as a fixed pipeline, so the agent and the API give the same kind of answer from the same pieces.

### Parallel passages over the whole train corpus

Tamil inscriptions are formulaic. A donation formula carved in one village often appears in another, and epigraphists have always restored gaps by finding those parallels. retrieve_parallels does the same at scale: BM25 over character n-grams across 14,355 train corpus lines, re-ranked with rapidfuzz, keeping the top 20 parallels.

### A character 5-gram model in the loop

A character 5-gram language model, built from the same train lines, proposes its own fills and scores every candidate. It takes 11 ms per gap at p50 (43 ms at p90) on an Apple M4 Pro.

### Three signals fused into one score

The pre-rank is a noisy-OR of three signals: the LLM's probability, the support from parallel passages, and the 5-gram's share. Any one strong signal can lift a candidate, and agreement between them lifts it further. A pre-registered rule picked this configuration on the validation split, and it is what runs in production today.

< FIGURE 3 of 7: upload blog/img/p2-03-restorer-pipeline.png here >
Alt text: The Restorer pipeline: a gap goes to parallel retrieval and the character 5-gram, Claude proposes fills, constraints filter them, and a noisy-OR of LLM probability, parallel support and 5-gram share gives a score that a Platt calibration turns into fill or abstain

*From a gap to a decision in one pass.*

### Where the Strands decision models plug in

The last step of rank_and_decide is a choice: pick the candidate fill the editors would have written, or none of them. That choice is exactly the job a Strands Decider does. The hosted general-purpose decider was tested for it under the same pre-registered rule and did not earn the slot, so the deployed Restorer makes no decider call today. I then fine-tuned a 2B Strands decision model for Tamil on this exact choice. It is tested on held-out inscriptions and not yet live, because the runtime cannot serve a local checkpoint. Part 3 tells that story.

## Routing between Sonnet and Opus on Amazon Bedrock

Claude Sonnet 4.6 goes first, and Claude Opus 4.6 takes over when it matters. The router escalates to Opus when Sonnet's best score is under 0.6, when the gap is over 12 letters, or when no good parallel passage exists. Both model IDs live in one file, config/models.yaml: us.anthropic.claude-sonnet-4-6 and us.anthropic.claude-opus-4-6-v1.

On the test set, Opus handled 296 of 413 gaps: 291 escalated up front by those rules and 5 more after Sonnet answered. That took 122 Sonnet calls and 297 Opus calls, about $2.49 for the whole run, or about $0.0060 per gap, as an estimate at list prices.

< FIGURE 4 of 7: upload blog/img/p2-04-routing.png here >
Alt text: Routing on the test set: 413 gaps, of which 291 go straight to Opus 4.6 by the pre-escalation rules, 5 escalate after a Sonnet 4.6 answer, and the rest stay with Sonnet; 122 Sonnet calls and 297 Opus calls in total

*Opus where it counts.*

## Calibrated confidence and the abstain decision

A raw model score says little about how often a fill will match. Ezhuthu runs every final score through Platt scaling fitted on the validation split only, with one key per answering model:

| Calibration key | Fitted on validation, n | Abstain threshold |
|---|---|---|
| Opus-answered gaps | 224 | 0.4887 |
| Sonnet-answered gaps | 278 | 0.4111 |

Above the threshold the Restorer fills; below it, it abstains, and the gap goes to the learner as "experts are unsure here too" or to the expert review queue. On held-out test the scale holds: the 95 gaps scored between 0.9 and 1.0 match the editors' restoration 97.9% of the time, and the expected calibration error is 0.110.

## A Tamil epigraphy ontology, served over MCP

The agents share a custom OWL ontology of Tamil epigraphy with 27 classes, 21 object properties, 1,958 named individuals and 23,029 triples. It holds rulers (42), places (357), administrative units (200), temples (139), formulas (14), taxes (8), measures (14), letters (262), script stages (8) and dynasties (6). All 6 dynasties and 19 of the 42 rulers link to Wikidata.

It reaches the agents through an MCP server and a Strands MCPClient, which exposes 5 tools: find_entities, valid_letters, formulas_for, entity and hints_for_gap. The server runs as a subprocess in the agent's own Python environment, locally, in tests and inside the AgentCore bundle. If the server process dies, the client restarts it once, and if it stays down the calls are answered by the in-process lookup and the health endpoint reports the fallback.

The ontology is built from the 862 train editions only. The 229 held-out editions are excluded, and tests enforce it.

< FIGURE 5 of 7: upload blog/img/p2-05-ontology-mcp.png here >
Alt text: The ontology slice: a ruler linked to a dynasty with its Wikidata ID, a temple, a place and a formula, beside counts for rulers 42, places 357, temples 139, formulas 14 and letters 262, with the five MCP tool names under the graph

*A custom ontology served to the agents over MCP, built from the train split only.*

I measured what the hints do for restoration, and on 88 hinted gaps they made no measurable difference (3 gained, 3 lost). Where the ontology earns its place is in teaching: the Tutor uses it for the ruler, the temple and the grant behind each lesson.

## A hard 25-second request budget

API Gateway allows 29 seconds, and the Lambda proxy gives the runtime 27. A restore request can carry several gaps, and each gap can call Sonnet and then Opus. Without a budget, a busy request runs straight through the limit.

So every request runs on a 25-second clock. Opus starts only with 8 seconds left, any LLM call only with 6 seconds left, and a request carries at most 8 gaps. A gap that runs out of time abstains with the reason time_budget, so the learner always gets an answer.

| Request | Before the budget | After the budget |
|---|---|---|
| 7 gaps | 30.8 s | 20.9 s |
| 5 gaps | 49.6 s | 25.0 s |
| 5 gaps | 58.4 s | 25.0 s |

All three used to time out, and all three now answer. On the 13 gaps the budget did not touch, the results are identical before and after (13 of 13). This is a latency check on n = 3 requests, and it says nothing about accuracy.

< FIGURE 6 of 7: upload blog/img/p2-06-request-budget.png here >
Alt text: Request budget before and after: three bars at 30.8, 49.6 and 58.4 seconds crossing the 27-second proxy line, then the same requests at 20.9, 25.0 and 25.0 seconds under it

*Three timeouts turned into three answers.*

## Deployment on Amazon Bedrock AgentCore Runtime

The agents run on Amazon Bedrock AgentCore Runtime as the runtime ezhuthu_tutor: Python 3.12, Direct Code Deploy, and a linux/arm64 bundle of about 237 MB unpacked and about 67 MB zipped, with the ontology MCP server inside the bundle.

Everything around it is serverless and written as code with the AWS CDK in TypeScript, in 5 stacks:

| Stack | What it holds |
|---|---|
| EzhuthuData | Amazon DynamoDB, on demand, with point-in-time recovery |
| EzhuthuAuth | Amazon Cognito with PKCE and the experts group |
| EzhuthuAgent | the AgentCore Runtime |
| EzhuthuApi | API Gateway HTTP API, JWT authorizer, Lambda proxy on Node 22 arm64 |
| EzhuthuWeb | private Amazon S3 behind Amazon CloudFront |

The hosted Strands Decider key lives only in AWS Secrets Manager, and the runtime gets read access to that one secret only when it exists. The deployed Restorer makes no decider call.

< FIGURE 7 of 7: upload blog/img/p2-07-cdk-stacks.png here >
Alt text: The five CDK stacks: EzhuthuWeb with S3 and CloudFront, EzhuthuApi with API Gateway, a JWT authorizer and a Lambda proxy, EzhuthuAuth with Cognito, EzhuthuAgent with the AgentCore Runtime, and EzhuthuData with DynamoDB, plus Secrets Manager holding the decider key

*Five stacks, all as code.*

## Engineered like a lab

The repository has 461 Python test functions. make check enforces the leakage rules and checks that the numbers in the README match the benchmark statistics file, so a stale claim fails the build.

## Next in this series

Part 3 is about the Strands decision models I fine-tuned for Tamil and the evaluation work behind every number in this series: training rows built from the train split only, cross-fitting by stone, a selection rule committed before the validation runs, and a test set scored once. It also covers what did not work.

The code is at https://github.com/Vivek0712/ezhuthu and the site is live at https://d3jz2k92ne5puo.cloudfront.net.

## Credits

Inscription texts: the DHARMA project (ERC grant 809994) and the named editors of each edition, CC BY-SA 4.0. The derived benchmark is shared under CC BY-SA 4.0.

Hero photograph on the live site: "Brihadishwara Temple, Dedicated to Shiva, built by Rajaraja I, completed in 1010, Thanjavur (38)" by Richard Mortel, CC BY 2.0 (https://creativecommons.org/licenses/by/2.0/), via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:1010_CE_Brihadishwara_Shiva_Temple,_inscription,_built_by_Rajaraja_I,_Thanjavur_Tamil_Nadu_India.jpg); cropped and resized.

Fonts: Noto Serif Tamil, Noto Sans Tamil, Noto Sans Brahmi, Noto Sans Grantha, Fraunces and Instrument Sans, SIL OFL 1.1.

Built with Strands Agents and Strands Decider; runs on Amazon Bedrock AgentCore; models Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock.
