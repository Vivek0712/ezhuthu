# Ezhuthu: 30-second social cuts

Four cuts of one 30.000 s piece, built for muted autoplay (burned-in, word-lit captions) with a hook on frame 1.

| File (in `ezhuthu-video/social/out/`) | Size | For | How it is made |
| --- | --- | --- | --- |
| `ezhuthu-teaser-30s-16x9.mp4` | 1920x1080 | LinkedIn (and YouTube, X) | main-film scenes + own graphics + captions + end card (`pages/teaser.html?fmt=wide`) |
| `ezhuthu-teaser-30s-1x1.mp4` | 1080x1080 | LinkedIn feed autoplay | the same shots in a 1080x608 panel, brand band on top, big captions below (`?fmt=square`) |
| `ezhuthu-reel-30s-9x16.mp4` | 1080x1920 | Instagram Reel (and Shorts) | vertical-native page `pages/reel.html` (no crop of the film) |
| `ezhuthu-reel-30s-4x5.mp4` | 1080x1350 | Instagram feed | crop of the reel, y 285..1635 (the reel keeps all text in that band) |

All four: H.264 High, yuv420p, 30 fps CFR, 900 frames, AAC 320k 48 kHz, -14 LUFS integrated, true peak -1.5 dBTP.
Contact sheets (1 frame per second): `ezhuthu-video/social/out/contact-*.jpg`.

## Arc and narration (one VO for every cut, 72 words)

Problem 0-9 s, the build 9-12 s, how it works 12-27 s (four fast beats), end card 27.2-30 s (bell, no voice).
Voice: the sound team's choice in `media/video/audio-v2/narration-v2.json` (Amazon Polly **Arjun**, generative,
en-IN), read at 100% so 30 s fits (the film uses 90-95% with pauses). Placement and per-word times: `vo.json`.

**Ezhuthu pronunciation (final, user pick 2026-11-03):** option 3 =
`<phoneme alphabet="ipa" ph="ˈeɭʊt̪ːʊ">Ezhuthu</phoneme>` (reference: `ezhuthu-video/audio-v2/pron-options/opt3.mp3`).
It is pinned in `social.json` (`vo.ezhuthu_ph`) and passed explicitly when rendering (`--ezhuthu-ph`), because
`narration-v2.json` may still carry the older IPA. "Ezhuthu" is spoken once (line 3). To change it: re-run
`tools/vo.py --rate 100% --ezhuthu-ph "<IPA>"`, then `tools/audio.py`, then the render (about 5 minutes in all;
the generative voice varies slightly per call, and the pages re-time themselves from `vo.json`).

| # | On the clock | Line | Facts |
| --- | --- | --- | --- |
| 1 | 0.45 | Tamil, one of the oldest living languages, is fading from temple walls. | E1 (classical language; user wording "one of the oldest living languages"), P7 |
| 2 | 5.1 | In 2021, India had about 23 epigraphists. | P1 / E7 (The Federal, 3 Aug 2021) |
| 3 | 9.2 | So I built Ezhuthu, an apprentice. | R1 |
| 4 | 12.1 | A team of Strands agents reads the stone, letter by letter. | T1, R1 (Reader) |
| 5 | 15.7 | Lost letters? It checks thousands of parallels, and fills only when sure. | 14,355 train lines (retrieve_parallels), S4, A7 |
| 6 | 20.7 | Nine in ten fills match the editors' restoration. | A7 (187 of 206 = 90.8%); on screen "on 413 held-out test gaps" (A1) |
| 7 | 24.1 | It explains the meaning, and teaches you to read it. | R1 (Interpreter, Tutor), S2, H2 |

On-screen numbers, first half: 2,000 years of Tamil writing (P4); 65% of the 1,320 inscriptions we studied carry a
gap or an editor's restoration (P6, P7); about 23 epigraphists in 2021 for nearly 1 lakh inscriptions (P1).

