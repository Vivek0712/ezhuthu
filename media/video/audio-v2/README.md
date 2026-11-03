# Ezhuthu film, audio v2

Soothing South Indian temple ambience, a calmer narration read and a mild original score for the 180.0 s film.
v1 (`ezhuthu-video/audio/`, `media/video/narration.json`, `captions.srt`) is untouched.

## Files

| What | Where |
| --- | --- |
| Final soundtrack, 48 kHz stereo 24-bit, exactly 8,640,000 samples (180.000 s) | `/Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2/soundtrack-v2.wav` |
| 30 s opening preview | `/Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2/preview-opening.mp3` |
| Narration stem (180 s, mono float) and per-scene WAVs | `ezhuthu-video/audio-v2/narration-v2.wav`, `ezhuthu-video/audio-v2/vo/Arjun-generative/` |
| Alternate full renders (same v2 text, all fit) | `ezhuthu-video/audio-v2/vo/Gregory-long-form/`, `vo/Kiara-generative/` |
| Voice auditions (opening two scenes) | `ezhuthu-video/audio-v2/auditions/*-opening.mp3`, `auditions.json` |
| Stems (vo, amb, music, punct = bells, sfx, bed, premix) | `ezhuthu-video/audio-v2/stems/` |
| Checks (verify.json, levels.json, ebur128.txt, spectrograms, sources.json, pronunciation tests) | `ezhuthu-video/audio-v2/check/` |
| Per-scene narration: text, SSML, file, duration, offset, captions | `narration-v2.json` (this folder) |
| Captions for the v2 narration | `captions-v2.srt` (this folder) |
| Build | `mix-v2.sh` (this folder) -> `tools/build_v2.py`, `tools/verify_v2.py` |
| Narration synth / auditions / ASR check | `tools/synth_v2.py`, `tools/audition_v2.py`, `tools/asr_check.py`, `tools/v2lib.py` |
| Sound sources and licences | `SOUND-CREDITS.md` |

Rebuild: `bash media/video/audio-v2/mix-v2.sh` (add `RESYNTH=1` to re-render the narration with Polly; generative
Polly is not bit-exact between runs, so re-check fit and captions after a re-render).

## Voice

**Amazon Polly Arjun, en-IN, generative engine**, paced per scene at the slowest of 90% + 350 ms sentence breaks,
95% + breaks, 95%, 100% that leaves >= 0.30 s in the scene's VO window (105% was never needed).

Auditions (opening two scenes, rate 90% + breaks; `auditions/`):

| Voice | Engine | Pace (wpm) | Median F0 | Fit both windows | Notes |
| --- | --- | --- | --- | --- | --- |
| Arjun (en-IN, m) | generative | 135 | 86 Hz | no at 90% (yes at 95%) | deepest, least harsh male (2.5-6 kHz energy -21 dB vs body); native Indian English; male voice fits the first-person "So I built" |
| Gregory (en-US, m) | long-form | 129 | 124 Hz | no at 90% | Polly's narration engine; warm, darkest spectrum; US accent on Tamil names; long natural sentence pauses |
| Kiara (en-IN, f) | generative | 130 | 243 Hz | no at 90% | best place-name recognition in the ASR check; brighter; female voice on "So I built" |
| Kajal (en-IN, f) | generative | 167 | 238 Hz | yes | quick read, least calm |
| Arthur (en-GB, m) | neural | 151 | 109 Hz | yes | harsher upper mids (-13.7 dB), neural sounds less natural |
| Matthew (en-US, m) | generative | 142 | 109 Hz | edge | clear, more air/hiss |

Why Arjun: the user called the narration "awesome" (2026-11-03) and Arjun is the existing film voice; with the
calmer v2 pacing, sentence breaths and fixed pronunciation it is the warmest, deepest and least harsh male read, it
keeps Indian English on Tamil place names, and a male voice matches VOICE.md's first-person turn. Gregory long-form
(documentary narrator) and Kiara (best name handling) are fully rendered alternates if a different voice is wanted.

