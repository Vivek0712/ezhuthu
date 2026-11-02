# Positioning C: an apprenticeship tool for Tamil epigraphy

**Status:** adopted by the project lead on 2026-11-02 (option C of the positioning brief). The app copy, navigation,
home hero and brand voice follow it in the PR that adds this file. **README.md and docs/CHARTER.md are not edited
here** (PR #31 owns them): the proposed copy for both is at the end of this page, for the lead to apply at wrap-up.

## Positioning statement

Ezhuthu is an apprenticeship tool for Tamil epigraphy. It trains students and new epigraphists to read real, damaged
inscriptions, and gives working scholars a restoration assistant that shows how sure it is, abstains when it is not,
and routes those doubts to expert review.

## Tagline

- **EN:** *Learn to read the stone. Help read the backlog.*
- **TA:** *கல்வெட்டைப் படிக்கக் கற்றுக்கொள்ளுங்கள்; காத்திருக்கும் கல்வெட்டுகளைப் படிக்க உதவுங்கள்.*
  **Pending a native-speaker check** (flagged in a comment in `app/web/src/i18n/strings.ts`; the same line is the
  Tamil home heading, so change both together).

## Who it is for

1. **Students** of Tamil, history and epigraphy, and heritage guides: guided practice on real stones, L1 to L5, with
   feedback in Tamil first.
2. **New epigraphists:** practice on damaged texts with an assistant that shows its doubts, so the slow,
   mentor-bound part of training goes further.
3. **Working scholars:** read (photo or EpiDoc), restore with confidence, see the parallels behind each fill, and
   settle what the assistant sends to the expert review queue.

## Elevator pitch (three sentences)

In 2021 India had about 23 epigraphists; of nearly 1 lakh inscriptions found since 1886, only 30,000 to 35,000 had
been deciphered and published (The Federal, 3 Aug 2021). Ezhuthu turns 1,320 real DHARMA inscriptions into levelled
reading practice with feedback in Tamil, from modern Tamil back through Chola and Pallava letters. Its restoration
assistant, built with Strands Agents and Strands Decider, ranks fills, abstains when unsure and sends those cases to an
expert review queue, and every number it shows is published in `eval/reports/`.

## Names in the app

| Before | Now (EN / TA) | Route |
| --- | --- | --- |
| Learn | **Practice** / பயிற்சி | `/practice` (`/learn` redirects, query and state kept) |
| Restore | Restore / மீட்டமை (unchanged) | `/restore` |
| Test ("Test the engine") | **Benchmark** / அளவுகோல் (avoids confusion with the learner pre/post test) | `/benchmark` (`/test` redirects) |
| Review ("Review queue") | **Expert review** / வல்லுநர் மதிப்பாய்வு (bottom tab: "Review" / மதிப்பாய்வு, for width) | `/review` (unchanged) |
| Progress | Progress / முன்னேற்றம் (unchanged) | `/progress` |
| "An AI tutor for Tamil inscriptions" | "An apprenticeship in Tamil epigraphy" / கல்வெட்டியல் பயிற்சித் துணை | |

## Claims we can make (with their source)

| Claim | Number | Source |
| --- | --- | --- |
| Corpus | 1,320 DHARMA inscriptions, 65% damaged | `benchmark/DATA_CARD.md` |
| Expert restorations in the benchmark | 3,289 (test 413, test-hard 317) | `benchmark/DATA_CARD.md` |
| Fills that match the expert restoration (top-1, test, local 2B decider) | **49.6%** (205 of 413); copy-from-parallel 47.2% (not significantly different), character 5-gram **56.7%** | `eval/reports/2026-11-02-test-eval.md` |
| **Abstaining buys accuracy** (our one defensible engine claim) | at the VAL-fitted threshold the engine fills 46.5% of test gaps and **63.5% of those fills match the expert**, vs 49.6% overall (N = 413) | `eval/reports/2026-11-02-test-eval.md` |
| The same on the cloud runtime's deciders | 60 test-hard items only: hosted decider top-1 0.45 abstaining on 83%; self-report 0.40 overall, 0.67 on the 55% kept | `eval/reports/2026-11-02-decider-benchmark.md` |
| Photo reading of Tamil script (experimental) | CER 0.10 on 72 synthetic plates (0.05 clean), 0.09 on 3 real printed pages; **not measured on real stones** | `eval/reports/2026-11-02-ocr-eval.md` |
| Photo reading of Tamil-Brahmi | **fails**: CER 0.83 to 0.91 on 3 real images | `eval/reports/2026-11-02-ocr-eval.md` |
| Restorations in inscriptions over 1,100 years old | 410, Pallava collection only | `benchmark/DATA_CARD.md` |
| Learner gain; expert with/without-AI study (Study B) | **TBD** | `docs/expert-validation/` |

## Claims we never make

- That restorations are "correct" or "accurate". Say they **match expert restorations**, with N.
- That it reads Tamil-Brahmi, Grantha or Vatteluttu from photos.
- That it clears the backlog, replaces epigraphists or deciphers inscriptions.
- That scholars have validated it (Study A and Study B have not run).
- That L5 lessons come from Tamil-Brahmi editions: the corpus has none, so L5 teaches the letters from transliterated
  text.
- "Over 1,100 years old" for anything except the Pallava collection (410).
- Any top-1, ECE or learner-gain number that `eval/reports/` does not hold.
- "Strands AI" or "AWS AI". Say **built with Strands Agents**.
- "A backlog of about 70,000". Use the Federal wording above.

**Correction to the positioning brief.** The brief (`05-positioning-ologists.md`) says the ontology build leaks
val/test inscriptions. That is wrong and must not be repeated: the shipped ontology is built from the train split
only, and tests enforce it (`tests/ontology/test_artefacts.py::test_shipped_build_is_train_split_only`,
`tests/ontology/test_splits.py`; data card, "Leakage").

## The home hero, and why it is honest

The home page opens on a **real photograph** of a Chola-period inscription on the Brihadisvara temple, Thanjavur
(Richard Mortel, CC BY 2.0, via Wikimedia Commons; `app/web/public/hero/ATTRIBUTION.md`). The animation lights the
carved letters on hand-annotated boxes, then **matches them letter by letter**: the first few one at a time in a card
(the carved glyph, zoomed -> the modern Tamil letter -> a ring filling to the Reader's confidence), then a fast
cascade of badges over the other boxes. The letter the Reader was least sure of goes to the Restorer and the Strands
Decider; then the letters fly past the pipeline and assemble into the reading, run together as carved. The
Interpreter then **slides them apart into words**, **arranges the words as a phrase in today's Tamil**, and gives
**the meaning in English and in Tamil**; the finished frame (stone | phrase and meaning) is held for 3 s and the meaning
crossfades into the next cycle. Everything it shows is the **actual output** of our system on that photo (`app/web/src/hero/hero-reading.json`, built by `scripts/hero_read.py` and
`scripts/hero_build.py`; models from `config/models.yaml`):

- **Letter by letter** (`Reader.read_glyphs`, Opus 4.6, one call per row of boxes, 4 calls): 46 boxes, each named as a
  modern Tamil letter with the model's own probability (self-reported, not calibrated). Mean **0.65**; per row 0.68,
  0.67, 0.65, 0.60.
- One letter (line 3, box 2: ண்ணி at 0.45) is under the 0.5 cut-off, so it was sent to the Restorer as a gap
  (`POST /api/restore` code path, 1 Bedrock call). Opus proposed fills; the hosted Strands Decider
  (`strands-decider-2b-hobson-v19`, `noul` on the top 3) scored the best, குப், at 0.37. That is under 0.5, so the
  Decider **abstains** and the hero shows "?".
- **Words, phrase and meaning** (`Interpreter.interpret`, `src/ezhuthu/agent/interpreter.py`; Sonnet 4.6, then Opus
  4.6 because Sonnet's own probability was under 0.6; Sonnet's answer was the more confident and was kept; 2 calls):
  11 words, each naming the letters it is made of; 3 at 0.5 or more (ர்குடிக்கு 0.55, குளம் 0.75, கொடும் 0.65), 2 of
  them attested in the DHARMA train split. Phrase: "…ர்குடிக்கு குளம் … கொடும் …". Meaning (the model's probability
  0.30): a fragment of a donative record, a tank given for a settlement; the rest too fragmentary to read. The prompt
  was grounded with words from published editions found in the letter stream (குடிக்கு, குளம், கொடும்) and the
  ontology.
- **No published edition of this stone was found** (it is not in the DHARMA split, and two Commons searches for an
  openly licensed photo of a DHARMA inscription found none that could be matched), so the hero shows no match rate and
  credits the meaning as "Meaning by Ezhuthu". It does not call itself experimental and it makes no claim that the
  letters or the meaning are right: it shows the numbers.
- The app's own line-by-line reading of the same crop (Sonnet 4.6, then Opus 4.6; confidence 0.20) and the Restorer
  on its gaps are kept in the record (`line_reading`) but are not shown.

Media: `design/brand/banners/hero-stone.webm` (1440 x 900 desktop, light), `hero-stone-dark.webm`,
`hero-stone-phone.webm` (375 x 740, Tamil), `hero-stone.gif` (light, small, for places without video) and
`hero-stone-poster.png` (the reduced-motion frame). `design/hero/contact-sheet.png` shows one frame per second of a
cycle for review.

## Proposed README copy (for the lead; README.md is owned by PR #31)

Replace the bold one-liner and the Tamil line under the badges with:

> **Learn to read the stone. Help read the backlog.** Ezhuthu is an apprenticeship tool for Tamil epigraphy: it trains
> students and new epigraphists to read real, damaged inscriptions, and gives working scholars a restoration assistant
> that shows its confidence, abstains when unsure, and routes doubts to expert review.
> <span lang="ta">கல்வெட்டைப் படிக்கக் கற்றுக்கொள்ளுங்கள்; காத்திருக்கும் கல்வெட்டுகளைப் படிக்க உதவுங்கள்.</span>

Under it, the hero media:

> <p align="center"><a href="design/brand/banners/hero-stone.webm"><img src="design/brand/banners/hero-stone-poster.png" alt="A real Chola-period inscription from Thanjavur: each carved letter is matched to a modern Tamil letter with a confidence, the least certain one goes to the Restorer and the Strands Decider, which leaves it open; the letters assemble into words, a phrase in today's Tamil and its meaning" width="88%"></a></p>
> <p align="center"><sub>A real photo (Richard Mortel, CC BY 2.0), read letter by letter by Ezhuthu: 46 letters, mean
> confidence 0.65, one left open by the Strands Decider; then words, a phrase in today's Tamil and its meaning.</sub></p>

"Why it matters", first two bullets:

> - **Too few readers.** In 2021 India had about 23 epigraphists; of nearly 1 lakh (100,000) inscriptions found since
>   1886, only 30,000 to 35,000 had been deciphered and published ([The Federal, 3 Aug 2021](https://thefederal.com/news/inscriptions-languish-as-the-number-of-epigraphists-dwindles)).
>   Training a new epigraphist is slow and depends on a mentor.
> - **Practice for students, an assistant for scholars.** Students of Tamil, history and epigraphy, heritage guides and
>   new epigraphists practise on real damaged stones with feedback in Tamil first. Working scholars get a restoration
>   assistant that shows its confidence and sends what it cannot settle to an expert review queue.

Numbers table (PR #31 added the test-eval rows; keep them), rows to add:

> | Photo reading, Tamil script / Tamil-Brahmi | CER **0.10** synthetic, 0.09 printed pages / **0.83 to 0.91 (fails)** | [eval/reports/2026-11-02-ocr-eval.md](eval/reports/2026-11-02-ocr-eval.md) |
> | Expert study B (reading with vs without the assistant) | **TBD** | [docs/expert-validation/](docs/expert-validation/) |

Elsewhere: "Learn" becomes "Practice", "Test" becomes "Benchmark", "Review" becomes "Expert review"; "five levels ...
Tamil-Brahmi" becomes "... Tamil-Brahmi letters (L5, from transliterated text)".

## Proposed CHARTER copy (for the lead; docs/CHARTER.md is owned by PR #31)

First paragraph:

> **Ezhuthu (எழுத்து, "letter/script")**: an apprenticeship tool for Tamil epigraphy. It trains students and new
> epigraphists to read real, damaged inscriptions, in Tamil first, and gives working scholars a restoration assistant
> that shows its confidence, abstains when unsure and routes doubts to expert review. It is built with Strands Agents,
> uses Strands Decider for calibrated decisions, and is deployed on Amazon Bedrock AgentCore.

In "Underserved learners", replace "India has about 23 working epigraphists for a backlog of about 70,000 unread
inscriptions (The Federal, 2021)" with:

> In 2021 India had about 23 epigraphists; of nearly 1 lakh inscriptions found since 1886, only 30,000 to 35,000 had
> been deciphered and published (The Federal, 3 Aug 2021). Training new readers is the bottleneck.

Add to "Measurable improvement": "and an expert with/without-assistant reading study (Study B, kit in
`docs/expert-validation/`)."

## Not done here (follow-ups)

- Native-speaker check of the Tamil tagline and of the new Tamil strings (`home.*`, `about.who*`, `about.limit*`,
  `stoneHero.*`).
- Re-letter the README banners, social preview and OG image (`design/brand/banners/readme-hero-*`,
  `social-preview-*`, `og-image.svg`) with the new tagline.
- Re-shoot `app/web/screenshots/` (`npm run screenshots`) after the README update; before/after shots of this change
  are in `docs/media/positioning-c/`.
