<picture>
  <source media="(prefers-color-scheme: dark)" srcset="design/brand/banners/readme-hero-dark.png">
  <img alt="எழுத்து · Ezhuthu: learn to read 2,000 years of Tamil inscriptions, in Tamil." src="design/brand/banners/readme-hero-light.png" width="100%">
</picture>

<p align="center">
  <a href="https://github.com/Vivek0712/ezhuthu/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Vivek0712/ezhuthu/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="Code: Apache-2.0" src="https://img.shields.io/badge/code-Apache--2.0-9B3D22"></a>
  <a href="https://strandsagents.com"><img alt="Built with Strands Agents" src="https://img.shields.io/badge/built%20with-Strands%20Agents-1D1611"></a>
  <a href="https://aws.amazon.com/bedrock/agentcore/"><img alt="Runs on Amazon Bedrock AgentCore" src="https://img.shields.io/badge/runs%20on-Amazon%20Bedrock%20AgentCore-D2891C"></a>
  <a href="https://dharmalekha.info"><img alt="Data: CC BY-SA 4.0 (DHARMA)" src="https://img.shields.io/badge/data-CC%20BY--SA%204.0%20·%20DHARMA-3B4787"></a>
  <img alt="Education track" src="https://img.shields.io/badge/hackathon-Education%20track-2C6534">
</p>

<p align="center"><b>An AI tutor that teaches Tamil learners to read their own temple inscriptions, in Tamil, from today's letters back to Tamil-Brahmi.</b><br>
<span lang="ta">உங்கள் ஊர்க் கோயில் கல்வெட்டை நீங்களே படியுங்கள்.</span></p>

Ezhuthu (எழுத்து, "letter") turns real, damaged inscriptions into guided reading lessons at five levels: modern Tamil, Chola Tamil, Pallava (Grantha), Vatteluttu and Tamil-Brahmi. Its restoration engine proposes the missing letters with calibrated confidence. When it is unsure, it says so, and that becomes part of the lesson: *experts are unsure here too*.