Intelligibility (no listening possible): every final scene was run through Amazon Transcribe streaming (en-IN).
All 22 come back word-for-word except Ezhuthu (heard as "Elutu", as intended) and "5-gram" (heard as "5 g").

### Pronunciation (SSML)

- **Ezhuthu**: `<phoneme alphabet="ipa" ph="ˈeɭʊt̪ːʊ">` in every scene that says it (a2-07, c-22): the user's pick,
  option 3 (`ezhuthu-video/audio-v2/pron-options/opt3.mp3`), 2026-11-03. Transcribe hears the re-rendered scenes as
  "Elutu", the same as the reference option. (The first v2 render used ˈeɻʊt̪ʊ; the user rejected it.)
- **Thanjavur**: plain text. Transcribe returned "Thanjavur" for 3 of 4 plain renders and 0 of 4 for either IPA
  (ˈt̪aɲd͡ʒaːʋuːr, ˈt̪aɲdʒaːʋuːr); tests in `check/thanjavur/`. Both scenes (a1-02, a2-08) now come back as "Thanjavur".
- Madurai, Meenakshi, Rajaraja, Keeladi, Uttiramerur, Chola: plain text for the en-IN voice. Vatteluttu: IPA
  `ˈʋʌʈʈeɻʊt̪t̪ʊ` (not in the script). Only a1-02, a2-07, a2-08 and c-22 were re-rendered for these fixes; the other
  18 scenes are the same audio as before (`synth_v2.py --only ...`).
- `AgentCore` -> "Agent Core", `5-gram` -> "five-gram", "read" in the tagline forced to /ɹiːd/, 2021 read as a year.

## Script changes (user direction 2026-11-03)

Numbers are unchanged; every scene fits with >= 0.3 s margin. `narration-v2.json` has `text` (new) and
`narration_v1` per scene; the film's on-screen captions should use `captions-v2.srt`.

| Scene | v2 text |
| --- | --- |
| a1-02 | Tamil is one of the oldest living classical languages, written in stone for over 2,000 years, from Madurai to Thanjavur. |
| a1-03 | Sangam poets sang of Madurai. Its name is carved in these stones too. |
| a1-04 | Sun and rain wear the letters away. 65% of the 1,320 inscriptions we studied are damaged. |
| a1-05 | In 2021, India had only about 23 epigraphists for nearly one lakh inscriptions. |
| a1-06 | And every year, more of the story is lost. |
| a2-08 | On a Chola-period stone from Thanjavur, it reads the letters, the words, then the meaning. Stones like it record gifts to temples, lamps to burn forever, land and water. |
| c-22 | Ezhuthu. Let the stones speak again. Learn to read the stone. Help read the backlog. |

Notes for the edit: (1) a1-03's kinetic type still shows "25 editions name Madurai / 23 in a Chola king's title";
the narration now says the name is carved in the stones, which the overlay supports, but the count is no longer
spoken. (2) a1-02 now says "over 2,000 years" for Tamil writing while the vimana lower-third says "completed 1010 CE";
the two are about different things (the language vs the temple); keep them visually separate. (3) a2-08 no longer
speaks "forty-six letters, each with its own confidence"; the on-screen read still shows them.
Corpus check for a2-08: DHARMA titles mention donation 244, land 137, lamp 101, grant 96, perpetual 69, gift 65,
village 56, tank 14 times (of 1,320; `benchmark/inscriptions.jsonl`). "Lamps to burn forever" = perpetual-lamp endowments.
The interpreter gives the meaning in English and modern Tamil (`src/ezhuthu/agent/interpreter.py`).

