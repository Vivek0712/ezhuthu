# Ezhuthu launch film: storyboard and script (v2)

**Runtime 180.0 s exactly · 1920x1080 · 30 fps (5,400 frames) · English narration (Amazon Polly, heisenberg, us-east-1) · rebuilt 2026-11-03 to `media/MESSAGING_BRIEF.md`**

Machine-readable twin: [`storyboard.json`](storyboard.json). Fields per scene: `id, act, start_s, end_s, duration_s, render, narration, narration_ssml, vo_in_s, vo_window_s, narration_words, words_per_min, vo_wpm, on_screen_text, visual, music_cue, fact_ids, credit_ids`. This page is generated from the JSON: edit the JSON first. Every number cites a row in [`../FACTS.md`](../FACTS.md); every external image or clip cites a row in [`CREDITS.md`](CREDITS.md) / [`stock.json`](stock.json).

## The film in one breath

Madurai's temple walls are written in Tamil, and the letters are fading; in 2021 India had about 23 epigraphists. So I built an apprentice. Ezhuthu reads a real Thanjavur stone letter by letter, turns real inscriptions into drills, fills worn-away letters when it is sure and leaves them open when it is not. Under the hood: six agents built with Strands Agents, a custom Tamil ontology over MCP, Claude on Amazon Bedrock, Strands decision models we fine-tuned for Tamil, all running on Amazon Bedrock AgentCore. It helps students, temple visitors and epigraphists, and on 413 held-out gaps it matches the editors' restoration 62.7% of the time; when it commits, 9 in 10. It knows when it does not know.

**Direction (user, 2026-11-03):** problem -> solution -> implementation -> impact. Documentary-meets-product-launch: warm, emotional, big but true. No model-vs-model framing (no Claude-vs-decider graphic; Claude appears only as a stage in the pipeline). The fine-tuned Strands decision models appear as part of the build, always badged *fine-tuned · tested · not yet live*.

## Structure

