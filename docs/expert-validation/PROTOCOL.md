# Expert validation protocol (v1)

Owner: QA team (`u:qa`). Code: `src/ezhuthu/expert/` (`python -m ezhuthu.expert`). Tests: `tests/expert/`.

Agents cannot stand in for epigraphists. The benchmark tells us how often a proposal **matches the edition**.
It cannot tell us whether a proposal for a passage the editors left blank is a plausible reading, or whether
the tool helps a human reader. This protocol measures both with real experts, blind, at a cost of about two
hours per expert. Every number it produces goes into `eval/reports/qa-expert-validation-<date>.md`. The
charter wording rule applies there too: write "rated plausible by N of M epigraphists" or "matches the
edition", never "correct".

## 1. Questions

| # | Question | Study | Main measure |
|---|---|---|---|
| Q1 | Do experts agree with each other when they rate restorations? Without agreement, no other number means much. | A | Fleiss' kappa over all raters, pairwise Cohen's kappa (unweighted and quadratic-weighted) |
| Q2 | On passages the editors left blank, does the AI propose readings that experts find plausible? | A, blank items | share of passages with at least one AI proposal whose mean rating is 3 or more |
| Q3 | When the editors' fill is known, how do blind experts rate the AI proposals against it? | A, masked items | mean rating, edition fill minus best AI option (paired by passage) |
| Q4 | Does the AI's confidence track expert judgement? | A | Spearman correlation of AI confidence with the mean expert rating |
| Q5 | Do experts restore better or faster with the AI's suggestions than without them? | B | exact match with the edition and CER, per condition; time per passage |

## 2. Materials

- **Blank passages** (`benchmark/blank.jsonl`, `kind: blank`): `<gap>` spans with a known size and no expert
  fill. By default they are drawn from **test and val** inscriptions, which are not in the retrieval corpus.
- **Masked restorations** (`benchmark/items.test.jsonl`): `<supplied>` spans whose fill the edition gives. The
  fill is hidden and shown again as one option among the AI's.
- **Eligibility** (`SampleSpec`): gap of 2 to 12 Tamil letters; at least 15 letters of context; at most 3 other
  gap markers in the context; at most 2 passages per inscription (passages from one inscription are
  correlated); about 30% of masked passages come from the age set (Pallava and Uttiramerur).
- **AI proposals** (`propose`): the production restorer with ontology OFF, because the current ontology build
  reads val/test text (KrewHQ gotcha 01M6CBX5). Retrieval runs over `benchmark/corpus_lines.jsonl`, which holds
  train lines only and refuses to load if a held-out inscription appears in it. The decider is refused on
  purpose, so the ranking is the restorer's flagged fallback: the LLM's self-reported confidence, else the
  retrieval heuristic. The 2B decider abstains on everything at the current threshold
  (`eval/reports/2026-11-02-decider-benchmark.md`), so it is not used here. The LLM runs only with
  `EZHUTHU_LIVE=1`; the call cap is 40, one call per passage, with model IDs from `config/models.yaml`. The
  output budget is 2,048 tokens, because the pipeline's 800 truncates (quick-eval finding 1).
- **Sampling is seeded** (default seed 2026). `sample.jsonl.meta.json` records the SHA-256 prefixes of the
  input files, so the same seed and the same files always give the same packet.

## 3. Study A: blind plausibility rating

**Items.** Each rating item is one passage with exactly `k` options (default 3), whatever its kind:

- masked passage: the edition's fill plus the top `k-1` distinct AI proposals;
- blank passage: the top `k` distinct AI proposals.

A fixed `k` means the number of options does not reveal whether an item is masked or blank. If the AI also
proposed the edition's fill, it is shown once and `key.json` marks it `also_proposed_by_ai`. If an item has
fewer than `k` distinct options, a pre-drawn spare replaces it, and the packet records the drop.

**Blinding.**

- All options are written in one spelling: editorial marks, hyphens and `·` are removed and the text is
  lower-cased. The edition's typography therefore cannot give its fill away.
- The options are shuffled with a seed and labelled A, B, C. Item codes (`P01`...) are opaque, and each
  rater gets the items in a different order.
- Raters do not see the source, model, rank or confidence of any option. Only
  `coordinator/key.json` holds them, and only the coordinator opens it.
- A test (`tests/expert/test_packet.py::test_sheets_are_blind_bilingual_and_complete`) checks that no sheet
  contains a source tag, a confidence value, an item's internal id or the words masked, blank or expert.
- The DHARMA source link is on the sheet because experts need the inscription's context: place, date and
  photograph. Raters are asked to open it **only after rating** that passage, because for masked passages
  the edition shows the fill. Two columns record honesty flags: `consulted_edition_before_rating_y` and
  `knew_this_text_y`. Ratings flagged in either column are left out of the main analysis, counted, and
  included in a sensitivity row.

**Known residual cue.** For a masked passage, the gap size shown is the edition fill's own length in letters.
For a blank passage, it is the editor's estimate. A rater who counts letters may therefore single out the
option whose length matches exactly. The restorer already filters AI options to about +/-34% of the gap, so
most options are close in length, but not all. The analysis reports, for each rater, how often the edition
fill got their top score. If one rater is far above the others, read their masked-item ratings with this cue
in mind. Blank passages carry no such cue, because they have no edition fill.