Built with [Strands Agents](https://strandsagents.com) and Strands Decider, and built with AWS Context Ontology Accelerator. It runs on Amazon Bedrock AgentCore. Inscription texts come from [DHARMA](https://dharmalekha.info) (CC BY-SA 4.0).

> **Status:** hackathon build (Education track), under active development. Every number below links to its source. **TBD** means the evaluation has not been published yet; we do not estimate.

## Why it matters

- **Underserved learners.** Tamil-medium school and college students, rural heritage guides and self-learners mostly cannot read the inscriptions on their own village temples, and there has been no tool that teaches old Tamil scripts *in Tamil*. India has about 23 working epigraphists for a backlog of about 70,000 unread inscriptions (The Federal, 2021).
- **Real, damaged texts.** The corpus is **1,320** DHARMA inscriptions, of which **65%** are damaged ([data card](benchmark/DATA_CARD.md)). Damage is the normal case, so a reading tutor has to handle it honestly.
- **Feedback in the learner's first language.** Hints, explanations and history (ruler, temple, grant) are in Tamil. English is optional.
- **Measured gain.** A built-in pre-test and post-test on reading letters by era report each learner's gain in letters read correctly and their time per letter. Pilot result with AWS UG Madurai student volunteers: **TBD** ([eval/reports/](eval/reports/)).

| What we measure | Number | Source |
| --- | --- | --- |
| Expert restorations in the benchmark | **3,289** (test **383**, hard **301**) | [benchmark/DATA_CARD.md](benchmark/DATA_CARD.md) |
| Restorations in inscriptions over 1,100 years old (Pallava + Uttiramerur set only) | **419** | [benchmark/DATA_CARD.md](benchmark/DATA_CARD.md) |
| Fills that match the expert restoration (top-1, test) | **TBD** | [eval/reports/](eval/reports/) |
| Calibration (ECE) and coverage at the abstain threshold | **TBD** | [eval/reports/](eval/reports/) |
| Learner gain, pre-test to post-test | **TBD** | [eval/reports/](eval/reports/) |

## How it works

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#FBF8F1', 'primaryBorderColor': '#9B3D22', 'primaryTextColor': '#1D1611', 'lineColor': '#76674F', 'clusterBkg': '#F5EACB', 'clusterBorder': '#B28C42', 'tertiaryColor': '#F4EEE2'}}}%%
flowchart LR
  A["Damaged inscription line<br/>(DHARMA, ISO-15919)"] --> R
  subgraph G["Strands Graph · one lesson"]
    R["Restorer<br/>parallels + candidate fills"] --> D{"Strands Decider<br/>fill or abstain?"}
    D -- fill --> L["Lesson Builder<br/>letters → words → line,<br/>at level L1–L5"]
    D -- abstain --> U["'Experts are unsure'<br/>(a teaching moment)"] --> L
    L --> S
    subgraph S["Swarm · tutoring"]
      T["Tutor<br/>Tamil hints + history"] <--> X["Assessor<br/>grades; Decider picks<br/>advance · repeat · hint"]
    end
  end
  S --> P["Pre/post scores<br/>→ learner gain"]
  O[("Ontology<br/>rulers · temples · grants")] -.-> R & T
```

<p align="center"><img src="design/renders/glyphs/evolution-strip-light.png" alt="Five Tamil letters across Tamil-Brahmi, Vatteluttu, Grantha/Pallava, Chola and modern Tamil" width="88%"></p>

<p align="center"><sub>One letter, five stages. Vatteluttu has no Unicode, so it is drawn (<a href="design/glyphs/REFERENCES.md">sources and review status</a>).</sub></p>

## Screenshots

<!-- Rendered by the app team's Playwright run (npm run screenshots in app/web). -->
| Learn (Tamil) | Restore with confidence and abstain | Progress |
| --- | --- | --- |
| <img src="app/web/screenshots/mobile-02-learn-levels-ta.png" alt="Learn screen" width="240"> | <img src="app/web/screenshots/mobile-04-restore-ta.png" alt="Restore screen" width="240"> | <img src="app/web/screenshots/mobile-07-progress-en.png" alt="Progress screen" width="240"> |

## Quick start

```bash
make setup            # Python 3.12 venv with uv, editable install with dev extras
make data             # fetch DHARMA at the pinned commit into data/raw/ (gitignored)
make check            # ruff + pytest (no live model calls; live tests need EZHUTHU_LIVE=1)

# API (all endpoints in contracts/restore-api.md)
.venv/bin/uvicorn ezhuthu.api.app:app --port 8080

# Web app (Node 22)
cd app/web && npm ci && npm run dev
```

AWS: profile `heisenberg`, region `us-east-1`. Model IDs come only from [`config/models.yaml`](config/models.yaml).

## Architecture

| Layer | What | Where |
| --- | --- | --- |
| Corpus + benchmark | DHARMA TEI/EpiDoc parsing, script conversion (Aksharamukha), restoration benchmark | `src/ezhuthu/corpus/`, `benchmark/` |
| Ontology | Rulers, titles, places, grants, measures, formulae (built with AWS Context Ontology Accelerator) | `src/ezhuthu/ontology/`, `ontology/` |
| Agents | Strands **Graph** (fixed lesson flow) with a **Swarm** inside tutoring: Restorer, Lesson Builder, Tutor, Assessor | `src/ezhuthu/agent/` |
| Decisions | Strands Decider: fill or abstain, Sonnet → Opus routing, and advance / repeat / hint | `src/ezhuthu/agent/` |
| API | FastAPI, following [`contracts/restore-api.md`](contracts/restore-api.md) | `src/ezhuthu/api/` |
| Runtime | Amazon Bedrock AgentCore Runtime (`/invocations`), with infrastructure in CDK | `infra/` |
| App | React + Vite, Tamil-first and bilingual, mobile-first | `app/web/` |
| Design system | Brand, tokens, glyph art, UX spec | [`design/`](design/README.md) |

Teams and ownership: [docs/TEAMS.md](docs/TEAMS.md). Product charter: [docs/CHARTER.md](docs/CHARTER.md). Contracts: [contracts/](contracts/).

## Data credit and licence

- **Inscription texts:** [DHARMA](https://dharmalekha.info), "The Domestication of 'Hindu' Asceticism and the Religious Making of South and Southeast Asia" (ERC grant 809994), and the named editors of each edition. Edition files are **CC BY-SA 4.0**. The derived **benchmark is shared under CC BY-SA 4.0**, with attribution to DHARMA ([data card](benchmark/DATA_CARD.md)). The Tamil Lexicon is used for lookups only. No scraped data.
- **Code:** [Apache-2.0](LICENSE).
- **Fonts:** Noto Serif/Sans Tamil, Noto Sans Brahmi, Noto Sans Grantha, Fraunces and Instrument Sans, all under the SIL Open Font License 1.1 ([design/brand/FONTS.md](design/brand/FONTS.md)).
- **Restorations** are described as "matching expert restorations", never as "correct". Drawn Vatteluttu glyphs are teaching shapes pending an epigrapher's review.

<p align="center"><img src="design/brand/logo/mark-color.svg" alt="" width="48"><br><sub>எழுத்து · Ezhuthu</sub></p>
