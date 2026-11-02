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

## Strands multi-agent design (loops to swarms)
A Strands **Graph** (fixed lesson flow), with a **Swarm** inside the tutoring step:
- **Restorer agent:** retrieves parallel passages, proposes fills (Sonnet 4.6, escalating to Opus 4.6), checks the ontology, and lets the decider rank or abstain.
- **Lesson Builder agent:** builds a levelled practice set from a restored inscription: letters by era (Aksharamukha plus ontology), words, then a line.
- **Tutor agent:** runs the practice in Tamil, gives hints, and explains the history (ruler, temple, grant) from the ontology.
- **Assessor agent:** grades answers. The decider makes the pedagogy decision (advance, repeat or hint) and records the pre/post scores.

## Decider patterns (reusable)
1. **Restoration choice and abstention:** `choice` over candidate fills, giving a confidence or "abstain".
2. **Model routing:** escalate from Sonnet to Opus only when needed.
3. **Learning policy:** `choice` of advance, repeat or hint from the learner state (the "guardrails/policy" pattern).

## Non-goals for v1
Reliable automatic reading of stone photographs. Photo reading (`POST /api/read`, upload in the app) is
**experimental** and labelled so in Tamil and English: measured CER 0.10 on 72 synthetic Tamil-script plates from
DHARMA TEST lines (0.05 unless weathered) and 0.09 on 3 real printed Tamil pages, but CER 0.86 on 3 real
Tamil-Brahmi images (it does not read Tamil-Brahmi), 0.56 on synthetic Grantha, and Vatteluttu is unmeasured (no
Unicode font). Numbers: `eval/reports/2026-11-02-ocr-eval.md`. Also out of scope: palm-leaf manuscripts and
Indus-script claims.

## Rules
- Branding: say "built with Strands Agents" and "built with AWS Context Ontology Accelerator". Never "Strands AI" or "AWS AI".
- Restorations are described as "matches expert restorations", never "correct".
- "1,100 years old" applies only to the Pallava collection (410 restorations). The age set also includes 9 Uttiramerur restorations, and Uttiramerur holds later Chola and Vijayanagara inscriptions, so do not call the whole age set "over 1,100 years old".
- Credit DHARMA (CC BY-SA 4.0; the derived benchmark is shared under the same licence). Use the Tamil Lexicon for lookups only. No scraped data.
- Every claim in the README and video is backed by a number in `eval/reports/`.
