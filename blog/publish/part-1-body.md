< COVER IMAGE: upload blog/img/p1-00-cover.png in the cover field (1200x675, no text) >

By Vivek Raja, AWS AI Hero

The great temple at Thanjavur has stood for over 1,000 years, its walls written in Tamil. Rajaraja I Chola completed it in 1010 CE, and it is a UNESCO World Heritage Site. In 2021, India had about 23 epigraphists to read stones like these.

That second number comes from a report in The Federal (3 August 2021): of nearly 1 lakh (100,000) inscriptions found in India since 1886, only 30,000 to 35,000 had been deciphered and published, and the country had about 23 epigraphists left to do the work. Training a new one is slow and depends on a mentor. Most learners cannot read the inscriptions on their own village temple.

So I built Ezhuthu. The name is the Tamil word for "letter". It is an apprenticeship tool for Tamil epigraphy: it teaches students, temple visitors and new epigraphists to read real, damaged inscriptions, Tamil first, and it gives scholars an assistant that proposes the worn-away letters, shows how sure it is, and hands its doubts to an expert.

< FIGURE 1 of 9: upload blog/img/p1-01-at-a-glance.png here >
Alt text: Ezhuthu at a glance: 1,320 DHARMA inscriptions parsed, 1,469 Tamil-first practice items, 62.7 percent of 413 held-out test gaps matching the editors' restoration, and 90.8 percent of the fills it commits to matching

*Ezhuthu at a glance. Every number traces to an evaluation report in the repository.*

It is built with Strands Agents, runs on Amazon Bedrock AgentCore, and uses Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock. On 413 held-out test gaps, scored once, the configuration it ran before its current decision model matches the editors' restoration on 259 of them (62.7%). When it commits to a fill, 9 in 10 match: 187 of 206. The live app now ranks its candidate fills with a Strands decision model I fine-tuned for Tamil; that configuration has not been scored on the test set yet, and part 3 gives the numbers for the model itself.

This is part 1 of a three-part series about the problem, the place and the product, with a walkthrough of the live site. Part 2 opens the agent pipeline on AWS. Part 3 covers the Strands decision models I fine-tuned for Tamil and the evaluation work behind every number here.

The site is live at https://ezhuthu.sparrowdecider.com and the code is public at https://github.com/Vivek0712/ezhuthu.

## From Madurai to Thanjavur, the walls are written

Tamil Nadu's State Department of Archaeology says its epigraphy wing has copied about 24,771 inscriptions as estampages, ink impressions taken from the stone, and that these "are deciphered, edited and published" by the department. In November 2022 the state's archaeology minister said that of 74,000 estampages held by the Archaeological Survey of India in Mysuru, about 26,000 are in Tamil.

Most of that writing sits on temples. Ezhuthu works from 1,320 editions published by the DHARMA project, and 534 of them name a temple in their title. By dynasty, 480 editions are Pallava, 312 Chola, 115 Pandya and 21 Vijayanagara. The ontology built from these editions holds 139 temples, 8 taxes and 14 formulas.

Madurai, the temple city on the Vaigai, is carved into the stones as well. 25 of the editions contain matirai, Madurai in the inscriptions' own spelling. 23 of those carry it inside a royal title, matirai konta, "who took Madurai", used by the Chola king Parantaka I. One edition comes from the Minakshi temple in Madurai itself, from the time of Maravarman Sundara Pandya.

< FIGURE 2 of 9: upload blog/img/p1-09-tamil-nadu-stones.png here >
Alt text: The stones behind Ezhuthu: 1,320 DHARMA editions, 534 naming a temple in their title, dynasties by count from Pallava 480 and Chola 312 to Pandya 115 and Vijayanagara 21, and Madurai named in 25 editions, 23 of them in the Chola title who took Madurai

*Kings, temples and Madurai, counted from the corpus itself. Counts are of DHARMA editions, which are not the same as stones.*

## Damage is the normal case

Stone weathers. In 858 of the 1,320 inscriptions (65%), the editors had to mark a gap or supply a restoration. A reading tutor that only works on clean text would fail on most of the corpus, so damage sits at the centre of the design.

In the Tamil lines the DHARMA editors supplied 3,289 expert restorations, spans where the stone is broken and an editor filled in the missing letters from their knowledge of the language, the formulas and the period. Those restorations are what Ezhuthu learns from and is scored against. 410 of them are in Pallava inscriptions over 1,100 years old. Another 3,557 gaps have a known size and no expert fill at all.

< FIGURE 3 of 9: upload blog/img/p1-03-gap-lengths.png here >
Alt text: Benchmark gap lengths: 1,833 one-letter gaps and 583 two-letter gaps, falling to 23 gaps of 21 or more letters

*Most gaps are a single letter. The long ones are the hard ones.*

