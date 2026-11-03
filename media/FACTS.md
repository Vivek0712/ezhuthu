# Ezhuthu launch FACTS: the single source of truth for the video and the blogs

Every claim in the 3-minute video, the narration, the on-screen graphics and the Builder Center blogs must come
from a row in this file, quoted with its **exact** number. Cite the fact ID (for example `A1`) in the storyboard,
script and blog drafts so the reviewer can check it. If a number you want is not here, it is not a claim we make.

Built 2026-11-03 from `origin/main` at `d4ea3b3` (plus the fine-tuned decider report on
`origin/team/agent/ft-decider`). Restructured the same day to follow `media/MESSAGING_BRIEF.md`: **problem ->
solution -> implementation -> impact -> achievements**, grounded in Madurai, Tamil Nadu, the Tamil language and the
temples whose walls carry the inscriptions. All paths are repo-relative. Existing fact IDs are unchanged (the
storyboard cites them); new rows use new IDs (P12+, R1+, D1+, H1+, E1+).

## How to use this file

- **Be bold in wording, exact in numbers.** "62.7%" may be said as "nearly two in three" only if the row says so.
  Never round up (0.6271 is 62.7%, never 63%). Rounding down is allowed ("+21 points" for +21.06).
- **Keep the qualifier that travels with the number** (TEST, held-out, N, "matches the editors' restoration").
  The qualifier column says what must stay attached.
- **Story order (user direction, 2026-11-03):** lead with the problem and the place, then the apprentice, then the
  agent pipeline on AWS (with the fine-tuned Strands decision models and the work behind them as part of that
  pipeline), then who it helps, then the results. **Do not build the story on model-vs-model comparisons** (no
  "Claude vs decider" framing). Comparison rows (A2-A6, A15, A16, A18) are supporting evidence for a blog table or a
  skeptic's question, not a headline.
- **External facts** (section 6, IDs `E*`) are about Madurai, Tamil Nadu and the Tamil language, not about Ezhuthu.
  Each carries a public URL. Say them as context ("Tamil Nadu ...", "UNESCO lists ..."), never as our result.
- **Live site:** https://d3jz2k92ne5puo.cloudfront.net (pages: Home, Practice, Restore, How it works, Benchmark).
- **Repo:** https://github.com/Vivek0712/ezhuthu (public).

## Copy rules (hard bans)

| Never say | Say instead | Why / source |
| --- | --- | --- |
| "experimental" (anywhere, including for photo reading) | "photo reading of Tamil script, shown with its confidence for you to check against the edition" | campaign rule |
| the banned company name (starts "Aiv") | (nothing) | campaign rule |
| "Strands AI", "AWS AI" | "built with Strands Agents", "runs on Amazon Bedrock AgentCore" | `docs/CHARTER.md` Rules |
| "correct", "accurate", "accurate restoration of the original" | "matches the editors' restoration" / "matches the expert restoration", with N | `docs/marketing/positioning.md` "Claims we never make" |
| "over 1,100 years old" for anything but the Pallava collection | "410 restorations in Pallava inscriptions over 1,100 years old" | `benchmark/DATA_CARD.md` Known limits |
| "reads Tamil-Brahmi (or Grantha, or Vatteluttu) from photos" | "reads Tamil-script photos; teaches Tamil-Brahmi letters" | `eval/reports/2026-11-02-ocr-eval.md` |
| "COA store / FalkorDB / Context Ontology Accelerator runs" or "built with AWS Context Ontology Accelerator" | "a custom OWL ontology served to the agents over MCP" | `ontology/README.md` (COA "not run yet") |
| "the fine-tuned decider is live / deployed / in production" | "fine-tuned", "tested on held-out TEST" | `2026-11-02-finetuned-decider.md` ("It is not deployed") |
| "the live Strands Decider drives the tutor in the cloud" | "the tutor's advance / repeat / hint policy is built on Strands Decider with rule guardrails" | `infra/README.md` "Hosted decider switch": without the decider key the cloud runtime falls back to rules ("today" at `d4ea3b3`); see S8 |
| "deciphers inscriptions", "clears the backlog", "replaces epigraphists", "validated by scholars" | "an apprenticeship tool", "routes doubts to expert review" | `docs/marketing/positioning.md` |
| "beats humans", "better than epigraphists", "state of the art", "first", "world's first" | "matches the editors' restoration on N of 413 held-out gaps" | campaign rule; no human study exists (L7) |
| "a backlog of about 70,000" | The Federal wording in P1 | `docs/marketing/positioning.md` |
| "the ontology makes it more accurate" | "the agents look up kings, places and formulas in the ontology" | L5 (no measurable effect) |
| any learner-gain or expert-study number | "learner pilot and expert study: next" | README ("TBD") |
| any Madurai / Tamil Nadu fact not in section 6 | (leave it out) | this file |

**Credits (must appear in the video end card and every blog):**
- Inscription texts: **DHARMA** project (ERC grant 809994) and the named editors of each edition, **CC BY-SA 4.0**;
  the derived benchmark is shared under CC BY-SA 4.0. Source: `benchmark/DATA_CARD.md`.
- Hero photograph: **Richard Mortel, CC BY 2.0**, via Wikimedia Commons ("Brihadishwara Temple ... Thanjavur (38)").
  Source: `app/web/public/hero/ATTRIBUTION.md`.
- Fonts: Noto Serif/Sans Tamil, Noto Sans Brahmi, Noto Sans Grantha, Fraunces, Instrument Sans (SIL OFL 1.1).
  Source: `design/brand/FONTS.md`.
- Built with Strands Agents and Strands Decider; runs on Amazon Bedrock AgentCore; models Claude Sonnet 4.6 and
  Claude Opus 4.6 on Amazon Bedrock.