The four "how it works" beats (both layouts):
1. **Reader**: the real Thanjavur stone; letter boxes light one by one and the letters fly into modern Tamil; agent
   chips Reader, Restorer, Interpreter, Tutor, Assessor, "a team of agents, built with Strands Agents" (teaser: the
   live hero capture, then the film's Reader shot).
2. **Restorer**: a real gap from the live gallery (`…பாம்புணி[?]கூற்றத்து…`, a district name in a Tiruvalisvaram
   inscription). Four sources light and pulse into a Confidence check: 14,355 parallel lines, the custom Tamil ontology
   (1,958 entities), fine-tuned Strands decision models, Claude on Amazon Bedrock. Then "72% sure, FILL", க் drops into
   the gap, "✓ matches the editors' restoration" (CREDITS `c-capture`: filled -k at 72%, matches the edition).
3. **Proof**: 9 in 10, 90.8% (187 of 206) on 413 held-out test gaps; it fills about half and flags the rest.
4. **Meaning and teaching**: the hero stone with its real Interpreter output in Tamil and English (ஒரு குடிக்கு குளம்
   கொடுக்கப்படும் / "A tank is to be given for a settlement.", confidence 0.30, from `app/web/src/hero/hero-view.json`),
   then a Practice drill answered on a phone (live capture), "on Amazon Bedrock AgentCore".

No status claim for the decision models (no "live", no "not yet live"); the 62.7% / 90.8% numbers are the pre-rank
configuration's (scored on TEST before the switch to the fine-tuned decider) and are not attributed to any single component.

## Shots

**Teaser (16:9 and 1:1)**: 0-12 s reuses the rendered main-film scenes (all-intra copies in
`ezhuthu-video/social/clips/`): weathered wall + "Who will read the stones?" on frame 1 -> Madurai gopuram -> the gap
and 65% -> epigraphists at Arachalur, 23 -> எழுத்து lockup. 12-27 s: live hero capture (letter boxes) -> the film's
Reader shot -> the Restore beat (own graphic, `SOC.restoreBeat`) -> 9 in 10 (film; held before its "?" outro; the
caption drops below its "expert review" chip) -> meaning card on the stone (own graphic) -> the film's Practice shot
-> end card. Cut times come from `vo.json` word times (`pages/teaser.html`, `SH`).

**Reel (9:16, 4:5)**: hook = the stone with all 46 boxes igniting under "Who will read the stones?" -> Meenakshi
gopuram tilt-up, "2,000 years of Tamil writing" -> wall wearing away, 65% -> big 23 -> lockup + vertical pipeline ->
Reader beat -> Restore beat (2x2 sources -> Confidence check -> FILL) -> 9 in 10 dots -> meaning card -> Practice on a
phone -> end card over the Thanjavur vimana. Text only in x 60..930, y 250..1500; captions on a dark pill at about
y 1300-1490; nothing important above y 300, so the 4:5 crop keeps everything.

## Audio

`tools/audio.py`: temple hand-bell dings at 0.0 s, 9.05 s (the turn) and 27.15 s (end card), synthesized (inharmonic
partials, no samples); soft tanpura drone in C# (Pa-Sa-Sa-Sa, synthesized); no conch. Bed ducked 10 dB under the
voice; two-pass loudnorm to -14 LUFS, TP -1.5 dBTP; cut to 30.000 s.

## Build

```
# 1 narration (generative engine has no word speech marks: word times from Amazon Transcribe streaming)
ezhuthu-video/social/work/venv/bin/python media/social/tools/vo.py --rate 100% --ezhuthu-ph "ˈeɭʊt̪ːʊ"   # venv = amazon-transcribe + boto3
python3 media/social/tools/audio.py        # bed + mix -> ezhuthu-video/social/audio/mix.wav
python3 media/social/tools/srt.py          # captions.srt sidecar
# 2 all-intra copies of the main-film scenes the teaser uses (re-run if the film scenes are re-rendered)
for b in a1-01-cold-open a1-04-damage a1-05-few-readers a2-07-title a2-08-hero-read a2-09-practice a3-13-reader-restorer a4-21-knows; do
  ffmpeg -y -i ezhuthu-video/scenes/$b.mp4 -an -c:v libx264 -crf 17 -g 1 -pix_fmt yuv420p ezhuthu-video/social/clips/$b.mp4; done
# 3 render (run from the worktree root)
node media/social/render.mjs teaser-16x9 teaser-1x1 reel-9x16 reel-4x5
node media/social/render.mjs --stills 0,1.5,10 reel-9x16       # spot stills
```

## LinkedIn post (with the 16:9 or 1:1 video)

> Tamil is one of the oldest living languages, and its history is carved into temple walls. The letters are wearing
> away: 65% of the 1,320 inscriptions I studied carry a gap or an editor's restoration. In 2021, India had about 23
> epigraphists to read them.
>
> So I built Ezhuthu (எழுத்து, "letter"): an apprentice for Tamil epigraphy. A team of agents built with Strands
> Agents turns a photo of a stone into letters. Where letters are lost, the Restorer checks 14,355 lines from other
> inscriptions, a custom Tamil-inscription ontology, fine-tuned Strands decision models and Claude on Amazon Bedrock,
> and fills a gap only when it is sure. Then it gives the words and the meaning, in Tamil and English, and teaches you
> to read the stone yourself. It runs on Amazon Bedrock AgentCore.
>
> On 413 held-out test gaps, 62.7% match the editors' restoration. When it commits to a fill, 90.8% do; the rest go
> to an expert.
>
> Try it: https://ezhuthu.sparrowdecider.com
> Code: https://github.com/Vivek0712/ezhuthu
>
> #StrandsAgents #AmazonBedrock #AgentCore #Tamil #Epigraphy #Madurai #AIforGood

First comment (credits): Photos and video via Wikimedia Commons: MADHURANTHAKAN JAGADEESAN, Neechalkaran, Mythic
Society Inscriptions 3D Scanning Project, Nandhinikandhasamy (CC BY-SA 4.0); Paulthy, Richard Mortel (CC BY 2.0).
Inscription texts: DHARMA project, CC BY-SA 4.0. Narration: Amazon Polly. Music: original. The video is shared under
CC BY-SA 4.0.

## Instagram caption (with the Reel / 4:5)

> Who will read the stones?
>
> Tamil is one of the oldest living languages, and its letters are fading from temple walls. In 2021, India had about
> 23 epigraphists.
>
> Ezhuthu (எழுத்து, "letter") is a team of AI agents that reads the stone letter by letter, fills lost letters only
> when it is sure, explains the meaning in Tamil and English, and teaches you to read it. When it commits, 9 in 10
> fills match the editors' restoration (on 413 held-out test gaps). When it is unsure, it asks an expert.
>
> Built with Strands Agents, on Amazon Bedrock AgentCore. Try it: link in bio (ezhuthu.sparrowdecider.com)
> Code: github.com/Vivek0712/ezhuthu
>
> Photos via Wikimedia Commons: Richard Mortel (CC BY 2.0); MADHURANTHAKAN JAGADEESAN, Neechalkaran, Mythic Society
> Inscriptions 3D Scanning Project, Cafeskool (CC BY-SA 4.0). Texts: DHARMA, CC BY-SA 4.0. Video CC BY-SA 4.0.
>
> #Tamil #தமிழ் #Epigraphy #Inscriptions #Madurai #Thanjavur #TamilNadu #TempleArchitecture #History #Heritage
> #AI #AgenticAI #StrandsAgents #AmazonBedrock #AWS #AIforGood

## Copy guard rails applied

Never "experimental", "Strands AI", "AWS AI", "correct", "state of the art", "first", "beats humans", or the banned
company name; restorations always "match the editors' restoration"; "over 1,100 years" not used (no Pallava shot);
no Tamil-Brahmi claim; "fine-tuned Strands decision models" with no live / not-live status claim; Madurai written
மதுரை where shown (மதிரை is not shown in these cuts). Live URL: https://ezhuthu.sparrowdecider.com (live since 2026-11-04;
also served at https://d3jz2k92ne5puo.cloudfront.net).

## Files

- `social.json` cut list (voice, line placement, bells, formats, shot lists) · `vo.json` per-word times (generated)
- `pages/teaser.html`, `pages/reel.html`, `pages/_lib/{social.js,social.css}` (load `media/video/scenes/_lib`)
- `render.mjs` renderer · `tools/vo.py`, `tools/audio.py`, `tools/srt.py` · `captions.srt`
- binaries: `ezhuthu-video/social/{out,vo,audio,clips,frames,work}/`