The script changes under your feet. Ezhuthu teaches five levels: modern Tamil, Chola Tamil, Pallava Grantha, Vatteluttu and Tamil-Brahmi, and its letter model tracks 8 script stages across them. Vatteluttu has no Unicode encoding, so I drew 7 teaching glyphs for it (a, e, ka, lla, ma, pa, ta). They are teaching shapes pending an epigrapher's review.

< FIGURE 4 of 9: upload blog/img/p1-02-letter-evolution.png here >
Alt text: The letter ka traced across five eras of Tamil writing, from modern Tamil back through Chola Tamil, Pallava Grantha and Vatteluttu to Tamil-Brahmi

*One letter, five eras. Tamil script appears only inside the figures; the text uses transliteration.*

## The apprentice idea

An epigraphist learns by reading damaged stones beside someone who already can. Ezhuthu tries to give more people a seat at that bench. Its tagline is "Learn to read the stone. Help read the backlog."

It does five things. Practice turns real inscriptions into drills. Restore proposes the worn-away letters, or abstains. Reader turns a photo or an EpiDoc file into a transcription. Interpreter turns letters into words, a phrase in today's Tamil and a plain meaning. Tutor gives hints and history, in Tamil first with English optional.

The design rule I care about most is that the assistant shows its doubt. When the assistant is unsure about a gap it says so, and the learner is told that experts are unsure here too. That moment becomes the lesson, and the gap goes to an expert's review queue.

## A walkthrough of the live site

### Home: a real stone, read letter by letter

The home page opens on a real Chola-period stone from Thanjavur, photographed by Richard Mortel (CC BY 2.0). In a recorded run, the Reader names 46 carved letters with Claude Opus 4.6 in 4 calls, each with the model's own probability (mean 0.65, self-reported and uncalibrated). The least certain letter, at 0.45, goes to the Restorer. Claude Opus 4.6 proposes fills, and the best one scores 0.08 after calibration, under the 0.49 needed, so the letter stays open.

The Interpreter then groups the letters into 11 words, 3 of them at 0.5 or more, and offers a phrase in today's Tamil and a meaning at confidence 0.30. This stone has no published edition, so the meaning is credited "Meaning by Ezhuthu" and nobody should treat it as a reading.

< FIGURE 5 of 9: upload blog/img/p1-04-home-hero.png here >
Alt text: The home hero in four frames: the Thanjavur stone with each carved letter boxed, the least certain letter sent to the Restorer, whose best fill scores 0.08 after calibration, under the 0.49 needed, so it stays open, then words, a phrase in today's Tamil and a plain meaning

*Four steps in one animation, every probability on screen.*

### Practice: real inscriptions turned into drills

Practice has 1,469 items built from the train split of the corpus: 205 letter drills, 540 word drills, 394 gap drills and 330 formula drills, each at 3 difficulty levels, across the five script levels. Feedback comes in Tamil first.

< FIGURE 6 of 9: upload blog/img/p1-05-practice-banks.png here >
Alt text: Practice bank sizes: letters 205, words 540, gaps 394 and formulas 330, split by difficulty level

*1,469 drills, all from real stones.*

< FIGURE 7 of 9: upload blog/img/p1-06-practice-screens.png here >
Alt text: The Practice page in Tamil on desktop and mobile, with a letter drill and its hint panel

*Practice on desktop and on a phone.*

### Restore: propose, show the confidence, or abstain

Restore is the scholar's bench. You paste a passage with a gap, or pick one of 13 real DHARMA passages from the gallery: 10 masked validation passages where the editors' reading is known, and 3 genuine lacunae nobody has restored.

In my recorded gallery run it filled 4 of the 10 masked gaps, and all 4 match the editors' restoration. It left the other 6 open, and the edition's reading was among its 5 candidates on 9 of 10. Ten gaps are far too few to estimate a rate, so the real rates are below and in part 3. On the unsolved lacunae it abstained on all 4 of the gaps it was asked about, with top confidence between 0.107 and 0.150, and offered its options to an expert.

< FIGURE 8 of 9: upload blog/img/p1-07-restore.png here >
Alt text: The Restore page: a passage with a masked gap, five ranked candidate fills with calibrated confidence, the parallel passages behind them, and the published edition's reading with a match badge

*Candidates, the parallels behind them, and the decision: fill or abstain.*

### Read and Interpret: from a photo to a meaning

The Reader does photo reading of Tamil script, shown with its confidence for you to check against the edition. It uses Claude Sonnet 4.6 vision and escalates to Claude Opus 4.6. On 72 synthetic Tamil-script plates made from held-out DHARMA lines, its character error rate is 0.097 (0.047 on clean plates), and on 3 real printed Tamil pages it is 0.093. The older scripts are taught in Practice. The Interpreter turns the letters into words, a phrase in today's Tamil and a plain meaning.

### Expert review, How it works and Benchmark

Every abstention can land in the expert review queue, a route open only to the Cognito group "experts". How it works is an animated overview of the agents, which part 2 covers in depth. Benchmark publishes the headline numbers, the leaderboard and the reliability chart, each linked to the report it comes from.