- Any external footage or photo: title, author, licence, URL and changes in `media/video/CREDITS.md` and on the end
  card. No BBC (or other all-rights-reserved) footage.

## 0. The story in five beats (for the narration spine)

| Beat | One line (bold wording, every number traceable) | Fact IDs |
| --- | --- | --- |
| Problem | Tamil Nadu's temple walls hold over a thousand years of Tamil writing; 65% of the inscriptions we use have a gap or an editor's restoration; and in 2021 India had about 23 epigraphists. | E2, E3, E5, P1, P7, P12 |
| Solution | Ezhuthu is an apprentice for Tamil epigraphy: Practice, Restore, Reader, Interpreter, Tutor, Tamil first. | S1-S16, R1 |
| Implementation | A Strands Graph and Swarm of six agents, a custom ontology over MCP and Claude on Amazon Bedrock, running on Amazon Bedrock AgentCore; plus Strands decision models we fine-tuned for Tamil and tested on held-out inscriptions (not live). | T1-T20, D1-D8 |
| Impact | Students, temple visitors and heritage volunteers learn to read the stone; what the AI cannot settle goes to an epigraphist's review queue. | H1-H6 |
| Achievement | On 413 held-out gaps it matches the editors' restoration on 62.7%, and when it commits, 9 times in 10. | A1, A7, A8 |

---

## 1. The problem