Considered and not used: "still spoken by tens of millions" (FACTS.md section 6 rejects speaker totals: the Census
table could not be opened); "Pallava kings" (no room; the Pallava Shore Temple shot and the "410 in Pallava
inscriptions" overlay carry it in a1-04).

## External facts

| Claim in the narration | Source |
| --- | --- |
| Tamil is "one of the oldest living classical languages" | Wikipedia, "Tamil language": "one of the longest-surviving classical languages in the world" (refs 10, 11 there), https://en.wikipedia.org/wiki/Tamil_language (read 2026-11-03; *secondary*). India's declaration: Government of India declared Tamil a Classical Language on 12 October 2004 (FACTS.md E1), https://www.pmindia.gov.in/en/news_updates/cabinet-approves-conferring-status-of-classical-language-to-marathi-pali-prakrit-assamese-and-bengali-languages |
| "written in stone for over 2,000 years" | Earliest Tamil-Brahmi inscriptions (rock beds, e.g. Mangulam near Madurai) dated 3rd/2nd century BCE (Iravatham Mahadevan, "Recent discoveries of Jaina cave inscriptions in Tamilnadu", 1994; Zvelebil 1973), as summarised at https://en.wikipedia.org/wiki/Tamil-Brahmi (read 2026-11-03; *secondary*). Also FACTS.md P4 ("2,000 years of Tamil writing"). |
| "Sangam poets sang of Madurai" | FACTS.md E6: Madurai is described in Sangam-era Tamil texts, https://en.wikipedia.org/wiki/Meenakshi_Temple (cites Ramaswamy 2017; Britannica "Sangam literature"); *secondary* |
| "Its name is carved in these stones too" | FACTS.md P13 (25 editions contain *matirai*) |
| "only about 23 epigraphists" in 2021, "nearly one lakh inscriptions" | FACTS.md P1/E7, The Federal, 3 Aug 2021, https://thefederal.com/news/inscriptions-languish-as-the-number-of-epigraphists-dwindles |
| "Stones like it record gifts to temples, lamps to burn forever, land and water" | corpus titles, DHARMA editions (counts above) |

Britannica's Tamil-language page returned 403 to the fetcher; re-open it before publishing if a primary
reference is wanted for "oldest living".

## Mix

- Act 1 (0-40 s): ambience leads: Tamil Nadu dawn birds, water, far-off chanting, a ghanta ding at 0.0 s, a distant
  big bell at 13.45 s under the Thanjavur vimana; drone very low.
- Title (40-47 s, Vaigai sunrise): ding, water and birds swell in the narration gaps; pad enters.
- Product (47-90 s) and pipeline (90-145 s): ambience fades out; drone + pad swell gently through Act 3; dings at 90 and 145.
- People + close (145-180 s): birds, water and chant return; drone and pad swell; ding at 172.0; distant big bell at 178.6 fading out.
- Ducking: speech-activity envelope (attack 60 ms, release 450 ms, 40 ms look-ahead) pulls ambience and music
  down 13.5 dB under speech, bells and SFX 10 dB. Transparent look-ahead limiter (max 2.3 dB, speech peaks only),
  then two-pass ffmpeg loudnorm, linear.

Measured (`check/verify.json`): integrated -14.0 LUFS, true peak -1.5 dBTP, LRA 2.7 LU, 8,640,000 samples at
48 kHz stereo; speech over bed per scene 13.1 LU minimum (worst: a1-06 13.1, a1-01 13.2, c-22 13.9, all with a ding
or the returning ambience); bell peaks -12.1 to -21.7 dBFS; no gap below -50 dB longer than 1.5 s.

## Swap into the film

```bash
# after media/video/compile.sh has written the film:
ffmpeg -y -i /Users/vivekrajaps/tamil-script/ezhuthu-video/ezhuthu-film.mp4 \
  -i /Users/vivekrajaps/tamil-script/ezhuthu-video/audio-v2/soundtrack-v2.wav \
  -map 0:v:0 -map 1:a:0 -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart \
  /Users/vivekrajaps/tamil-script/ezhuthu-video/ezhuthu-film-audio-v2.mp4
```

compile.sh (being edited by another agent at 03:21, so not touched here) already reads
`audio-v2/narration-v2.wav` and `audio-v2/captions-v2.srt` but mixes them with v1 music.wav/sfx.wav; the command
above replaces that mix with soundtrack-v2.wav. If the film burns in captions, re-render with `media/video/audio-v2/captions-v2.srt` (the Act 1, a2-08 and close
lines changed).