| Act | Window | Beat | Scenes |
| --- | --- | --- | --- |
| 1 Problem | 0.0-40.0 s | Madurai cold open + hook in 5 s; Madurai to Thanjavur; Madurai in the stones; letters wearing away (65%); about 23 epigraphists (2021); training is slow | a1-01-cold-open .. a1-06-slow |
| 2 Solution | 40.0-90.0 s | Ezhuthu, the apprentice; live hero reads the Thanjavur stone (letters, words, today's Tamil, meaning); Practice; Restore fills; Restore leaves open: doubt becomes the lesson | a2-07-title .. a2-11-restore-open |
| 3 Implementation | 90.0-145.0 s | Six Strands agents; Reader -> Restorer (parallels, 5-gram, Sonnet -> Opus) -> confidence check -> Interpreter -> Tutor (Graph + Swarm); ontology over MCP; fine-tuned Strands decision models and the effort; AgentCore cloud path | a3-12-under-the-hood .. a3-18-agentcore |
| 4 Impact | 145.0-172.0 s | Students, temple visitors and volunteers, epigraphists' review queue; 62.7% of 413 held-out gaps; 9 in 10 when it commits; it knows when it does not know | a4-19-who .. a4-21-knows |
| Close | 172.0-180.0 s | Lockup, tagline, built with Strands Agents, live URL + GitHub, fast credits crawl | c-22-close .. c-22-close |

Narration: **335 words over 180 s** (about 112 wpm average). Every scene's spoken window (`vo_in_s` to 0.25 s before the cut) is at or under 152 wpm, most 130-145; number-heavy lines sit lower because Polly reads numbers long.

## Voice, music, visual system

- **Voice**: Amazon Polly neural, Indian English (suggest `Kajal`, en-IN; audition `Kajal` and one en-GB voice), `prosody rate 95%`. Pronunciation: *Ezhuthu* as "Ezh-oo-thoo" (`<sub alias>` in `narration_ssml`); *lakh* as "lahk"; *Thanjavur* "Than-jah-voor"; *Madurai* "Mah-thoo-rye". Check each against a Tamil speaker before the final mix.
- **Music**: original score only (no third-party or copyrighted music). Cues M1 'stone' (drone), M2 'memory' (sparse plucked strings), M3 'apprentice' (main theme), M4 'pipeline' (rhythmic build, mridangam-like percussion), M5 'people' (theme returns, full), M6 'resolve'. SFX (chisel taps, stone settling, chimes) generated or CC0; list any CC0 SFX in CREDITS.md.
- **Palette** (`design/tokens/tokens.css`): granite-950 `#13100D` / granite-900 background; stone-50 to stone-300 text; laterite-600 `#9B3D22` / laterite-400; lamp-500 `#D2891C` / lamp-300 `#F5C468` focus; neelam-300 `#AEB8EC` for 'unsure / left open'; neem-300 `#93D09C` for 'matches the editors' restoration'; kumkum only for damage.
- **Type**: Fraunces (display, numbers, tabular-nums), Instrument Sans (labels, captions, credits), Noto Serif/Sans Tamil, JetBrains Mono (tool names, URLs).
- **Footage**: only licensed stock from `stock.json` (Wikimedia Commons, CC0/CC BY/CC BY-SA/PD), repo assets and live-site captures in `ezhuthu-video/footage/`. No BBC or other all-rights-reserved media. Ken Burns rects are `[x, y, w, h]` normalised to the source image (16:9 output). Grade: warm, lifted blacks, consistent across stock. Captions must match each asset's real place (p32 is Arachalur, Erode district; p26 is Chennai; p35 is Kanchipuram district).
- **Logo rule** (`BRAND.md` section 4): mark and wordmarks only FADE. No scale-bounce, rotate, outline or morph. No AWS or third-party logos anywhere; services are named in text.
- **Render split** (`render` field): `html` = animated scene page `scenes/<id>.html` rendered by `render.mjs`; `comp` = stock / capture edit done in the compositor (ffmpeg or NLE); `comp+html` = stock base plate + an HTML overlay layer (render the overlay with alpha, or composite in the page). Existing v1 pages reusable as overlay layers: `s02-scale.html` (23 count-up, tile grid) for a1-05, `s03-damage.html` (65% ring) for a1-04.

## Guard rails applied in this script

- "Over a thousand years" is said only over Thanjavur imagery (a1-02, p14). "Over 1,100 years old" appears only as on-screen text over the Pallava Shore Temple (a1-04) and only for the 410 Pallava restorations (P10).
- The live home-hero capture (a2-08) must be cropped to the hero panel: the page eyebrow says "some carved over 1,100 years ago" and must not sit on the Thanjavur stone.
- Restorations always "match the editors' restoration"; the gallery-run numbers carry "in our recorded gallery run" and the small-n note (S11).
- Fine-tuned Strands decision models: "fine-tuned · tested on held-out TEST · not yet live" badge for the whole of a3-17; drawn as a dotted branch, not the live path (L4). The Tutor's policy is "built on Strands Decider, with rule guardrails" (S8, L13), never "a live decider drives the cloud tutor".
- Ontology: "the agents look up kings, temples and formulas" (T4); no accuracy claim (L5).
- Reader: "turns a photo into letters" for Tamil script; no stone-photo accuracy number and no Tamil-Brahmi reading claim (L6). The a4-19 phone overlay is a graphic, not a measured capture.
- Numbers are never rounded up: 90.8% or "nine in ten" (A7), 62.7% (A1). Classic-method numbers (47.2%, 56.7%) appear only as a quiet on-screen footnote in a4-20; no model names in the impact act.
- Madurai: "25 editions name it" (P13) with the Chola-title qualifier on screen; the benchmark is "Tamil Nadu's temples", never "Madurai's inscriptions" (L12).
- Banned words checked by script on every narration and on-screen line: experimental, the banned company name, Strands AI, AWS AI, correct, state of the art, first (as a claim), beats humans, Tamil-Brahmi, FalkorDB/COA, live/deployed (except 'not yet live' and the live-site URL label), 91%, 63%.

## Scene by scene

### a1-01-cold-open · 0.0-5.0 s (5.0 s) · Act 1-problem · render: `comp`

**Narration** (11 words; VO in at 0.25 s, 147 wpm in its window)

> These temple walls are written in Tamil. The letters are fading.

**On screen**

- Madurai, Tamil Nadu

**Visual**: Cold open from black. 0.0-2.4 s: p01 (Meenakshi south gopuram) Ken Burns tilt-up, rect [0.20,0.55,0.60,0.39] -> [0.20,0.05,0.60,0.39], ease-in-out, warm grade (+8 temp, lifted blacks), 0.4 s fade from black. Location tag 'Madurai, Tamil Nadu' bottom-left, Instrument Sans 22 px stone-100, fades in at 0.6 s. 2.4 s hard cut on a chisel tap to p17 (weathered Tamil inscription, Agneeshwaran temple wall, Madurai district) macro push-in rect [0.18,0.30,0.50,0.28] -> [0.24,0.34,0.40,0.225]; a raking lamp-400 light sweep crosses the worn band left to right (1.6 s); at 4.0 s three letters on the band dissolve to 40% opacity (mask erosion) to show 'fading'.

**Music**: M1 'stone' starts at 0.0: low original drone (tanpura-like, C#), room tone, one chisel-tap SFX at 2.4 s (CC0 or recorded).

**Facts**: E6, P7 · **Credits**: p01, p17

### a1-02-place · 5.0-14.0 s (9.0 s) · Act 1-problem · render: `comp`

**Narration** (19 words; VO in at 5.3 s, 135 wpm in its window)

> From Madurai to Thanjavur, kings carved their words in stone. Thanjavur's great temple has stood over a thousand years.

**On screen**

- Madurai
- Thanjavur
- Brihadisvara temple, completed 1010 CE

**Visual**: 5.0-8.6 s: p04 (aerial, Meenakshi gopurams) slow push-in rect [0.10,0.12,0.80,0.735] -> [0.38,0.05,0.55,0.505] toward the right-hand gopuram; tag 'Madurai'. 8.6 s match-dissolve (0.5 s) to v05 (Thanjavur, devotees at Brihadisvara) source in 3.0 s -> out 6.6 s, 1:1 speed, slight 1.00->1.05 scale; tag 'Thanjavur'. 12.2 s cut to p14 (vimana at dusk) push-in [0.15,0.05,0.70,0.68] -> [0.27,0.03,0.46,0.45] while the narration says 'over a thousand years'; lower-third 'Brihadisvara temple, completed 1010 CE' (Fraunces 600 opsz 72, stone-50). The 'over a thousand years' line must sit on Thanjavur imagery only (VOICE flag 3).

**Music**: M1 continues; a soft rising pad enters at 8.6 s.

**Facts**: E5, E6, P12 · **Credits**: p04, v05, p14

### a1-03-madurai-in-stone · 14.0-20.0 s (6.0 s) · Act 1-problem · render: `html`

**Narration** (10 words; VO in at 14.3 s, 110 wpm in its window)

> Madurai itself is carved into them: twenty-five editions name it.

**On screen**

- மதுரை  Madurai (carved மதிரை, matirai)
- 25 editions name Madurai
- 23 of them in a Chola king's title: 'who took Madurai'

**Visual**: Base layer: p11 (long plinth band of Tamil inscriptions, Thanjavur) lateral pan rect [0.00,0.25,0.62,0.40] -> [0.38,0.25,0.62,0.40], 6 s linear, darkened to 55%. Kinetic type over it: the word 'மதிரை' (Noto Serif Tamil 160 px, lamp-300) is 'carved' in with a chisel-ease stroke reveal at 14.6 s, ISO 'matirai' under it (JetBrains Mono 28 px). 16.2 s: counter '25' counts up 0 -> 25 (1.0 s, Fraunces 600 tabular, 180 px) + 'editions name Madurai'. 18.0 s: sub-line '23 of them in a Chola king's title: "who took Madurai"' fades in, stone-300, 30 px. Micro-credit bottom-left: 'Texts: DHARMA, CC BY-SA 4.0'. Do not imply this photo shows a Madurai inscription.

**Music**: M1 -> M2 'memory' crossfade at 14.0: sparse plucked-string motif (original), 72 bpm, no percussion.

**Facts**: P13 · **Credits**: p11, c-dharma

### a1-04-damage · 20.0-29.0 s (9.0 s) · Act 1-problem · render: `comp+html`

**Narration** (14 words; VO in at 20.3 s, 99 wpm in its window)

> Time wears the letters away. 65% of the 1,320 inscriptions we studied are damaged.

**On screen**

- 1,320 inscriptions (DHARMA editions)
- 65% (858) carry a gap or an editor's restoration
- 3,289 expert restorations in Tamil lines
- 410 in Pallava inscriptions over 1,100 years old

**Visual**: 20.0-25.0 s: p17 again, tighter macro on the most eroded block, rect [0.30,0.40,0.30,0.17] -> [0.34,0.42,0.24,0.135]; thin kumkum-600 crack strokes draw across (stroke-dashoffset 0.8 s); bracketed gaps '[ ? ? ]' glow neelam-300 over two worn letters. Overlay (reuse the ring-chart layer from scenes/s03-damage.html): '1,320' types in at 21.2 s, ring sweeps to 65% (1.4 s) with '858' in the centre. 25.0 s dissolve (0.6 s) to p20b (Shore Temple at dusk, Mamallapuram, Pallava; replaces p20, a close group of faces) push-in [0.00,0.08,1.00,0.84] -> [0.22,0.06,0.62,0.62]; lines '3,289 expert restorations in Tamil lines' then '410 in Pallava inscriptions over 1,100 years old' (lower-third, 26.0 s and 27.2 s). The 1,100-year line appears ONLY over this Pallava image.

**Music**: M2 continues; a low cello-like swell (original) under the 65% ring.

**Facts**: P6, P7, P8, P10 · **Credits**: p17, p20b, c-dharma

### a1-05-few-readers · 29.0-36.0 s (7.0 s) · Act 1-problem · render: `comp+html`

**Narration** (12 words; VO in at 29.3 s, 112 wpm in its window)

> In 2021, India had about 23 epigraphists for nearly one lakh inscriptions.

**On screen**

- In 2021: about 23 epigraphists
- nearly 1 lakh (100,000) inscriptions found since 1886
- only 30,000 to 35,000 deciphered and published
- Source: The Federal, 3 Aug 2021

**Visual**: 29.0-32.4 s: p32 (team 3D-scanning a rock inscription in a cave, Arachalur, Erode district) push-in [0.05,0.10,0.90,0.83] -> [0.20,0.22,0.65,0.60]; caption 'Documenting an inscription, Arachalur, Tamil Nadu'. 32.4 s cut to p09 (inscribed wall, Brihadisvara, a man seated beside it) slow pull-out [0.30,0.25,0.55,0.51] -> [0.10,0.10,0.85,0.78]. Overlay: '23' count-up 0 -> 23 (1.2 s, Fraunces 600 220 px, laterite-400) at 30.6 s with 'epigraphists (about, 2021)'; 33.2 s the tile-grid from scenes/s02-scale.html (1,000 tiles = 1 lakh; 300-350 lit as the published range band) fades in over the darkened p09. Source line stone-400 18 px bottom-left the whole scene.

**Music**: M2 thins out to a single sustained note: the 'silence' beat before the turn.

**Facts**: P1, E7 · **Credits**: p32, p09

### a1-06-slow · 36.0-40.0 s (4.0 s) · Act 1-problem · render: `comp`

**Narration** (7 words; VO in at 36.3 s, 122 wpm in its window)

> And training a new reader is slow.

**On screen**

- அரிச்சுவடி  a palm-leaf alphabet primer

**Visual**: p26 (Tamil alphabet palm-leaf book, Govt Oriental Manuscripts Library, Chennai) macro drift [0.10,0.30,0.55,0.41] -> [0.30,0.32,0.55,0.41], 4 s; warm desaturated grade. At 39.2 s the frame dims to 20% and a single lamp-300 point of light appears centre (the glow that becomes the logo light in the next scene; never the mark itself).

**Music**: M2 resolves into a held breath; at 39.8 s a soft reverse swell into M3.

**Facts**: P2, P3 · **Credits**: p26

### a2-07-title · 40.0-47.0 s (7.0 s) · Act 2-solution · render: `html`

**Narration** (10 words; VO in at 40.4 s, 94 wpm in its window)

> So I built an apprentice. Meet Ezhuthu: in Tamil, 'letter'.

**On screen**

- எழுத்து
- Ezhuthu
- an apprentice for Tamil epigraphy

**Visual**: Background p07 (sunrise over the Vaigai, Madurai) graded down to 30%, slow drift [0.10,0.20,0.80,0.74] -> [0.15,0.22,0.75,0.70]. The lamp glow from a1-06 widens; at 41.4 s the logo mark (design/brand/logo/mark-reversed.svg) FADES in (0.8 s; never scales, rotates or morphs, BRAND.md section 4), then the Tamil wordmark (wordmark-ta-reversed.svg) and English wordmark (wordmark-en-reversed.svg) fade in at 43.0 s. 44.6 s sub-line 'an apprentice for Tamil epigraphy' (Instrument Sans 32 px, stone-200).

**Music**: M3 'apprentice' theme enters at 40.0: warm, hopeful, plucked strings + soft pulse, 84 bpm. This is the film's main theme.

**Facts**: R1, S1 · **Credits**: p07

### a2-08-hero-read · 47.0-60.0 s (13.0 s) · Act 2-solution · render: `comp`

**Narration** (28 words; VO in at 47.3 s, 135 wpm in its window)

> On a real Chola-period stone from Thanjavur, it reads forty-six carved letters, each with its own confidence, then the words, a phrase in today's Tamil, and its meaning.

**On screen**

- Live: ezhuthu.sparrowdecider.com
- 46 carved letters, each with the model's own probability (self-reported)
- The least certain letter: left open (?)
- Meaning by Ezhuthu (confidence 0.30)
- Photo: Richard Mortel, CC BY 2.0

**Visual**: Live capture footage/home-hero.mp4 (1920x1080, 30 fps). CROP to the hero panel only (stone + readout + Tamil/English meaning), excluding the page eyebrow 'Real temple stones, some carved over 1,100 years ago', which must not sit on this Thanjavur stone. Edit: in 3.0 -> 9.0 s at 1.0x (letter call-outs: carved shape -> modern letter + %); in 10.5 -> 15.0 s at 1.5x (all letter boxes, words fill in, the '?' letter at 0.45 sent to Restore and left open); in 19.5 -> 23.5 s at 1.0x (phrase in today's Tamil, English meaning, Tamil meaning; scroll). Total 6 + 3 + 4 = 13 s. 1.06x digital push-in over the whole scene. Pop-on labels (Instrument Sans 24 px on granite-900 chips) at 48.0, 53.6 and 57.0 s. Fallback source: design/brand/banners/hero-stone-dark.webm (23.04 s, read sequence 2-21 s).

**Music**: M3 continues; tiny chime SFX on each letter call-out in the first 6 s (max 4 chimes).

**Facts**: S13, S14, S15, E5 · **Credits**: c-hero, c-capture

### a2-09-practice · 60.0-70.0 s (10.0 s) · Act 2-solution · render: `comp`

**Narration** (14 words; VO in at 60.3 s, 89 wpm in its window)

> Practice turns real inscriptions into 1,469 drills: letters, words, gaps and formulas. Tamil first.

**On screen**

- Practice
- 1,469 drills from real stones
- letters 205 · words 540 · gaps 394 · formulas 330
- five levels, Tamil first

**Visual**: Split screen. Left 62%: footage/practice.mp4 (Tamil UI) in 0.0 -> 8.9 s at 0.9x speed (drill opens at 2.8 s, answer at 5.1 s), with a lamp-400 pulse ring on the correct answer. Right 38%: footage/practice-mobile.mp4 in 0.0 -> 8.77 s in a phone frame (390x844 shape, granite-800 bezel), offset 0.4 s. Count-up '1,469' (1.0 s) at 61.0 s over the top-left; the four-way split as a thin stacked bar (letters / words / gaps / formulas) at 64.0 s. Last 0.6 s whip-pan right into a2-10.

**Music**: M3 adds a light hand-drum pulse (original) from 60.0.

**Facts**: S2, S3, P4, S16 · **Credits**: c-capture, c-dharma

### a2-10-restore-fill · 70.0-80.5 s (10.5 s) · Act 2-solution · render: `comp`

**Narration** (22 words; VO in at 70.3 s, 133 wpm in its window)

> Restore proposes the worn-away letters. In our recorded gallery run, it filled four gaps of ten; all four match the editors' restoration.

**On screen**

- Restore
- Fills when sure
- Gallery run: 4 of 10 filled, all 4 match the editors' restoration
- 10 gaps: too few to estimate a rate

**Visual**: footage/restore-fill.mp4, re-captured 2026-11-03 (sample 'A district's name at Tiruvāliśvaram': filled -k at 72%, matches the editors' restoration; the Tiruvāvaṭutuṟai take abstained on the day). Edit: in 0.4 -> 3.3 s (click Restore at 2.94 s), then a 0.5 s 'stone dust' transition standing in for the ~20 s wait (small 'Reader -> Restorer -> confidence check' progress chip, no fake timer), then in 23.4 -> 25.4 s at 1x and 25.4 -> 33.6 s at 1.6x (response at 23.40 s; result scroll from 24.61 s; 'matches the editors' restoration' at ~32 s). Zoom 1.0 -> 1.22x onto the filled letters as they turn neem-300 (match). Lower-third with the gallery-run numbers at 76.0 s; the small-n note in stone-400 20 px under it.

**Music**: M3; a soft 'stone settles' SFX when the fill lands (~74.5 s).

**Facts**: S4, S10, S11 · **Credits**: c-capture, c-dharma

### a2-11-restore-open · 80.5-90.0 s (9.5 s) · Act 2-solution · render: `comp`

**Narration** (20 words; VO in at 80.8 s, 134 wpm in its window)

> Where it is unsure, it leaves the gap open. And that doubt becomes the lesson: experts are unsure here too.

**On screen**

- Leaves it open
- ?
- Doubt becomes the lesson
- Unsolved gaps: options proposed, sent to an expert

**Visual**: footage/restore-open.mp4 (sample 'Mamallapuram: calf pasture'). Edit: in 2.0 -> 3.2 s (click), cut to in 18.3 -> 26.6 s (response at 18.29 s, result scroll 19.50 s). Hold on the '?' gap: zoom 1.0 -> 1.5x, the open gap glows neelam-300; a card slides in 'Doubt becomes the lesson' (Fraunces 600 italic, 56 px) at 85.4 s, then a smaller line 'Unsolved gaps: options proposed, sent to an expert' at 87.6 s.

**Music**: M3 drops to strings only under 'doubt becomes the lesson'; a held chord carries into Act 3.

**Facts**: S4, S5, S12, S9 · **Credits**: c-capture, c-dharma

### a3-12-under-the-hood · 90.0-96.0 s (6.0 s) · Act 3-implementation · render: `html`

**Narration** (10 words; VO in at 90.3 s, 110 wpm in its window)

> Six agents, built with Strands Agents, pass the stone along.

**On screen**

- Built with Strands Agents
- Reader · Restorer · Interpreter · Lesson Builder · Tutor · Assessor

**Visual**: Transition: the '?' from a2-11 shrinks into a single node. Background p15 (Brihadisvara carved facade) at 15% opacity under granite-950, blurred 12 px. Six agent nodes (rounded granite-800 cards, Instrument Sans 26 px labels, lamp-400 outline) draw in left to right with 120 ms stagger and link into the pipeline spine that the next scenes animate: Reader -> Restorer -> Confidence check -> Interpreter -> Tutor team (Lesson Builder, Tutor, Assessor). A small carved-letter particle travels the spine once (the 'stone passed hand to hand'). Optional picture-in-picture: footage/how.mp4 in 2.1 -> 8.1 s (the live 'How it works' animation) at 24% size, bottom-right, labelled 'live site'.

**Music**: M4 'pipeline' enters at 90.0: original rhythmic build, mridangam-like percussion + synth pulse, 96 bpm; builds through Act 3.

**Facts**: T2, T1 · **Credits**: p15, c-capture

### a3-13-reader-restorer · 96.0-108.0 s (12.0 s) · Act 3-implementation · render: `html`

**Narration** (26 words; VO in at 96.3 s, 136 wpm in its window)

> The Reader turns photos into letters. The Restorer checks parallels and a 5-gram model, then asks Claude on Amazon Bedrock: Sonnet first, Opus when it matters.

**On screen**

- Reader: photo or EpiDoc in, letters out
- Restorer: a tool-using Strands agent, 5 tools
- retrieve_parallels: 14,355 train lines, top 20
- character 5-gram: 11 ms per gap
- Claude Sonnet 4.6 -> Claude Opus 4.6 on Amazon Bedrock
- escalate if best score < 0.6, gap > 12 letters, or no good parallel

**Visual**: Camera trucks along the spine. 96.0-99.5 s READER node: a crop of p13 (Chola inscription close-up, rect [0.20,0.25,0.45,0.41]) slides into the node and comes out as a typed Tamil line (Noto Serif Tamil, stone-50) with one bracketed gap. 99.5-108.0 s RESTORER node expands into a panel with three lanes fused by a noisy-OR into one score: (1) Parallels: a stack of 20 faint text strips flies in from a 14,355-line 'library' wall, best match highlighted; (2) 5-gram: letter probabilities tick as small bars, '11 ms' chip; (3) LLM: 'Claude Sonnet 4.6' chip, then the routing rule flips a switch and 'Claude Opus 4.6' lights (lamp-500) as the narration says 'Opus'. Tool names in JetBrains Mono 20 px: retrieve_parallels, propose_fills, check_constraints, rank_and_decide, ontology_hints. Three candidate fills land in a 'top 3' tray.

**Music**: M4 builds: second percussion layer at 99.5 s.

**Facts**: S6, T3, T8, T10, T11, T12, T18 · **Credits**: p13

### a3-14-confidence · 108.0-114.0 s (6.0 s) · Act 3-implementation · render: `html`

**Narration** (12 words; VO in at 108.3 s, 132 wpm in its window)

> Then a calibrated confidence check decides: fill it, or leave it open.

**On screen**

- Confidence check
- calibrated on validation only
- FILL
- LEAVE OPEN
- 25-second budget per request

**Visual**: The top-3 tray drops onto a gate: a horizontal gauge 0 -> 1 with the calibrated threshold line (lamp-300). Two candidates run the gate: one scores above the line and continues as a filled letter (neem-300, chisel-ease reveal) into the spine; one scores below and splits off to a neelam-300 '?' lane labelled 'leave open -> learner lesson / expert review'. Small chips: 'Platt scaling, fitted on VAL', '25 s request budget'. A stopwatch ring around the node fills to 25 s.

**Music**: M4: a single percussive 'gate' hit at 110.4 s, then the groove continues.

**Facts**: T13, T14, S4 · **Credits**: none (own animation)

### a3-15-interpreter-tutor · 114.0-123.0 s (9.0 s) · Act 3-implementation · render: `html`

**Narration** (20 words; VO in at 114.3 s, 142 wpm in its window)

> The Interpreter turns letters into meaning. A Strands Graph runs every lesson, with a Swarm of Tutor and Assessor inside.

**On screen**

- Interpreter: words, today's Tamil, a plain meaning
- Strands Graph: restore -> lesson_builder -> tutor_team
- Strands Swarm: Tutor ⇄ Assessor
- advance · repeat · hint: built on Strands Decider, with rule guardrails

**Visual**: 114.0-117.5 s INTERPRETER node: the restored line splits into word chips, then a modern Tamil phrase, then an English meaning card ('Meaning by Ezhuthu'). 117.5-123.0 s the camera pulls back: the whole pipeline sits inside a large Graph frame (three nodes restore -> lesson_builder -> tutor_team, drawn with lamp-400 edges); tutor_team opens to show two agents, Tutor and Assessor, passing a lesson card back and forth (Swarm, ⇄ arrows animate twice). A policy chip 'advance · repeat · hint' appears under the Tutor with the line 'built on Strands Decider, with rule guardrails'.

**Music**: M4 continues; melodic motif from M3 re-enters over the groove at 117.5 s (the apprentice theme, now technical).

**Facts**: S7, T1, T2, S8, T19 · **Credits**: none (own animation)

### a3-16-ontology · 123.0-130.0 s (7.0 s) · Act 3-implementation · render: `html`

**Narration** (14 words; VO in at 123.3 s, 130 wpm in its window)

> Agents look up kings, temples and formulas in a custom Tamil ontology over MCP.

**On screen**

- Custom Tamil-inscription ontology
- 1,958 named entities · 27 classes · 23,029 triples
- rulers 42 · places 357 · temples 139 · formulas 14
- served over MCP: 5 tools
- built from the train split only

**Visual**: A knowledge graph blooms behind the pipeline: nodes for rulers (laterite-400), places (lamp-300), temples (neem-300), formulas (neelam-300), drawn from app/web/src/components/how/ontology-slice.json; real labels such as Rājarāja I, Thanjavur, Madurai fade in on 6-8 nodes. An 'MCP' connector cable plugs into the Restorer and Tutor nodes; five tool names (find_entities, valid_letters, formulas_for, entity, hints_for_gap) run along it in JetBrains Mono. Counter '1,958' (1.0 s). No accuracy claim for the ontology on screen.

**Music**: M4 groove, add a shimmering high pad on the graph bloom.

**Facts**: T4, T5, T7 · **Credits**: none (own animation)

### a3-17-finetuned · 130.0-139.0 s (9.0 s) · Act 3-implementation · render: `html`

**Narration** (16 words; VO in at 130.3 s, 114 wpm in its window)

> We fine-tuned Strands decision models for Tamil: train stones only, a pre-registered pick, one held-out test.

**On screen**

- Fine-tuned Strands decision models for Tamil
- 2B · LoRA r 48 · continued from Strands Decider v1-2610
- 2,334 choice + 6,936 yes/no rows, train split only
- 96 near-duplicates removed
- 8 variants, picked on 280 validation gaps by a rule committed first
- tested once on held-out inscriptions
- 74 min on one A100 · USD 2.26
- fine-tuned · tested · not yet live

**Visual**: A 'workshop' sub-scene branching off the Restorer's top-3 tray (dotted line = not in the live path). Left: a data funnel; train stones flow in, a scrubber removes '96 near-duplicates', 5 cross-fitting folds shown as 5 coloured bands; out comes '2,334 + 6,936 rows'. Centre: 'ezhuthu-strands-2b-ft' card with three size chips (2B chosen; Sparrow tiny; Sparrow nano) and a training-loss line drawing across 580 steps. Right: a sealed envelope 'selection rule, committed first' opens on 8 variant cards on 280 VAL gaps; one card wins, then a single 'TEST: scored once' stamp. Footer badge, always visible in this scene: 'fine-tuned · tested on held-out TEST · not yet live' (neelam-300 chip). Cost chip '74 min · one A100 · USD 2.26' lands at 136.5 s.

**Music**: M4 peaks: full groove, percussion fill into 139.0.

**Facts**: D1, D2, D3, D4, D5, D6, D7, L4 · **Credits**: none (own animation)

### a3-18-agentcore · 139.0-145.0 s (6.0 s) · Act 3-implementation · render: `html`

**Narration** (11 words; VO in at 139.3 s, 121 wpm in its window)

> The live app runs on Amazon Bedrock AgentCore, serverless, as code.

**On screen**

- Runs on Amazon Bedrock AgentCore Runtime
- CloudFront -> API Gateway (JWT) -> Lambda -> AgentCore -> Amazon Bedrock
- 5 CDK stacks · Cognito · DynamoDB · ontology MCP inside the bundle

**Visual**: The whole pipeline compresses into one box labelled 'AgentCore Runtime: ezhuthu_tutor' (Python 3.12, arm64). The cloud path draws left to right as a lit request travelling: phone/browser -> CloudFront (private S3 web) -> API Gateway HTTP API + JWT (Cognito) -> Lambda proxy (Node 22) -> AgentCore Runtime -> Amazon Bedrock (Claude Sonnet 4.6 / Opus 4.6), with DynamoDB beside the API. Text labels only, no AWS logos. '5 CDK stacks' chip; the request returns to the phone inside a 25 s ring.

**Music**: M4 resolves on a downbeat at 145.0 (cut to silence for 0.3 s).

**Facts**: T15, T16, T14, T18 · **Credits**: none (own animation)

### a4-19-who · 145.0-156.0 s (11.0 s) · Act 4-impact · render: `comp`

**Narration** (24 words; VO in at 145.3 s, 138 wpm in its window)

> Students practise on real stones. Temple visitors point a phone at Tamil text. And what it cannot settle goes to an epigraphist's review queue.

**On screen**

- Students and heritage guides
- Temple visitors and heritage volunteers
- Epigraphists' review queue
- Next: learner pilot with AWS UG Madurai student volunteers

**Visual**: Three people beats, each with a caption. 145.3-149.0 s: p35 (school children, Kanchipuram district, alphabet charts behind) wide, slow push [0.05,0.10,0.90,0.83] -> [0.12,0.12,0.80,0.74], composite of the practice-mobile capture in a phone frame lower-right; caption 'Students and heritage guides'. 149.0-152.5 s: p10 (visitors passing inscribed pilasters, Brihadisvara) push-in [0.05,0.10,0.90,0.83] -> [0.25,0.20,0.65,0.60]; a phone silhouette overlay reads letters off the wall (graphic, not a measured capture); caption 'Temple visitors and heritage volunteers'. 152.5-156.0 s: p32 (documenters at work, Arachalur) [0.15,0.20,0.70,0.65] hold, with a review-queue card sliding in ('3 gaps waiting for an expert', neelam-300 '?' badges); caption 'Epigraphists' review queue'. Small footer line throughout: 'Next: learner pilot with AWS UG Madurai student volunteers'.

**Music**: M5 'people' at 145.3: M3 theme returns, fuller, strings + pulse, rising.

**Facts**: H1, H2, H3, H4, H6, S9 · **Credits**: p35, p10, p32, c-capture

### a4-20-proof · 156.0-165.0 s (9.0 s) · Act 4-impact · render: `html`

**Narration** (10 words; VO in at 157.5 s, 83 wpm in its window)

> On 413 held-out test gaps, 62.7% match the editors' restoration.

**On screen**

- 62.7%
- 259 of 413 held-out test gaps match the editors' restoration
- pre-registered, chosen on validation, test scored once
- same gaps: copying a parallel 47.2% · character 5-gram 56.7%

**Visual**: Background p11 (Thanjavur plinth band) at 20%, blur 8 px. '62.7%' slams in (Fraunces 700, 300 px, lamp-300, 0.35 s overshoot ease) at 160.6 s, synced to the narration. A 413-dot field (21 x 20 grid) fills: 259 dots light neem-300. Qualifier line under it stays on screen the whole time. At 162.8 s a quiet footnote row (Instrument Sans 20 px, stone-400) shows the classic methods on the same gaps; no model names, no model-vs-model graphic.

**Music**: M5 swell; a low boom hit at 160.6 s on the number.

**Facts**: A1, A13, A3, A4 · **Credits**: p11

### a4-21-knows · 165.0-172.0 s (7.0 s) · Act 4-impact · render: `html`

**Narration** (15 words; VO in at 165.3 s, 140 wpm in its window)

> When it commits, nine in ten fills match. When it doesn't know, it says so.

**On screen**

- 9 in 10
- 90.8% of fills match (187 of 206)
- fills about half, flags the rest for an expert
- It knows when it does not know.

**Visual**: The 413-dot field from a4-20 re-sorts into two groups: 206 'filled' dots (187 neem-300, 19 dim) and 207 '?' dots in neelam-300 that drift toward an 'expert review' tray. '9 in 10' slams in at 166.2 s, '90.8% (187 of 206)' beneath. At 169.0 s everything dims except one glowing '?' and the line 'It knows when it does not know.' (Fraunces 600 italic 64 px, stone-50).

**Music**: M5 holds its highest chord, then pulls back to the M1 drone under the last line.

**Facts**: A7, L2, S9 · **Credits**: none (own animation)

### c-22-close · 172.0-180.0 s (8.0 s) · Act close · render: `html`

**Narration** (10 words; VO in at 172.4 s, 82 wpm in its window)

> Ezhuthu. Learn to read the stone. Help read the backlog.

**On screen**

- எழுத்து Ezhuthu
- Learn to read the stone. Help read the backlog.
- Built with Strands Agents, on Amazon Bedrock AgentCore
- ezhuthu.sparrowdecider.com
- github.com/Vivek0712/ezhuthu
- (end crawl: credits, see CREDITS.md 'End card for storyboard v2')

**Visual**: 172.0-176.0 s: p05 (Meenakshi gopuram over the Golden Lotus tank, Madurai) at 35%, slow drift [0.10,0.05,0.80,0.74] -> [0.14,0.05,0.74,0.69] (the film ends where it began, in Madurai). Lockup (design/brand/logo/lockup-stacked-reversed.svg) FADES in at 172.2 s; tagline at 173.2 s (Fraunces 600 52 px); 'Built with Strands Agents, on Amazon Bedrock AgentCore' (Instrument Sans 26 px) at 174.0 s; URLs in JetBrains Mono 28 px lamp-300 at 174.6 s. 176.0-180.0 s: lockup and URLs move to the top third (fade-through, no scaling of the mark) and a fast two-column end crawl runs underneath (Instrument Sans 15 px, ~24 lines, 4 s): inscription texts DHARMA (ERC 809994) + editors CC BY-SA 4.0; hero photo Richard Mortel CC BY 2.0; every stock asset used (title, author, licence, 'via Wikimedia Commons'); fonts SIL OFL 1.1; narration Amazon Polly; music original. Final frame (179.6-180.0) holds the URLs. The full list also goes in the video description.

**Music**: M6 'resolve' at 172.0: M3 theme's final phrase, ending on the open drone note at 179.0; 1.0 s tail to 180.0.

**Facts**: R1, T15 · **Credits**: p05, c-dharma, c-hero, c-fonts, c-polly, c-music

## Full narration script (for Polly)

| Scene | VO in (s) | Line |
| --- | --- | --- |
| a1-01-cold-open | 0.25 | These temple walls are written in Tamil. The letters are fading. |
| a1-02-place | 5.3 | From Madurai to Thanjavur, kings carved their words into temple walls. Thanjavur's great temple has stood for over a thousand years. |
| a1-03-madurai-in-stone | 14.3 | Madurai itself is carved into them: twenty-five editions name it. |
| a1-04-damage | 20.3 | But time wears the letters away. Of the 1,320 inscriptions we studied, 65% carry a gap or an editor's restoration. |
| a1-05-few-readers | 29.3 | Yet in 2021, India had about 23 epigraphists, for nearly one lakh inscriptions. |
| a1-06-slow | 36.3 | And training a new reader is slow. |
| a2-07-title | 40.4 | So I built an apprentice. Meet Ezhuthu: in Tamil, 'letter'. |
| a2-08-hero-read | 47.3 | On a real Chola-period stone from Thanjavur, it reads forty-six carved letters, each with its own confidence, then the words, a phrase in today's Tamil, and its meaning. |
| a2-09-practice | 60.3 | Practice turns real inscriptions into 1,469 drills: letters, words, gaps and formulas. Tamil first. |
| a2-10-restore-fill | 70.3 | Restore proposes the worn-away letters. In our recorded gallery run, it filled four gaps of ten; all four match the editors' restoration. |
| a2-11-restore-open | 80.8 | Where it is unsure, it leaves the gap open. And that doubt becomes the lesson: experts are unsure here too. |
| a3-12-under-the-hood | 90.3 | Under the hood: six agents, built with Strands Agents, passing the stone along. |
| a3-13-reader-restorer | 96.3 | The Reader turns a photo into letters. The Restorer searches parallel passages, weighs a 5-gram model, and asks Claude on Amazon Bedrock: Sonnet first, Opus when it matters. |
| a3-14-confidence | 108.3 | Then a calibrated confidence check decides: fill it, or leave it open. |
| a3-15-interpreter-tutor | 114.3 | The Interpreter turns letters into meaning. A Strands Graph runs every lesson, with a Swarm of Tutor and Assessor inside. |
| a3-16-ontology | 123.3 | The agents look up kings, temples and formulas in a custom Tamil ontology, over MCP. |
| a3-17-finetuned | 130.3 | And we fine-tuned Strands decision models for Tamil: training data from train stones only, a pre-registered pick, one held-out test. |
| a3-18-agentcore | 139.3 | All of it runs on Amazon Bedrock AgentCore, serverless, and defined as code. |
| a4-19-who | 145.3 | Students practise on real stones. Temple visitors point a phone at Tamil text. And what it cannot settle goes to an epigraphist's review queue. |
| a4-20-proof | 157.5 | On 413 held-out gaps, it matches the editors' restoration 62.7% of the time. |
| a4-21-knows | 165.3 | When it commits, nine in ten fills match. When it doesn't know, it says so. |
| c-22-close | 172.4 | Ezhuthu. Learn to read the stone. Help read the backlog. |

## End credits crawl (c-22-close, 176.0-180.0 s; also in the video description)

Footage and photos via Wikimedia Commons:

- "S-TN-34 Meenakshi Amman Temple South Gopuram enriched with delicate Stucco works", MADHURANTHAKAN JAGADEESAN, CC BY-SA 4.0 (share-alike) [p01]
- "Tamil Inscription in wall of agneeshwaran Temple", Neechalkaran, CC BY-SA 4.0 (share-alike) [p17]
- "Aerial view of Madurai Meenakshi amman temple", Prakashkumar, CC BY-SA 4.0 (share-alike) [p04]
- "Tanjavur Song Devotee", Rainer Halama, CC BY-SA 4.0 (share-alike) [v05]
- "Brihadeeswarar temple evening, Thanjavur, Tamilnadu", Cafeskool, CC BY-SA 4.0 (share-alike) [p14]
- "Tamil Inscriptions in Thanjavur Brahadeeshwara Temple written 1000 years ago", KARTY JazZ, CC BY-SA 4.0 (share-alike) [p11]
- "Mamallapuram, Shore Temple, Dusk, India", Vyacheslav Argenberg, CC BY 4.0 [p20b]
- "3D Scanning of The Arachalur 400CE Musical Notations Inscription 01", Mythic Society Inscriptions 3D Scanning Project, CC BY-SA 4.0 (share-alike) [p32]
- "Inscriptions at the Brihadisvara Temple, Thanjavur, Tamil Nadu, India (2016) 1", Nandhinikandhasamy, CC BY-SA 4.0 (share-alike) [p09]
- "Tamilnadu Govt-Oriental Manuscripts Library And Research Center-Tamil alphabets palm leaf book-2025-Sep-09", Info-farmer, CC BY-SA 4.0 (share-alike) [p26]
- "A sunrise over Vaigai River in Madurai Tamil Nadu India", Paulthy, CC BY 2.0 [p07]
- "Brihadeeswarar Temple 3587", Vengolis, CC BY-SA 4.0 (share-alike) [p15]
- "1010 CE Brihadishwara Shiva Temple, inscription, built by Rajaraja I, Thanjavur Tamil Nadu India", Richard Mortel from Riyadh, Saudi Arabia, CC BY 2.0 [p13]
- "Tamil Nadu school kids", McKay Savage from London, UK, CC BY 2.0 [p35]
- "Inscriptions at the Brihadisvara Temple, Thanjavur, Tamil Nadu, India (2016) 2", Nandhinikandhasamy, CC BY-SA 4.0 (share-alike) [p10]
- "Meenakshi Temple, Gopuram, Madurai, India", Vyacheslav Argenberg, CC BY 4.0 [p05]

- Inscription texts: DHARMA project (ERC grant 809994) and the named editors of each edition, CC BY-SA 4.0
- Home-hero stone photo: Richard Mortel, 'Brihadishwara Temple ... Thanjavur (38)', CC BY 2.0, via Wikimedia Commons (cropped, letter boxes overlaid)
- Live-site captures: Ezhuthu, https://d3jz2k92ne5puo.cloudfront.net (own work; on-screen inscription texts DHARMA, CC BY-SA 4.0)
- Fonts: Noto Serif/Sans Tamil, Noto Sans Brahmi, Noto Sans Grantha, Fraunces, Instrument Sans, JetBrains Mono (SIL OFL 1.1)
- Narration voice: Amazon Polly
- Music and sound design: original score (no third-party music)
- Built with Strands Agents and Strands Decider; runs on Amazon Bedrock AgentCore; Claude Sonnet 4.6 and Claude Opus 4.6 on Amazon Bedrock.

**Licence of the film**: the cut includes 11 CC BY-SA assets (p01, p17, p04, v05, p14, p11, p32, p09, p26, p15, p10), so the finished film is an adaptation that must be released under CC BY-SA 4.0 (state this in the video description), or those shots must be replaced.

## v3 cut: review fixes (2026-11-03). Supersedes the crawl above where they differ

Reviewer verdict "changes" (14 findings) fixed in the scene sources; per-scene detail in `storyboard.json` `render_note` ("v3 ...").

| At | Fix | Facts |
| --- | --- | --- |
| 0-5 s | Opens on the inscribed temple wall (p17) from frame 0; stakes on screen by 1.2 s: "About 23 epigraphists. Nearly one lakh inscriptions." (India, 2021 · The Federal). p01 gopuram removed from the film | P1, E7 |
| 21, 31, 61 s (and 16, 125 s) | Count-ups 0.45 s ease-out; the 23 fades in at its final value | P7, P1, S2, P13, T4 |
| 47-60 s | Hero capture framed on the panel only: legend in, Pause/Replay and page credit out, Live pill + credit in a dark top band | S13, S14 |
| 60 s | Practice scene elements in from 0.0 s | S2 |
| 70-90 s | Restore scenes rebuilt from 3x-DPR stills of the live page; element-exact framing, hard cuts (no scroll capture, no doubled rows), lower-thirds in opaque bottom bands, nothing over the headline, whole lines in the push-in | S11, S12, S17 |
| 90-96 s | "Lesson graph" box (Lesson Builder) with a separate "Swarm" box (Tutor, Assessor); nodes in from 0.05 s; stone flash (p10) 95-96 s | T1, T2 |
| 96-108 s | "11 ms per gap (p50, Apple M4 Pro)"; top 3 = 0.08 / 0.08 / 0.07; stone flash (p11) 107-108 s | T12, S14 |
| 122-123 s | Stone flash (p09) | - |
| 123-130 s | Ontology graph over a dimmed temple plate (p14) | T4, T5 |
| 130-139 s | "74 min per variant on one A100 · USD 2.26 total"; "Fills 57.6% of held-out TEST gaps, 92.0% match" (fine-tuned, not yet live) | D7, D8, A17 |
| 143.75-145 s | AgentCore beat ends on the live site on a phone | T15, S16 |
| 145-156 s | Beats cut on the narration (temple at 147.5 s, review queue at 150.6 s); "Illustration" label on a dark pill, 22 px | H1-H4 |
| 154.8-157.5 s | Dot field lights from 156.3 s on four synthesized chisel taps (156.05-157.2 s) | A1 |
| 172-180 s | Credits from 174.85 s (about 5 s), 21 px at 86% white on an 82% dark veil, sound credits added | credits |

Audio: the film now uses the finished v2 soundtrack (`ezhuthu-video/audio-v2/soundtrack-v2.wav`: Polly Arjun narration,
CC0/CC BY temple ambience, original score, SFX), rebuilt with the new taps; `compile.sh` uses it as is
(`SOUNDTRACK=""` falls back to the v1 in-script mix). Narration text is unchanged from `audio-v2/narration-v2.json`.

Share-alike assets in the v3 cut: p17, p04, v05, p14, p11, p32, p09, p26, p15, p10 (p01 and p13 are not in the film).
The end card and the video description (`CREDITS.md` "Video description") carry the full list.
