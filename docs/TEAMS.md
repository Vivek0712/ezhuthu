# Teams, ownership and protocol

| Team | KrewHQ actor | Owns (paths) | Milestone |
| --- | --- | --- | --- |
| Lead / integration | u:lead | `contracts/`, `docs/`, `config/`, root files, merges | all |
| Data | u:data | `src/ezhuthu/corpus/`, `benchmark/` (artefacts), `data/` (gitignored raw) | M1 Benchmark |
| Ontology | u:onto | `src/ezhuthu/ontology/`, `ontology/` (OWL, lookups) | M2 Ontology |
| Agent + Eval | u:agent | `src/ezhuthu/agent/`, `src/ezhuthu/eval/`, `src/ezhuthu/api/`, `eval/reports/` | M3 Agent, M4 Evaluation |
| App + Infra | u:app | `app/web/` (React), `infra/` (AgentCore + CDK) | M5 App + AgentCore |
| QA | u:qa | `tests/e2e/`, review comments, `eval/reports/qa-*.md` | M6 QA + Release |

## Rules every team follows
1. **Contracts first.** Build against `contracts/*`. To change a contract, open a PR labelled `contract-change` and send a KrewHQ handoff to every affected team. Never change a contract silently.
2. **Git.** Work in your own worktree on branch `team/<name>/<topic>`. Make small commits with conventional messages (`feat(corpus): ...`). Open a PR to `main` that references its issue (`Closes #N`). Never push to `main` directly. Never commit secrets, `data/raw/`, model weights or `.env`.
3. **Tests or it didn't happen.** Every PR adds tests, and `make check` must pass locally before the PR. CI must be green before merge.
4. **KrewHQ context layer** (`scripts/kq <role> ...`, hub on 127.0.0.1:7800):
   - Start of work: `scripts/kq <role> recall "<topic>"` and `scripts/kq <role> handoffs`. Pick up anything addressed to you.
   - Decisions and gotchas: `scripts/kq <role> capture --type decision --title "..." "..." --ref <PR or issue URL> --promote`.
   - Hand-offs: `scripts/kq <role> handoff EZ-<issue#> "<what, where, how to use>" --to u:<role> --ref <PR URL>`.
5. **AWS:** profile `heisenberg`, region `us-east-1`. Model IDs come only from `config/models.yaml`. Keep Bedrock spend small in development: use `limit` options, cache responses under `.cache/`, and set no per-test live calls by default (put live calls behind `EZHUTHU_LIVE=1`).
6. **Data:** `make data` fetches DHARMA at the pinned commit into `data/raw/` (gitignored). Processed, small artefacts may be committed under `benchmark/` and `ontology/` with data cards.
7. **Python 3.12 with uv.** Web: Node 22 with npm.
