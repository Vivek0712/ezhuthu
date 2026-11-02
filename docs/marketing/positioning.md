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

The home page now opens on a **real photograph** of a Chola-period inscription on the Brihadisvara temple, Thanjavur
(Richard Mortel, CC BY 2.0, via Wikimedia Commons; `app/web/public/hero/ATTRIBUTION.md`). The animation shows the
letters lighting up on hand-annotated boxes, flying into Reader, Restorer and Strands Decider, and landing as the
reading, and everything it shows is the **actual output** of our Reader and Restorer on that photo
(`app/web/src/hero/hero-reading.json`, built by `scripts/hero_read.py` and `scripts/hero_build.py`; 10 live Bedrock
calls, models from `config/models.yaml`):

- Reader confidence **0.20** (Sonnet 4.6 at 0.15, then Opus 4.6 on "read again"); all 4 lines are under 0.5.
- 3 gaps; Opus proposed fills and the hosted Strands Decider (`strands-decider-2b-hobson-v19`, `noul` on the top 3,
  the current `restorer.strategy_llm`) scored the best ones 0.38, 0.48 and 0.44. The cloud runtime has no calibration
  for that decider, so it fills only at 0.5 or above: **all three abstain** and the reading goes to expert review.
- **We could not identify this stone in a published edition**, so the hero shows no error rate and no translation, and
  says so. Two Opus reads of overlapping crops of the photo disagreed, which is itself evidence that the reading is
  unreliable.

That is positioning C in one screen: a real stone, an assistant that shows how unsure it is, and a route to an expert.
A follow-up worth doing: an epigraphist identifies the inscription (SII volume 2 is the likely place), and we add its
edition and a CER, or swap to a photo of a DHARMA train inscription with a published reading.

Media: `design/brand/banners/hero-stone.webm` (desktop, light), `hero-stone-dark.webm`, `hero-stone-phone.webm`
(375 px, Tamil), `hero-stone.gif`, and `hero-stone-poster.png` (the reduced-motion frame).

## Proposed README copy (for the lead; README.md is owned by PR #31)

Replace the bold one-liner and the Tamil line under the badges with:

> **Learn to read the stone. Help read the backlog.** Ezhuthu is an apprenticeship tool for Tamil epigraphy: it trains
> students and new epigraphists to read real, damaged inscriptions, and gives working scholars a restoration assistant
> that shows its confidence, abstains when unsure, and routes doubts to expert review.
> <span lang="ta">கல்வெட்டைப் படிக்கக் கற்றுக்கொள்ளுங்கள்; காத்திருக்கும் கல்வெட்டுகளைப் படிக்க உதவுங்கள்.</span>

Under it, the hero media:

> <p align="center"><a href="design/brand/banners/hero-stone.webm"><img src="design/brand/banners/hero-stone.gif" alt="A real Chola-period inscription from Thanjavur: letters light up, fly through Reader, Restorer and Strands Decider, and land as Ezhuthu's reading, with low confidence, three abstained gaps and a note that it goes to expert review" width="88%"></a></p>
> <p align="center"><sub>A real photo (Richard Mortel, CC BY 2.0), read by Ezhuthu: confidence 0.20, three gaps left
> open, sent to expert review. No published edition of this stone was found, so no error rate is shown.</sub></p>

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
