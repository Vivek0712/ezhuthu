# LinkedIn: carousel (10 slides, PDF document post)

Same arc as the long post. One idea per slide: a headline (max ~8 words) and a body (max ~25 words). Brand: ink
#1D1611, terracotta #9B3D22, ochre #D2891C; Fraunces headlines, Instrument Sans body, Noto Serif Tamil for Tamil.
Visual paths are repo-relative (FACTS section 8). Fact IDs are for the reviewer, not the slide.

| # | Headline | Body | Visual | Facts |
| --- | --- | --- | --- | --- |
| 1 | Over 1,000 years on the wall. | The great temple at Thanjavur, a UNESCO World Heritage Site. Its walls are written in Tamil. | Hero photo, `app/web/public/hero/thanjavur-1568.jpg`; small credit "Richard Mortel, CC BY 2.0" | E5 |
| 2 | Time wears the letters away. | 65% of the 1,320 inscriptions we studied carry a gap or an editor's restoration. | `design/hero/boxes-overlay.jpg`, one letter box dimmed | P6, P7 |
| 3 | Who will read the stones? | In 2021, India had about 23 epigraphists. Of nearly 1 lakh inscriptions found since 1886, 30,000 to 35,000 had been deciphered and published. | Big "23" in terracotta; source line "The Federal, 3 Aug 2021" | P1, E7 |
| 4 | Meet Ezhuthu. எழுத்து, "letter". | An apprentice for Tamil epigraphy. Practice. Restore. Read. Interpret. Tutor. Tamil first. | Logo lockup, `design/brand/logo/` | R1, S16 |
| 5 | Learn on real stones. | 1,469 practice drills, five levels: modern Tamil, Chola Tamil, Pallava (Grantha), Vatteluttu, Tamil-Brahmi letters. | Evolution strip, `design/renders/glyphs/evolution-strip-light.png` | S2, P4, L9 |
| 6 | Six agents, on AWS. | A Strands Graph and Swarm, a 1,958-entity Tamil ontology over MCP, Claude on Amazon Bedrock, running on Amazon Bedrock AgentCore. | Redrawn pipeline: Restorer -> Lesson Builder -> Tutor ⇄ Assessor; Reader, Interpreter; ontology MCP | T1, T2, T4, T15 |
| 7 | A decision model, fine-tuned for Tamil. | A 2B Strands decision model taught to pick the editors' fill. Train split only, pre-registered. 74 minutes on one A100: USD 2.26. Tested, not yet live. | Training card: "2B · LoRA · 74 min · USD 2.26" | D1, D2, D5, D7 |
| 8 | When it commits, 9 in 10 match. | On 413 held-out test gaps: 62.7% match the editors' restoration. Of the fills it commits to, 90.8% match (187 of 206). | Two big numbers; reliability chart from `app/web/src/benchmark/summary.json` | A1, A7 |
| 9 | Doubt becomes the lesson. | When it is unsure, it abstains, tells the learner experts are unsure here too, and sends the gap to an epigraphist's review queue. | Restore screen showing "?" (`app/web/screenshots/` restore shot) | S5, S9, S12, H4 |
| 10 | Learn to read the stone. Help read the backlog. | Built with Strands Agents, on Amazon Bedrock AgentCore. Try it: d3jz2k92ne5puo.cloudfront.net · Code: github.com/Vivek0712/ezhuthu | Wordmark + credits strip: "Inscriptions: DHARMA (ERC 809994), CC BY-SA 4.0 · Photo: Richard Mortel, CC BY 2.0" | FACTS "Credits" |

## Post text to go with the carousel

> Over 1,000 years on the wall at Thanjavur, and in 2021 about 23 epigraphists in India to read stones like these. I built Ezhuthu, an apprentice for Tamil epigraphy, with Strands Agents on Amazon Bedrock AgentCore. 10 slides: the problem, the agents, the fine-tuned decision model, and what it scores on held-out inscriptions.
>
> #StrandsAgents #AmazonBedrock #Tamil #Epigraphy #AIforGood

## Checks before posting

- Slide 1: if unsure of the UNESCO wording, drop "a UNESCO World Heritage Site" (E5 is a *secondary* check). Never
  "1,100 years" for Thanjavur.
- Slide 5: "Tamil-Brahmi letters", never "Tamil-Brahmi inscriptions" (L9: no Tamil-Brahmi editions in the corpus).
- Slide 7: keep "Tested, not yet live" on the slide itself (L4).
- Slide 8: "match the editors' restoration", never "correct". Keep 90.8% (do not round to 91%).