| ID | Punchy claim | Exact number | Must keep | Source |
| --- | --- | --- | --- | --- |
| P1 | India's stones are waiting for readers. | In 2021 India had about **23** epigraphists; of nearly **1 lakh (100,000)** inscriptions found since 1886, only **30,000 to 35,000** had been deciphered and published. | "In 2021", "about", cite The Federal, 3 Aug 2021 | `README.md` "Why it matters" (The Federal, 3 Aug 2021) |
| P2 | Training a new reader is slow and mentor-bound. | (qualitative) | none | `docs/marketing/positioning.md` proposed README copy |
| P3 | Most learners cannot read the inscriptions on their own village temple, and there was no tool that teaches old Tamil scripts *in Tamil*. | (qualitative) | none | `README.md`, `docs/CHARTER.md` |
| P4 | 2,000 years of Tamil writing, five scripts: modern Tamil, Chola Tamil, Pallava (Grantha), Vatteluttu, Tamil-Brahmi. | **5** levels (L1 to L5), **8** script stages in the letter model | none | `README.md`; `ontology/letters_by_era.json` (`levels`, `stages`) |
| P5 | Vatteluttu has no Unicode encoding, so we drew it. | **7** drawn Vatteluttu teaching glyphs (a, e, ka, lla, ma, pa, ta) | "teaching shapes pending an epigrapher's review" | `design/glyphs/vatteluttu/`, `README.md` |
| P6 | A real corpus, not a toy. | **1,320** DHARMA TEI editions parsed, **18,066** lines, from **14** pinned DHARMA repositories | none | `benchmark/DATA_CARD.md` Counts; `benchmark/stats.json` |
| P7 | Damage is the normal case. | **858 of 1,320** inscriptions (**65%**) have a restoration or a gap | none | `benchmark/stats.json` `inscriptions_damaged`; `benchmark/DATA_CARD.md` |
| P8 | Thousands of expert restorations to learn from and test against. | **3,289** expert restorations in Tamil lines (lost 2,525, undefined 764); all `<supplied>` spans in all languages: **5,752** | "expert restorations" = DHARMA editors' `<supplied>` spans | `benchmark/stats.json` |
| P9 | Plus thousands of gaps nobody has restored. | **3,557** blank gaps of known size with no expert fill | none | `benchmark/stats.json` `blank_items` |
| P10 | Over 1,100 years old. | **410** restorations in the **Pallava** collection (age set with Uttiramerur: 419) | "over 1,100 years old" ONLY for the 410 Pallava | `benchmark/DATA_CARD.md` Counts, Known limits |
| P11 | Most gaps are one letter, but the hard ones are long. | Benchmark gap lengths: **1,833** one-letter, **583** two-letter, ... **23** of 21+ letters | none | `benchmark/stats.json` `gap_chars_hist` |
| P12 | The corpus is temple stone: Madurai to Thanjavur. | **534 of 1,320** editions name a temple in their title; it includes **Madurai, Minākṣi temple** (1 edition, TEST: `DHARMA_INSTamilNadu00067`, time of Māṟavarmaṉ Sundara Pāṇḍya) and **6** editions from the **Thanjavur Bṛhadīśvara** temple (time of Rājarāja I Cōḻa and later; 5 train, 1 test) | "editions" (DHARMA TEI files), not stones; count by title string (`'temple'`, `'madurai'`, `'thanjavur'`/`'tanjore'` in `title`) | `benchmark/inscriptions.jsonl` `title`, `split` (count run 2026-11-03) |
| P13 | Madurai is written into the stones themselves. | **25** editions contain *matirai* (Madurai in the inscriptions' spelling); **23** of them in the royal title *matirai koṇṭa* ("who took Madurai", Parāntaka I Cōḻa) | "editions"; the 23 are a Cōḻa king's title, not inscriptions found in Madurai | `benchmark/inscriptions.jsonl` `text_iso`; `ontology/seeds/dynasties_rulers.yaml` (parantaka-i note) |
| P14 | Every great Tamil dynasty is on the wall. | Dynasty by title/metadata: Pallava **480**, Cōḻa **312**, Pāṇḍya **115**, Vijayanagara **21**, Rāṣṭrakūṭa **12**, Kāṭava **9**, not stated **371** (of 1,320) | none | `benchmark/inscriptions.jsonl` `dynasty` |
| P15 | Twelve DHARMA collections, from across Tamil Nadu and beyond. | Largest: Pallava 480, Tamil Nadu 343, *South Indian Inscriptions* 176, Tiruvāvaṭutuṟai 79, Cīrkāḻi 55, Pāṇḍya 54 | none | `benchmark/inscriptions.jsonl` `collection`; `benchmark/stats.json` `per_collection` |

## 2. The solution: an apprentice for Tamil epigraphy

Tagline: **"Learn to read the stone. Help read the backlog."** Tamil: *கல்வெட்டைப் படிக்கக் கற்றுக்கொள்ளுங்கள்; காத்திருக்கும் கல்வெட்டுகளைப் படிக்க உதவுங்கள்.* (Tamil line pending a native-speaker check.) Source: `docs/marketing/positioning.md`.

| ID | Punchy claim | Exact number | Must keep | Source |
| --- | --- | --- | --- | --- |
| R1 | **Five things the apprentice does:** Practice (drills from real stones), Restore (fills worn letters or abstains), Reader (photo or EpiDoc in, transcription out), Interpreter (words, today's Tamil, a plain meaning), Tutor (hints and history, Tamil first). | 5 modes | Reader: Tamil script only (L6); Interpreter: "Meaning by Ezhuthu" | S2, S4, S6, S7, S8 rows below |
| S1 | Three audiences, one tool: students and heritage guides, new epigraphists, working scholars. | 3 | none | `docs/marketing/positioning.md` "Who it is for" |
| S2 | Practice: real inscriptions turned into drills, Tamil first. | **1,469** practice items: letters **205**, words **540**, gaps **394**, formulas **330**, each at 3 difficulty levels | "built from the train split"; Tamil strings pending native-speaker check | `app/web/src/practice/banks/summary.json`, `banks/*.json` |
| S3 | Practice bank sizes by level (for a graphic). | letters 37/94/74; words 230/165/145; gaps 170/158/66; formulas 144/132/54 | none | `app/web/src/practice/banks/summary.json` |
| S4 | Restore: the AI proposes the missing letters, shows how sure it is, and abstains when it is not. | (see A-rows) | "matches the editors' restoration" | `README.md`, `contracts/restore-api.md` |
| S5 | When it is unsure, that becomes the lesson: *experts are unsure here too*. | (qualitative) | none | `README.md` |
| S6 | Reader: photo or EpiDoc file in, an editable transcription out. | Sonnet 4.6 vision, escalating to Opus 4.6 | Tamil script only (see L6) | `src/ezhuthu/agent/reader.py` docstring |
| S7 | Interpreter: letters in, words, a modern Tamil phrase and a plain meaning out. | (qualitative) | credited "Meaning by Ezhuthu" | `src/ezhuthu/agent/interpreter.py` docstring |
| S8 | Tutor: hints and history (ruler, temple, grant) in Tamil, English optional. | The advance / repeat / hint policy is built on Strands Decider with rule guardrails; in the cloud it uses the hosted Strands Decider only when the decider key is configured, otherwise the rules decide and the app shows "decided by rules" | "not yet measured with learners"; do not say a live decider drives the cloud tutor unless `DeciderBackend` = hosted is re-checked | `src/ezhuthu/agent/tutor/policy.py`, `docs/CHARTER.md`, `infra/README.md` "Hosted decider switch" |
| S9 | Expert review queue: what the assistant cannot settle goes to a human. | experts-only route (Cognito group `experts`) | none | `infra/README.md` Access rules |
| S10 | Try it in one click: a gallery of 13 real DHARMA passages. | **10** masked VAL passages + **3** genuine lacunae | none | `README.md`, `eval/reports/2026-11-02-samples.md` |
| S11 | It only fills when it is sure, and when it fills, it matches the editors. | Gallery live run: filled **4 of 10**, **all 4 match** the editors' restoration; 6 left open; edition reading among the 5 candidates on **9 of 10** | "10 gaps are far too few to estimate a rate" (say "in our recorded gallery run") | `eval/reports/2026-11-02-samples.md` |
| S12 | On unsolved lacunae it proposes options and asks an expert. | **4 of 4** unsolved gaps abstain (top confidence 0.107 to 0.150) | none | `eval/reports/2026-11-02-samples.md` |
| S13 | The home hero reads a real Chola-period stone from Thanjavur, letter by letter. | **46** carved letters, each with the model's own probability; mean **0.65**; Opus 4.6, **4** calls | "self-reported, not calibrated"; credit Richard Mortel CC BY 2.0 | `docs/marketing/positioning.md` "The home hero"; current run files `app/web/src/hero/runs/{read,restore,interpret}.json` (commit `fc18763`) |
| S14 | ...and the least certain spot goes to the Restorer, whose calibrated confidence check leaves it open. | 1 letter at 0.45 sent; the Restorer treats it as a **2-letter** gap (`pa[?2]`); best fill **குப்** (ku-p) at **0.08** (0.0823), threshold fitted on VAL **0.4887** (the site shows "8% < 49%"), so it abstains ("?"); top 3: குப் **0.08**, ணம் **0.08** (0.0809), ரம் **0.07** (0.0774); Opus 4.6 escalated, no hosted decider call | "left open"; never round the 0.0774 up | `app/web/src/hero/runs/restore.json` (commit `fc18763`, re-checked 2026-11-03: `gaps[0]`: `gap_chars` 2, `decision` abstain, `abstain_below` 0.4887, `calibration` prerank-ngram); replaces the earlier hosted-decider 0.37 run |
| S15 | ...then words, a phrase in today's Tamil, and its meaning. | **11** words; **3** at 0.5 or more (குளம் 0.75); meaning confidence 0.30 | "Meaning by Ezhuthu", no claim it is right; no published edition of this stone | same; `app/web/public/hero/ATTRIBUTION.md` |
| S16 | Tamil-first and bilingual, mobile-first. | React + Vite PWA | none | `README.md` Architecture |
| S17 | The film's Restore screens are live captures of the public gallery samples. | Fill: `tiruvalisvaram-district-name`, one letter filled with **-க் (-k), 72%**, "The system's fill matches the editors' restoration" (DHARMA Pandya00160). Open: `mamallapuram-calf-pasture`, about **2** letters, abstains, "Unsolved: even the editors left this blank", "Experts are unsure" (DHARMA Pallava00092). Captured 2026-11-03 at 3x DPR (`media/video/capture.mjs` `restore-*-stills`) | a single live run, not a rate (rates: S11, A1, A7). Honest note: the live Restorer is not deterministic; on 2026-11-03 one of four runs of the fill sample filled நாட்டு at 98% ("differs from the editors' restoration"), one timed out (HTTP 500), two filled -க் at 72% | `ezhuthu-video/footage/stills/restore-{fill,open}.json` (outside git) |

## 3. Implementation: agent pipelines on AWS (the technical flex)

### 3a. Agents, tools, knowledge, cloud

| ID | Punchy claim | Exact number / fact | Must keep | Source |
| --- | --- | --- | --- | --- |
| T1 | A Strands **Graph** runs every lesson; a Strands **Swarm** does the teaching inside it. | Graph: `restore` -> `lesson_builder` -> `tutor_team`; `tutor_team` = Swarm of Tutor ⇄ Assessor (offline fallback: template explanation) | none | `src/ezhuthu/agent/tutor/graph.py` docstring |
| T2 | Six specialist agents. | Restorer, Lesson Builder, Tutor, Assessor, Reader, Interpreter | none | `src/ezhuthu/agent/` (restorer, tutor/*, reader, interpreter) |
| T3 | The Restorer is a tool-using Strands agent. | **5** Strands `@tool`s: `retrieve_parallels`, `propose_fills`, `check_constraints`, `rank_and_decide`, `ontology_hints` | the API runs the same steps as a fixed pipeline | `src/ezhuthu/agent/tools.py` |
| T4 | A knowledge graph of Tamil epigraphy, served to the agents over MCP. | OWL ontology: **27** classes, **21** object properties, **1,958** named individuals, **23,029** triples; **5** MCP tools (`find_entities`, `valid_letters`, `formulas_for`, `entity`, `hints_for_gap`) via a Strands `MCPClient` | "built from the train split only" | `ontology/README.md`; `src/ezhuthu/agent/ontology_mcp.py` |
| T5 | Rulers, temples, places, taxes, formulas. | rulers **42**, places **357**, admin units **200**, temples **139**, formulas **14**, taxes **8**, measures **14**, letters **262**, script stages **8**, dynasties **6** | none | `app/web/src/components/how/ontology-slice.json` `counts` |
| T6 | Linked to Wikidata. | dynasties **6/6**, rulers **19/42** with Wikidata IDs | none | same, `wikidata` |
| T7 | Leak-proof by construction. | Ontology built from **862** train editions; **229** held-out editions excluded; enforced by tests | none | `ontology/README.md`; `ontology/coverage.json` |
| T8 | Smart model routing on Amazon Bedrock: Claude Sonnet 4.6 first, Claude Opus 4.6 when it matters. | Escalate to Opus when Sonnet's best score < **0.6**, the gap is over **12** letters, or no good parallel passage | none | `config/models.yaml` `routing`; `docs/CHARTER.md` Decider patterns |
| T9 | Opus where it counts. | On TEST **296 of 413** gaps used Opus (**291** pre-escalated, **5** after Sonnet); **122** Sonnet + **297** Opus calls | none | `eval/reports/2026-11-02-deployed-config.md` |
| T10 | Three signals fused into one score: noisy-OR pre-rank. | pre-rank = noisy-OR(LLM probability, parallel-passage support, character 5-gram share) | none | `config/models.yaml` `restorer.ngram_prerank` |
| T11 | Parallel-passage retrieval over the whole train corpus. | BM25 over character n-grams, re-ranked with rapidfuzz; **14,355** train corpus lines; top **20** parallels | none | `src/ezhuthu/agent/retrieval.py`; `benchmark/stats.json`; `config/models.yaml` |
| T12 | A character 5-gram language model in the loop. | **11 ms** per gap (p50; p90 43 ms) | "p50, Apple M4 Pro" must be on screen with the number (a laptop timing, not cloud latency) | `eval/reports/2026-11-02-deployed-config.md` "5-gram in the runtime" |
| T13 | Calibrated confidence, not vibes: Platt scaling fitted on the validation split. | Opus key n = **224**, threshold **0.4887**; Sonnet key n = **278**, threshold **0.4111** | "fitted on VAL only" | `eval/reports/2026-11-02-deployed-config.md` calibration table; `src/ezhuthu/agent/calibration.py` |
| T14 | A hard 25-second request budget so every answer beats the proxy. | `request_budget_s` **25**; Opus only with **8 s** left; LLM only with **6 s** left; max **8** gaps per request; proxy limit **27 s** (API Gateway 29 s) | none | `config/models.yaml` `restorer`; `eval/reports/2026-11-02-request-budget.md` |
| T15 | Runs on Amazon Bedrock AgentCore Runtime. | Runtime `ezhuthu_tutor`, Python 3.12, Direct Code Deploy, linux/arm64 bundle (~237 MB unpacked, ~67 MB zipped), ontology MCP server inside the bundle | none | `infra/README.md` |
| T16 | Serverless AWS stack, all as code (CDK, TypeScript). | **5** stacks: EzhuthuData (DynamoDB, on demand, PITR), EzhuthuAuth (Cognito, PKCE, `experts` group), EzhuthuAgent (AgentCore Runtime), EzhuthuApi (API Gateway HTTP API + JWT authorizer + Lambda proxy, Node 22 arm64), EzhuthuWeb (private S3 + CloudFront) | none | `infra/README.md` |
| T17 | Secrets stay secret. | The hosted decider key lives only in AWS Secrets Manager; the runtime gets read access to that one secret only when it exists | do not claim the runtime calls the hosted decider for restoration (it does not) | `infra/README.md` "Hosted decider switch" |
| T18 | Model IDs in one file. | `us.anthropic.claude-sonnet-4-6`, `us.anthropic.claude-opus-4-6-v1` | none | `config/models.yaml` |
| T19 | Strands Decider for calibrated decisions. | Tutor policy: advance / repeat / hint (see S8). Restoration ranking: Tamil fine-tuned Strands decision models trained and tested (D1-D8) | "the deployed restorer makes no decider call" | `docs/CHARTER.md`; `eval/reports/2026-11-02-deployed-config.md` |
| T20 | Engineered like a lab. | **461** Python test functions (`grep -r "def test_" tests`, 2026-11-03); `make check` enforces leakage rules and that the README numbers match `stats.json` | none | `tests/`; `benchmark/DATA_CARD.md` leakage table; `tests/test_doc_numbers.py` |

### 3b. The fine-tuned Strands decision models: the effort behind them

What the decider learns: given the restorer's top-3 candidate fills for a gap (or "none"), pick the one the editors
chose. All rows: `origin/team/agent/ft-decider`, `eval/reports/2026-11-02-finetuned-decider.md` unless noted.
Must keep on every row: **"fine-tuned", "tested on held-out TEST", never "live" or "deployed".**

| ID | Punchy claim | Exact number / fact | Must keep | Source |
| --- | --- | --- | --- | --- |
| D1 | We taught a Strands decision model to choose like a Tamil epigrapher's edition. | `ezhuthu-strands-2b-ft`: continue-from of Strands Decider v1-2610 2B, LoRA r **48** (50.5M) + pointer head (3.2M), 1 epoch, **580** steps x 16 rows | "fine-tuned", NOT live | finetuned-decider "Training compute and cost" |
| D2 | Training data built from TRAIN only. | **2,334** choice + **6,936** yes/no rows from **2,337** train items; **1,162** live Sonnet 4.6 calls to build candidates (hard cap 1,200), about USD 4.8 | none | finetuned-decider "Data and leakage controls"; `eval/reports/2026-11-02-ft-data.md` |
| D3 | Cross-fitted, so the model never sees its own answer key. | Train candidates built with retrieval and the 5-gram excluding the item's own fold (**5** folds by stone); audit: **0 of 6,996** train parallels from the item's own fold | none | finetuned-decider; `2026-11-02-ft-data.md` |
| D4 | Near-duplicates scrubbed. | **96 of 2,433** train items dropped (78 matched a TEST item, 18 a VAL item); reverse-direction audit: **1** shared target among 413 TEST items | "at most one TEST item affected" | finetuned-decider |
| D5 | Pre-registered, chosen on VAL, TEST scored once. | Selection rule committed before the VAL runs (commit `2c2f5b2`); **8** decider variants compared on **280** VAL gaps; calibration fitted on VAL (n 443 and 244); TEST scored once, 0 new Bedrock calls | none | finetuned-decider "VAL selection", `preregistration.md` |
| D6 | Three model sizes tried, from 2B down to one that trains in seconds. | ft 2B (A100, 74 min per variant); Sparrow tiny (Ettin-32M, M4 Pro, 21 min); Sparrow nano (static, Tamil WordPiece 8k vocabulary, seconds) | the 2B was chosen | finetuned-decider "Training compute and cost" |
| D7 | Trained for the price of a coffee. | 1x A100 40 GB, **74 min** per variant, 3.5 h total, **USD 2.26** | "fine-tuned", NOT live | same (= A19) |
| D8 | As a decision model it picks the editors' fill on 90.8% of the gaps it can reach. | Decider-only TEST: top-1 **0.5472** against a ceiling of **0.6029** (0.908 when the target is in the top 3); yes/no head AUC **0.971**, ECE 0.015; inside the restorer it fills **57.6%** of TEST gaps with **92.0%** matching | "fine-tuned", "on held-out TEST", NOT live; it is not run routed on TEST | same (= A17, A18) |

## 4. Impact: who it helps

All qualitative; no learner-gain or expert-study number exists yet (L7).

| ID | Punchy claim | Fact | Must keep | Source |
| --- | --- | --- | --- | --- |
| H1 | Students of Tamil, history and epigraphy, and heritage guides. | Guided practice on real stones, L1 to L5, feedback in Tamil first; **1,469** practice items (S2) | "not yet measured with learners" | `docs/marketing/positioning.md` "Who it is for" |
| H2 | Temple visitors and heritage volunteers: point a phone at Tamil text, get letters, words and a meaning to check. | Reader + Interpreter; mobile-first PWA; Tamil and English | Tamil script only; "check against the edition"; no stone-photo accuracy claim (L6) | S6, S7, S16 |
| H3 | New epigraphists: the slow, mentor-bound part of training goes further. | Practice on damaged texts with an assistant that shows its doubts | none | positioning "Who it is for" |
| H4 | Working scholars and the review queue: the AI fills what it is sure of and hands the rest to an expert. | Fills **49.9%** of TEST gaps at **90.8%** match; the rest abstain; experts-only review route (Cognito `experts` group) | "matches the editors' restoration"; "routes doubts to expert review" | A7, S9 |
| H5 | Doubt becomes the lesson. | When the AI is unsure, the learner is told experts are unsure here too | none | S5 |
| H6 | Built for and with the local community. | Planned learner pilot with AWS UG Madurai student volunteers | "planned" / "next"; result TBD | `README.md` "Measured gain"; `docs/CHARTER.md` |

## 5. Achievements (the numbers)

All "TEST" numbers: 413 held-out test gaps from 131 test inscriptions, split by inscription, **scored once**
after every choice was made on validation by a **pre-registered rule**. "Matches" = equals the DHARMA editor's
supplied text after ISO normalisation. Source unless noted: `eval/reports/2026-11-02-deployed-config.md`.

**Lead with A1, A7, A8, A10, A11, A13.** A2-A6, A15, A16, A18 are comparisons: use them in a blog table or to
answer "compared to what?", not as the hook (user direction: no model-vs-model framing).

| ID | Punchy claim | Exact number | Must keep | Source |
| --- | --- | --- | --- | --- |
| A1 | **Headline:** on held-out TEST, the deployed system matches the editors' restoration on 62.7% of gaps. | **259 of 413** = **0.6271** (95% CI 0.5787-0.6731) | "TEST", "matches the editors' restoration" | deployed-config Headline |
| A2 | **+21 points over Claude Sonnet 4.6 alone.** | 0.6271 vs **0.4165** (172/413) = +21.06 points | "Sonnet 4.6 alone" row is from the PR #31 test eval (Sonnet candidates ranked by the local 2B decider); both on the same 413 TEST gaps | `app/web/src/benchmark/summary.json` leaderboard; `eval/reports/2026-11-02-test-eval.md` |
| A3 | Beats a classic character 5-gram language model, with significance. | 0.6271 vs **0.5666**; 34 vs 9 discordant gaps, **p = 0.0002** (exact McNemar) | none | deployed-config |
| A4 | Beats copying the best parallel passage by 15 points. | 0.6271 vs **0.4722**; 88 vs 24, **p < 0.0001** | none | deployed-config |
| A5 | Beats our own earlier pipeline (routed LLMs + local 2B decider). | 0.6271 vs **0.4964**; 74 vs 20, **p < 0.0001** | none | deployed-config |
| A6 | Even on the hard set, where no close parallel exists. | test-hard **182 of 317** = **0.5741**; 5-gram 0.5268 (p = 0.0081), copy 0.3817, Sonnet alone 0.3281 | "hard = no close parallel in another train inscription" | `app/web/src/benchmark/summary.json` (hard leaderboard) |
| A7 | **When it commits, it is right 9 times in 10.** | At its VAL-fitted thresholds it fills **49.9%** of TEST gaps (206) and **90.8%** of those fills match (**187 of 206**) | "matches the editors' restoration", "on TEST" | deployed-config |
| A8 | Its confidence means something. | ECE **0.110**; gaps scored 0.9-1.0: **95** gaps, **97.9%** match | none | deployed-config; `summary.json` `abstention.reliability` |
| A9 | Calibrated on the hard set too. | test-hard: coverage **0.4101**, selective accuracy **0.9077** | none | deployed-config hard subset table |
| A10 | Single letters: three in four. | 1-letter gaps (n = 281): **0.7367**; 2-3 letters (n = 81): **0.5185**; 4+ letters (n = 51): **0.1961** | show all three bins if any is shown | deployed-config "Top-1 by gap length" |
| A11 | Fast and cheap. | latency per gap p50 **3.2 s**, p90 **5.5 s**, max 16.1 s; **0** gaps over 27 s; about **$0.0060 per gap** ($2.49 for 413 gaps, list prices) | "list prices, an estimate, not the bill" | deployed-config |
| A12 | Pallava + Uttiramerur age set. | **0.5686** on 51 TEST gaps; selective accuracy 0.8824 | do NOT call this set "over 1,100 years old" | deployed-config hard/age table |
| A13 | Pre-registered, chosen on validation, test scored once. | rule committed before scoring (commit `1322bdb`); 280 VAL gaps for selection; TEST scored once | none | deployed-config "How the choice was made" |
| A14 | The 25 s budget turned three timeouts into three answers. | Requests of 7, 5, 5 gaps: before **30.8 s, 49.6 s, 58.4 s** (all over 27 s); after **20.9 s, 25.0 s, 25.0 s**; **13/13** gaps the budget did not touch are identical | "n = 3 requests, a latency check, not an accuracy estimate" | `eval/reports/2026-11-02-request-budget.md` |
| A15 | **Fine-tuned 2B Strands Decider beats Claude Sonnet's self-confidence by 26.6 points.** | On the same Sonnet 4.6 candidates, full TEST: fine-tuned **0.6538** (270/413, CI 0.6077-0.6973) vs Sonnet self-confidence **0.3874** (116 vs 6, p < 1e-6) | "fine-tuned", "on held-out TEST"; NOT live | `origin/team/agent/ft-decider:eval/reports/2026-11-02-finetuned-decider.md` |
| A16 | It also beats the base 2B and the deployed ranking on the same candidates. | vs deployed pre-rank 0.5908 (32 vs 6, p = 2.4e-5); vs base 2B 0.5811 (41 vs 11, p = 3.6e-5); TEST-hard **0.5962** | "same Sonnet-only candidates", "not deployed" | same |
| A17 | It knows when it knows. | fills **57.6%** of TEST gaps with **92.0%** of fills matching (238 fills); ECE **0.070** | same | same |
| A18 | As a pure decider it gets 90.8% of the ones it can get. | decider-only top-1 **0.5472** vs ceiling 0.6029 (**0.908** when the target is in the top 3); vs hosted v19 0.4310 (+0.116), base 2B 0.4165, Sonnet self-confidence 0.3826; all p < 1e-8. Yes/no head: AUC **0.971**, ECE 0.015 | same | same |
| A19 | Trained for the price of a coffee. | 1x A100 40 GB, **74 min** per variant, **USD 2.26** total; LoRA r 48 continue-from Strands Decider v1-2610 2B; checkpoint 224 MB; decider time **0.83 s** p50 per gap on an M4 Pro (4.5 s p50 per gap including the LLM, VAL) | "fine-tuned", NOT live | same |
| A20 | Clean training data. | Trained on TRAIN only (2,334 choice + 6,936 yes/no rows); **96** near-duplicate train items dropped | none | same |
| A21 | Reads printed and synthetic Tamil-script text with about 1 letter in 10 wrong. | CER **0.097** on 72 synthetic Tamil-script plates from DHARMA TEST lines (**0.047** clean, 0.052 photo-like, 0.192 weathered); CER **0.093** on 3 real printed Tamil pages | Tamil script only; "synthetic plates" / "printed pages"; never "stone photos"; never "experimental" (ban) | `eval/reports/2026-11-02-ocr-eval.md` |
| A22 | Full eval spend is tiny. | Full TEST run: 122 Sonnet + 300 Opus calls, about $2.50 at list prices; OCR eval about $1.06 | "list prices" | `eval/reports/2026-11-02-test-eval.md`; ocr-eval |

## 6. Madurai and Tamil context (EXTERNAL facts, not Ezhuthu results)

Use only these, only as worded, with the source on the blog / in CREDITS.md where the format allows. Checked
2026-11-03. "Check status" says how the row was verified; rows marked *secondary* must not be strengthened.

| ID | Context line | Exact fact | Must keep | Source (URL) | Check status |
| --- | --- | --- | --- | --- | --- |
| E1 | Tamil is a classical language of India. | The Government of India declared Tamil a Classical Language on **12 October 2004** | "declared by the Government of India" | https://www.pmindia.gov.in/en/news_updates/cabinet-approves-conferring-status-of-classical-language-to-marathi-pali-prakrit-assamese-and-bengali-languages | Official page; text read via search excerpt (direct fetch returned 403). Re-open before publishing. |
| E2 | Tamil Nadu is the heartland of Indian inscriptions. | Tamil Nadu State Department of Archaeology: a 1996 survey places Tamil Nadu's inscriptions "at the top of the list"; Tamil-language inscriptions "amounting nearly 20,000" (all-India count on that page) | quote the department; do not convert to a percentage | https://tnarch.gov.in/epigraphy | Fetched and read 2026-11-03 |
| E3 | The state's own archive of stone rubbings. | Its epigraphy wing has copied "about **24,771** inscriptions" and preserves their estampages (ink impressions); inscriptions there "are deciphered, edited and published" | "about"; "copied" (not "read") | https://tnarch.gov.in/epigraphy | Fetched and read 2026-11-03 |
| E4 | Thousands of Tamil stone rubbings sit in a national archive. | Of **74,000** estampages with the ASI in Mysuru, "about **26,000** are in Tamil" (Tamil Nadu archaeology minister, Nov 2022) | "about"; attribute to the minister | https://www.dtnext.in/amp/story/news/tamilnadu/13k-estampages-of-tamil-received-from-mysuru-thennararu | Fetched and read 2026-11-03 (DT Next, 16 Nov 2022) |
| E5 | Thanjavur's great temple is a UNESCO World Heritage Site. | Brihadisvara Temple, Thanjavur, built by Rajaraja I Chola, completed **1010 CE**; part of UNESCO's "Great Living Chola Temples" (Thanjavur listed 1987, Gangaikondacholapuram and Darasuram added 2004) | "over 1,000 years" (not 1,100) | https://whc.unesco.org/en/list/250 ; https://en.wikipedia.org/wiki/Great_Living_Chola_Temples | UNESCO page returned 403 to the fetcher; years confirmed from UNESCO document excerpts and Wikipedia (*secondary*; sources disagree on 1986 vs 1987 for the series, so say "a UNESCO World Heritage Site" without a year if unsure) |
| E6 | Madurai: temple city on the Vaigai. | The Meenakshi temple stands on the southern bank of the Vaigai River in Madurai; Madurai is described in Sangam-era Tamil texts | no dates beyond "Sangam-era"; no inscription counts for the temple | https://en.wikipedia.org/wiki/Meenakshi_Temple (cites Ramaswamy 2017; Britannica "Sangam literature") | *secondary* (Wikipedia, read 2026-11-03) |
| E7 | Few readers left (the problem in one line). | = P1: In 2021 India had about **23** epigraphists; of nearly 1 lakh inscriptions found since 1886, only 30,000 to 35,000 deciphered and published | "In 2021", "about" | https://thefederal.com/news/inscriptions-languish-as-the-number-of-epigraphists-dwindles | Cited in `README.md` |

**Do not use** (checked and rejected): "60% of India's inscriptions are in Tamil Nadu" / "60,000 of 100,000" (only
via Wikipedia citing a 2005 newspaper report, and E4's minister figure points much lower); Tamil speaker totals
(could not open the Census C-16 table); "Madurai is 2,500 years old" or any city-age figure (no primary source read).

## 7. Honest limits (one line each; use in the blog "What's next" and as a single fast card in the video)

| ID | Limit | Source |
| --- | --- | --- |
| L1 | Long gaps are still hard: on gaps of 4+ letters (n = 51) the deployed system matches 19.6%, the same as copying a parallel. | deployed-config |
| L2 | It abstains on about half of TEST gaps (fills 49.9%); those go to the learner as "experts are unsure" or to expert review. | deployed-config |
| L3 | "Matches the editors' restoration" is not proof of the original text; editors' restorations are expert judgement. | `benchmark/DATA_CARD.md` Known limits |
| L4 | The fine-tuned decider is not deployed (the runtime cannot serve a local checkpoint), and on the frozen 60-item TEST-hard benchmark it ties Sonnet (0.400) and is below hosted v19 (0.450, p = 0.375). | finetuned-decider report |
| L5 | Ontology hints made no measurable difference to restoration (88 hinted gaps, 3 gained, 3 lost; hint hit@5 on held-out TEST 16/253). | test-eval; `ontology/hint_eval.json` |
| L6 | Photo reading fails on Tamil-Brahmi (CER 0.83 to 0.91 on 3 real images), Grantha is 0.56 (synthetic), Vatteluttu is unmeasured, and no real stone photo has been scored against an edition. | ocr-eval |
| L7 | Learner gain (pre/post test) and the expert studies have not run yet. | `README.md` (TBD); `docs/expert-validation/` |
| L8 | Public sources: a hosted LLM may have seen DHARMA or *South Indian Inscriptions* texts in pretraining; this cannot be ruled out. | `benchmark/DATA_CARD.md` Known residual risks |
| L9 | L5 Tamil-Brahmi lessons teach letters from transliterated text: the DHARMA Tamil collections used have no Tamil-Brahmi editions. | `docs/marketing/positioning.md` |
| L10 | Vatteluttu glyphs and new Tamil strings await expert / native-speaker review. | `README.md`; practice bank meta |
| L11 | Very long requests: the 25 s budget trades fills on late gaps (abstain `time_budget`) for an answer inside 27 s. | request-budget |
| L12 | The corpus has one edition from Madurai's Meenakshi temple and six from Thanjavur's Brihadisvara; most editions come from other temples across Tamil Nadu. Say "Tamil Nadu's temples", not "Madurai's inscriptions", for the benchmark. | P12 |
| L13 | In the cloud, the tutor's decisions come from rules unless the hosted Strands Decider key is configured (not configured at `d4ea3b3`). | `infra/README.md` "Hosted decider switch" |

## 8. Visual assets available (in the repo; reference by path, copy binaries to `ezhuthu-video/` not git)

| Asset | Path | Notes |
| --- | --- | --- |
| Logo mark, lockups, Tamil and English wordmarks (SVG; PNG for some) | `design/brand/logo/*.svg`, `design/brand/logo/png/` | color, mono, reversed variants; `construction.svg` shows the mark's geometry |
| Brand guide, fonts | `design/brand/BRAND.md`, `design/brand/FONTS.md`, `design/tokens/tokens.css` / `tokens.json` | colours: ink #1D1611, terracotta #9B3D22, ochre #D2891C, indigo #3B4787, green #2C6534 (README badges) |
| **Hero stone animation** (the real Thanjavur photo read letter by letter) | `design/brand/banners/hero-stone.webm` (1440x900 light), `hero-stone-dark.webm`, `hero-stone-phone.webm` (375x740, Tamil), `hero-stone.gif`, `hero-stone-poster.png` | credit Richard Mortel CC BY 2.0 on screen |
| Hero contact sheet (one frame per second) | `design/hero/contact-sheet.png` | storyboard reference |
| Hero source crop and letter boxes | `design/hero/thanjavur-crop.jpg`, `design/hero/boxes-overlay.jpg`, `design/hero/boxes.json` | for zoom/box animations |
| Hero photo, web sizes | `app/web/public/hero/thanjavur-{480,800,1568}.{jpg,webp,avif}` | |
| **Letter evolution** (ka across 5 eras) | `docs/media/hero-evolution.webm`, `hero-evolution-dark.webm`, `hero-evolution-poster.jpg` | traced, then filled, stage by stage |
| Evolution strips and glyph cards | `design/glyphs/evolution-strip-{light,dark}.svg`, `design/renders/glyphs/evolution-strip-{light,dark}.png`, `design/glyphs/glyph-card-{light,dark}.svg`, `design/glyphs/hero-evolution.json` | |
| Vatteluttu drawn glyphs | `design/glyphs/vatteluttu/*.svg` (7) | teaching shapes, pending review |
| README hero, social preview, OG image | `design/brand/banners/readme-hero-{light,dark}.{png,svg}`, `social-preview*.{png,svg}`, `og-image.svg`, `design/brand/icons/og-image.png` | still carry the older tagline |
| **Builder Center header** | `design/brand/banners/builder-center-header.{png,svg}` | blog header |
| **Video title cards** (existing) | `design/brand/banners/video/00-title-{light,dark}`, `01-problem`, `02-how`, `03-restore`, `04-results`, `05-credits` (`.png` + `.svg`) | re-check their numbers against this file before use |
| App screenshots (desktop + mobile, Tamil + English, light + dark) | `app/web/screenshots/desktop-01..18-*.{png,jpg}`, `mobile-01..18-*.{png,jpg}` | home, practice levels, Brahmi hint, restore, progress, benchmark report, review, about, rules, dark mode, samples gallery, restore from sample, read upload, read warning. Older shots say "Learn"/"Test" (renamed Practice/Benchmark) |
| Positioning before/after shots | `docs/media/positioning-c/{before,after}-{home,about}-{desktop,mobile}-{en,ta}.jpg` | current home copy ("after-*") |
| UX wireframe renders, design preview | `design/renders/ux/01-learn..06-states.png`, `design/renders/preview-{light,dark,mobile}.png` | |
| Live pages to screen-record | https://d3jz2k92ne5puo.cloudfront.net (Home hero, Practice, Restore, How it works animated overview, Benchmark leaderboard + reliability chart) | |
| Architecture diagram source | `README.md` mermaid ("How it works"); `infra/README.md` ASCII diagram | redraw for video |
| Benchmark chart data | `app/web/src/benchmark/summary.json` (leaderboards full/hard, reliability bins, gap-length bins) | use for animated bar charts |
