# Ezhuthu messaging brief (user direction, 2026-11-03)

## The crux (every piece must land this)
Agentic AI built with Strands Agents, Strands decision models and a custom Tamil-inscription ontology reads
inscriptions over 1,100 years old, fills the worn-away letters and words, restores the text, and beats the
existing methods. It needs a WOW factor.

## FOCUS (user, 2026-11-03): the overall problem, solution, implementation/pipelines and how it helps people.
Do NOT build the story on model-vs-model comparisons (no "Claude vs decider" framing). Show the fine-tuned Strands decision
models and the effort behind them as part of the pipeline story. Ground it in place: Madurai, Tamil Nadu, Tamil language,
temples and their inscriptions, archaeologists and epigraphists at work.

## Supporting numbers if a comparison is needed: "beats existing methods" (NOT humans: no human study exists)
Existing methods we beat, on 413 held-out test gaps, scored against the editors' restorations:
- A frontier LLM alone (Claude Sonnet 4.6): 41.7% -> Ezhuthu 62.7% (+21 points, 51% relative)
- Classic statistical language model (character 5-gram): 56.7%
- The epigrapher's classic move, copying from parallel inscriptions: 47.2%
- Hosted general-purpose Strands Decider (v19) as the chooser: 43.1% -> our Tamil fine-tuned 2B decider 54.7% (+11.6 points, p < 1e-7)
Precision when it commits: 91% (187/206) of fills match the editors' restoration; it fills ~half and flags the rest.
No "state of the art", "first", or "beats humans".

## Wording guard rails (wow, but defensible)
- "reads ... accurately": tie accuracy to the restoration numbers (91% when it commits; 63% overall). Do not claim photo OCR accuracy on real weathered stones (not measured) or any Tamil-Brahmi ability.
- "1,100+ years old" = the Pallava collection (410 restorations). The Thanjavur temple in the hero was completed 1010 CE ("over 1,000 years").
- "Strands decision models": the hosted Strands Decider drives the tutor's teaching decisions; the Tamil fine-tuned Strands Decider beats the hosted one on held-out test, and since 2026-11-04 the live app ranks restorations with it. Never give the live (routed + fine-tuned) configuration a TEST number: the 62.7% is the configuration scored on TEST before the switch.
- Ontology: custom, 1,958 entities (kings, places, titles, temples, grants), 27 classes, served to the agents over MCP. Do not claim it improves accuracy (ablation showed no measurable effect).
- Never: "experimental", "Strands AI", "AWS AI", "correct" for restorations (say "match the editors' restoration"), the banned company name.
- Every number must trace to media/FACTS.md / eval/reports.

## Variant testing (find the tone and voice)
Write many variants per format (headline, hook line, LinkedIn post, blog title, video opening line) across voices:
1. Bold founder ("I built ...") 2. Awe and heritage (the stones, the kings, 1,000 years) 3. Hard-technical (agents, calibration, p-values)
4. Social-good mission (few experts, vanishing letters, learners) 5. Punchy one-liner / meme-able.
Score each with a panel of distinct reader personas: AWS/Strands developer on LinkedIn, hackathon judge (Education track),
Tamil heritage enthusiast, skeptical ML researcher who checks numbers, an epigraphist. Criteria: wow / stop-scroll power,
clarity in 5 seconds, credibility (would the skeptic and the epigraphist sign off?), emotional pull, shareability.
Pick winners per format, iterate the top 3 once, and record the chosen voice in media/VOICE.md for video, blogs and LinkedIn.