< FIGURE 9 of 9: upload blog/img/p1-08-benchmark-page.png here >
Alt text: The top of the live Benchmark page: 0.6271 of first proposals match the editors' restoration on 259 of 413 test gaps, 90.8 percent of the fills it chooses to make match, and 0.1961 on gaps of four or more letters

*The Benchmark page shows the weak spot next to the strong ones.*

## Who it helps

Students of Tamil, history and epigraphy, along with heritage guides, get guided practice on real stones across five levels, with feedback in Tamil first.

Temple visitors and heritage volunteers can point a phone at Tamil text and get letters, words and a meaning to check against the edition. The site is a mobile-first web app in Tamil and English.

New epigraphists get to practise on damaged texts beside an assistant that shows its doubts, so the slow, mentor-bound part of their training goes further.

Working scholars get an assistant that fills the gaps it is sure of and sends the rest to the review queue, where a person makes the call.

The next step is local. I plan a learner pilot with student volunteers from the AWS User Group Madurai, and none of the learner gains are measured yet.

## The results, with their qualifiers

All numbers below are on 413 held-out test gaps from 131 inscriptions the system was never tuned on. Every choice was made on the validation split by a rule committed in advance, and the test set was scored once. They are for the pre-rank configuration the live app ran before it switched to the fine-tuned Strands decision model (part 3). "Match" means the fill equals the DHARMA editor's restoration after normalisation.

| What | On held-out test |
|---|---|
| First proposal matches the editors' restoration | 259 of 413, 0.6271 (95% CI 0.5787 to 0.6731) |
| Share of gaps it chooses to fill | 49.9% (206 gaps) |
| Its fills that match the editors' restoration | 90.8% (187 of 206) |
| Gaps it scores 0.9 to 1.0 | 95 gaps, 97.9% match |
| One-letter gaps (n = 281) | 73.6% match |
| Two- and three-letter gaps (n = 81) | 51.8% match |
| Gaps of four or more letters (n = 51) | 19.6% match |
| Latency per gap | 3.2 s at p50, 5.5 s at p90, 0 gaps over 27 s |
| Model cost per gap | about $0.0060, an estimate at list prices |

It also beats the two classic methods on the same gaps. Copying from the closest parallel inscription, the epigrapher's traditional move, matches 47.2%. A character 5-gram language model trained on the same corpus matches 56.6%. Ezhuthu's 62.7% is ahead of both, with p = 0.0002 against the 5-gram and p < 0.0001 against copying (exact McNemar).

## Honest limits

Long gaps are still hard: on gaps of four or more letters it matches 19.6%, the same as copying a parallel. It abstains on about half of the test gaps, by design. A match with the editors' restoration is agreement with expert judgement, which is no proof of the original text. Photo reading of Tamil-Brahmi fails today, and no real stone photo has been scored against an edition yet. The learner pilot and the expert study come next.

## Next in this series

Part 2 is the build: a Strands Graph with a Swarm inside it, six specialist agents, a custom Tamil-epigraphy ontology served over MCP, routing between Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock, calibrated confidence, and a 25-second request budget on Amazon Bedrock AgentCore Runtime. Part 3 is the Strands decision model I fine-tuned for Tamil, tested on held-out inscriptions, public on Hugging Face and now ranking restorations in the live app, and the evaluation discipline behind every number in this post.

Try it at https://ezhuthu.sparrowdecider.com. The end-to-end Jupyter notebook, from the data to the live AgentCore API and the test evaluation, is at https://github.com/Vivek0712/ezhuthu/blob/main/notebooks/ezhuthu_end_to_end.ipynb.

## Credits

Inscription texts: the DHARMA project (ERC grant 809994) and the named editors of each edition, CC BY-SA 4.0. The derived benchmark is shared under CC BY-SA 4.0.

Cover and figure 5 photograph: "Brihadishwara Temple, Dedicated to Shiva, built by Rajaraja I, completed in 1010, Thanjavur (38)" by Richard Mortel, CC BY 2.0 (https://creativecommons.org/licenses/by/2.0/), via Wikimedia Commons (https://commons.wikimedia.org/wiki/File:1010_CE_Brihadishwara_Shiva_Temple,_inscription,_built_by_Rajaraja_I,_Thanjavur_Tamil_Nadu_India.jpg); cropped, letter boxes and labels added.

Context sources: The Federal, 3 August 2021 (epigraphist numbers); Tamil Nadu State Department of Archaeology, https://tnarch.gov.in/epigraphy (estampages); DT Next, 16 November 2022 (ASI Mysuru estampages); UNESCO World Heritage List, Great Living Chola Temples.

Fonts: Noto Serif Tamil, Noto Sans Tamil, Noto Sans Brahmi, Noto Sans Grantha, Fraunces and Instrument Sans, SIL OFL 1.1.

Built with Strands Agents and Strands Decider; runs on Amazon Bedrock AgentCore; models Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock.
