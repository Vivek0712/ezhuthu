# Ezhuthu charter

**Ezhuthu (எழுத்து, "letter/script")**: an AI tutor that teaches Tamil learners to read 2,000 years of their own inscriptions, from Tamil-Brahmi to Chola-era Tamil, in their first language. It is built with Strands Agents, uses Strands Decider for calibrated decisions, and is deployed on Amazon Bedrock AgentCore.

## Hackathon fit: Education track (social good)
- **Underserved learners:** Tamil-medium school and college students, rural heritage guides near monument sites, and self-learners. Most of them cannot read the inscriptions on their own village temples. There is no learning tool for old Tamil scripts in Tamil, and India has about 23 working epigraphists for a backlog of about 70,000 unread inscriptions (The Federal, 2021).
- **The track examples, mapped:**
  - "A tutor that turns a textbook chapter into a guided practice set": Ezhuthu turns a real inscription into a guided reading practice set.
  - "Feedback in the user's first language": all feedback is in Tamil, with English optional.
  - "Leveled passages for a mixed-level class": the same text at five levels (modern Tamil, then Chola Tamil, Pallava, Vatteluttu, Tamil-Brahmi).
- **Measurable improvement:** built-in pre-test and post-test on reading letters by era. The app reports each learner's gain in letters read correctly and time per letter. A pilot with AWS UG Madurai student volunteers produces the headline number. A simulated-learner evaluation checks the instrument before any real learners use it.

## Engine: AI restoration of damaged inscriptions
Practice texts come from 1,320 published DHARMA editions (the edition files declare CC BY-SA 4.0), 858 (65%) of which have damaged passages. A restoration agent proposes the missing letters with calibrated confidence. It abstains when unsure, and the tutor then labels the gap as "experts are unsure", which is itself a teaching moment. The engine is evaluated on a benchmark of 3,289 expert restorations in Tamil lines (test 413, of which 317 are hard: no close parallel in the training inscriptions), including 410 in Pallava inscriptions over 1,100 years old (the benchmark's age set adds 9 from Uttiramerur, 419 in all). Numbers: `benchmark/DATA_CARD.md` and `benchmark/stats.json`. Splits are by inscription, and retrieval and the ontology read the train split only (data card, "Leakage").

**Measured (test, scored once, settings chosen on validation; `eval/reports/2026-11-02-test-eval.md`):** the shipped engine's top fill matches the expert restoration on 205 of 413 test gaps (49.6%), against 47.2% for copying the best parallel passage (not a significant difference) and 57.1% for a character 5-gram model, which is the strongest restorer measured so far. At its validation-fitted abstain threshold the engine fills 46.5% of gaps and 63.5% of those fills match the expert. Escalation to Opus 4.6 is what lifts the engine above Sonnet 4.6 alone (41.6%). 68% of test gaps are a single letter; on gaps of 4 or more letters no system matches the expert on more than 1 in 3. Ontology hints made no measurable difference (88 hinted gaps, 3 matches gained and 3 lost).

## Strands multi-agent design (loops to swarms)
A Strands **Graph** (fixed lesson flow), with a **Swarm** inside the tutoring step:
- **Restorer agent:** retrieves parallel passages, proposes fills (Sonnet 4.6, escalating to Opus 4.6), checks the ontology, ranks the candidates (the 2B decider's `noul` on the top 3 once an LLM answered) and fills or abstains at a threshold fitted on the validation split.
- **Lesson Builder agent:** builds a levelled practice set from a restored inscription: letters by era (Aksharamukha plus ontology), words, then a line.
- **Tutor agent:** runs the practice in Tamil, gives hints, and explains the history (ruler, temple, grant) from the ontology.
- **Assessor agent:** grades answers. The decider makes the pedagogy decision (advance, repeat or hint) and records the pre/post scores.

## Decider patterns (reusable)
1. **Restoration ranking and abstention:** the local 2B decider (`strands-decider-2B-qwen3.5-v1-2610`) asks `noul` ("is this the expert's restoration?") of the top 3 LLM candidates; its probability, calibrated on the validation split, decides fill or abstain. This won on validation, but **on test it ranks no better than the decider-free pre-rank** (27 vs 28 discordant gaps with Sonnet, 25 vs 29 routed), and on retrieval-only candidates the validation-best decider variant (`choice-all`) is below the decider-free pre-rank (42.4% vs 48.7%, p = 0.021). Restoration quality does not come from the decider: matching fills come from the parallels, the 5-gram and the LLMs. The hosted v19 decider (decider-cloud, used by the cloud runtime) has not been measured on restoration.
2. **Model routing:** escalate from Sonnet to Opus when the decider's confidence in Sonnet's best candidate is under 0.6 (kept on validation), when the gap is over 12 letters, or when no parallel passage matches well. On test, 299 of 413 gaps reach Opus, 291 of them by the last two rules.
3. **Learning policy:** `choice` of advance, repeat or hint from the learner state (the "guardrails/policy" pattern). Not yet measured with learners.

## Non-goals for v1
Reading stone photographs automatically (photos are shown, not read), palm-leaf manuscripts, and Indus-script claims.

## Rules
- Branding: say "built with Strands Agents" and "built with AWS Context Ontology Accelerator". Never "Strands AI" or "AWS AI".
- Restorations are described as "matches expert restorations", never "correct".
- "1,100 years old" applies only to the Pallava collection (410 restorations). The age set also includes 9 Uttiramerur restorations, and Uttiramerur holds later Chola and Vijayanagara inscriptions, so do not call the whole age set "over 1,100 years old".
- Credit DHARMA (CC BY-SA 4.0; the derived benchmark is shared under the same licence). Use the Tamil Lexicon for lookups only. No scraped data.
- Every claim in the README and video is backed by a number in `eval/reports/`.