**Scale** (on every sheet in Tamil and English):

| score | meaning |
|---|---|
| 4 | Highly plausible: I would accept this reading in an edition |
| 3 | Plausible: fits the context; other readings are about as likely |
| 2 | Unlikely: possible only with problems of language, length or formula |
| 1 | Implausible: ruled out by script, language, length or context |
| ? | Cannot judge (`cannot_judge_y = y`); left out of every statistic and counted |

Options on one passage are rated independently, so ties are allowed. The scale has no midpoint, so raters
must lean either "plausible" (3 or 4) or "not plausible" (1 or 2). The binary split at 3 is reported next to
the 4-point results.

**Raters.** At least 3, ideally 4 to 6, who read Tamil inscriptions professionally: epigraphists, editors
of the DHARMA Tamil corpora, and university faculty in Tamil epigraphy. Each rater has a code (`R1`...), never
a name, on the sheets. All raters rate all items: a fully crossed design, which Fleiss' kappa and the
pairwise Cohen's kappas need.

**Analysis** (`analyze`). The unit is one option of one passage.

- **Agreement.**
  - Fleiss' kappa on the 4 categories and on the binary split (3 or more versus less). If raters skipped
    units, units with fewer than 2 ratings are dropped and the standard pair-weighted generalisation is used.
  - Cohen's kappa for every pair of raters, unweighted and quadratic-weighted (the scale is ordinal), and
    their means.
  - Percent agreement.
  - Reading guide (Landis and Koch, as a convention, not a law): below 0.2 slight, 0.21 to 0.4 fair, 0.41
    to 0.6 moderate, above 0.6 substantial. If the binary kappa is below 0.4, Q2 to Q4 are reported as
    exploratory.
- **Plausibility by origin.** For each option, the mean rating over raters. For each group (edition fill,
  AI on masked passages, AI on blank passages, AI by source: llm, retrieval or n-gram), the mean of those
  means and the share of options at 3 or above. The 95% CIs come from a percentile bootstrap that resamples
  whole inscriptions.
- **Masked passages.** Per passage: the edition fill's mean minus the best AI option's mean (bootstrap CI);
  the share of passages where the best AI option is rated at least as high as the edition fill; and, for
  each rater, how often the edition fill got that rater's top score. The last figure is a sanity check that
  raters engage with the task.
- **Blank passages.** The share of passages with at least one AI option at a mean of 3 or above.
- **Calibration.** Spearman correlation of AI confidence with the mean rating.

## 4. Study B: reading study with and without AI (after Ithaca)

The design follows Assael et al., "Restoring and attributing ancient texts using deep neural networks",
*Nature* 603 (2022). Historians restored Greek inscriptions on their own and then with Ithaca's ranked
suggestions, and the paper reports the accuracy of the expert alone, the model alone and the expert with the
model. Here:

- **Items:** masked test passages (the edition's fill is the reference), **disjoint** from the Study A items
  (`role: reading`, default 12).
- **Counterbalanced forms:** the items are split into halves H1 and H2. Form A has H1 unaided, then H2 with
  AI. Form B has H2 unaided, then H1 with AI. Raters alternate between forms (`assignments.json`). Every
  passage is therefore seen unaided by some raters and with AI by others, and no rater sees one passage
  twice.
- **Block order:** the unaided block always comes first, so the AI's suggestions cannot prime an unaided
  answer.
- **AI-assisted condition:** the top 3 AI suggestions, each with its confidence as a percentage, as Ithaca
  showed its ranked list.
- **Responses:** the restoration in Tamil script or ISO-15919, a confidence from 1 to 4, seconds taken
  (self-timed), and the same two honesty flags as in Study A.
- **Session order:** Study B first, then Study A. Study A shows edition fills (blind), which could teach
  formulae that help in Study B.
- **Scoring:** answers are compared on letters only (`normalise_for_scoring`), and Tamil-script answers are
  converted to ISO first. Hyphens, spaces and editorial marks therefore never count against an expert.
  Measures: exact match, character error rate clipped to 1, median seconds and mean confidence, per
  condition. An empty answer is scored as wrong (CER 1), and the answered share is reported.
- **Comparison:**
  - paired by passage: mean accuracy with AI minus without, with a bootstrap CI over passages and an exact
    sign test;
  - per rater: the difference between conditions (on different passages) and a sign test;
  - "AI alone": the top suggestion's exact match on the same passages.
- **Power, stated honestly:** with 12 passages and 4 raters (48 answers) the study can show only large
  effects, such as the roughly 25-point gain Ithaca reported. Read it as a pilot that estimates effect size
  and timing for a larger study, not as a significance test.

## 5. Running a round

1. **Packet** (coordinator):

   ```bash
   python -m ezhuthu.expert sample   --out kit/sample.jsonl                      # seeded, offline
   EZHUTHU_LIVE=1 python -m ezhuthu.expert propose --sample kit/sample.jsonl \
       --out kit/proposals.jsonl --router sonnet                                 # <= 40 Bedrock calls
   python -m ezhuthu.expert generate --sample kit/sample.jsonl --proposals kit/proposals.jsonl \
       --raters R1,R2,R3,R4 --out kit/packet --pdf                               # CSV + HTML (+ PDF)
   ```

   Send each rater only `kit/packet/raters/<code>/`. Keep `kit/packet/coordinator/` private.
2. **Pilot:** first with 1 or 2 friendly experts on 5 items. Fix wording and confirm the timing, then freeze
   the packet. Any change after that point means a new seed and a new packet version.
3. **Sessions:** Study B (about 30 to 40 minutes), a break, then Study A (about 45 to 60 minutes). These
   times are estimates for the pilot to confirm. Remote sessions use the CSV or HTML; in-person sessions use
   the PDF.
4. **Returns:** collect the filled CSVs. For paper forms, the coordinator types them into the rater's CSV.
   Store them outside git under `data/expert-validation/<round>/` (gitignored).
5. **Analysis:**

   ```bash
   python -m ezhuthu.expert analyze --key kit/packet/coordinator/key.json \
       --out data/expert-validation/<round>/results data/expert-validation/<round>/returned/
   ```

   Malformed sheets (a score outside 1 to 4, a duplicate, an unknown item) stop the run with a message.
   Nothing is guessed. Copy the generated markdown to `eval/reports/qa-expert-validation-<date>.md` and add
   the caveats.
6. **Dry run:** `python -m ezhuthu.expert synth --key ... --out ...` writes synthetic sheets (raters `SYN-*`)
   so the analysis can be exercised end to end. Every report built from them carries a
   **SYNTHETIC RATINGS** banner, and mixing synthetic and real raters is refused.

## 6. Data, consent and leakage rules

- **Consent:** raters agree to take part, to have their **anonymised** ratings analysed, and, only if they
  opt in, to be thanked by name in the report. Rater codes link to names in one private file held by the
  coordinator, never in git.
- **Test-set hygiene:**
  - Study A and Study B use test and val passages.
  - Ratings, expert answers and comments on these passages must **never** enter the retrieval corpus, the
    ontology, few-shot prompts, decider training or any fine-tuning data.
  - The packet's `key.json` holds test fills, which are already in `benchmark/`. It is not training data
    and must not be used as such.
  - Raters' new readings of blank passages are valuable, but they stay in the validation store unless
    the data team deliberately adds them to a train-split resource, with credit and licence.
- **Licence:** passage text is from DHARMA editions under CC BY-SA 4.0 (`benchmark/DATA_CARD.md`). Every
  sheet carries the source link and the attribution line.
- **Nothing is sent automatically.** The kit writes files and the coordinator sends them by hand. The
  outreach templates are in `OUTREACH.md`.

## 7. The app's Review queue and this protocol

The app already has an expert **Review queue** (`/review`; `GET /api/queue`, `POST /api/queue/{id}` with
`approve | edit | reject`, reviewer token). Learners' corrections (`POST /api/corrections`) and abstained gaps
wait there for an expert. The queue and this kit are two channels with different jobs:

| | Review queue (operational) | Expert-validation kit (measurement) |
|---|---|---|
| purpose | curate fills shown to learners | measure plausibility, agreement and uplift |
| blinding | none: the reviewer sees the proposal and who sent it | full: source, model and confidence hidden |
| items | whatever users send, so biased | seeded sample, so representative |
| output | an approved, edited or rejected text | ratings from 1 to 4, kappas, CIs |

How the two connect. Rule 1 holds now. Rules 2 to 4 are the design for the next app iteration and are not
implemented in this PR.

1. **Queue decisions are not validation evidence.** A reviewer who sees the AI's proposal and its source is
   anchored, so the report never counts approval rates from the queue as plausibility. Only blind ratings
   from this kit count.
2. **Blind-first review mode** (proposed, for the app team): for an abstained gap, the queue first shows the
   kit's view: up to 3 options in the same spelling and shuffled, with no confidence. It asks for a score
   from 1 to 4 for each, and only then reveals the AI's choice and the approve, edit and reject buttons. The
   scores are stored on the queue item (`history[].ratings`) in the kit's CSV columns, so
   `python -m ezhuthu.expert analyze` can read an export directly. Mapping: approve means score 4 for the
   accepted text. Edit means the expert's text becomes a new option to rate blind in the next audit
   round. Reject means a score of 2 or less for the shown proposal.
3. **Periodic audit** (proposed): each round, sample about 20 approved or edited queue items into a kit
   packet as extra masked-style items, with the reviewer's text in place of the edition's fill. Blind
   raters then check the queue's decisions, and the agreement between the queue reviewer and the blind
   panel is reported with the same kappas.
4. **Held-out flag** (proposed, for the agent and app teams): a queue item whose gap lies in a val or test
   inscription is tagged `held_out` when it is created. Its approved text is shown to learners but excluded
   from every training or retrieval export, the same rule as section 6.

The queue reviewer role (`auth.expertRequired`, the experts group) and the kit's raters are the same pool of
people. The outreach email invites them to both: a one-off blind study, then optional ongoing review.
