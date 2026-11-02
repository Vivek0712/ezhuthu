# Ezhuthu film, audio v2: sound credits

Every third-party sound below was downloaded from Wikimedia Commons on 2026-11-03 into
`ezhuthu-video/audio-v2/raw/` (a fresh directory), checked with ffprobe, and its SHA-1 matched against the
Commons `imageinfo` hash. Licences were read from the file's `extmetadata` (`LicenseShortName`); only CC0,
public domain and CC BY were accepted (no CC BY-SA, no NC, no film or Carnatic recordings, no BBC).
Machine-readable record: `ezhuthu-video/audio-v2/check/sources.json`.

**No conch (shankha) is used anywhere** (user correction 2026-11-03). The temple "ding" is a brass ghanta struck
once with a mallet.

| Layer in the mix | Title (Commons file) | Author | Licence | URL | Edits |
| --- | --- | --- | --- | --- | --- |
| Temple hand-bell dings (0.0, 40.0, 90.0, 145.0, 172.0 s) | 274316 the-very-real-horst ghanta-leather-mallet-2015-05-16.wav | the_very_Real_Horst (via Freesound 274316) | CC0 1.0 | https://commons.wikimedia.org/wiki/File:274316_the-very-real-horst_ghanta-leather-mallet-2015-05-16.wav | four single strikes cut (1.72, 7.82, 24.82, 33.22 s), 300 Hz high-pass (hum, mallet thump), pitched from 1014 Hz to C#6 (~1109 Hz) to sit in the drone's key, faded tails, low level, ducked 10 dB under speech |
| Dawn birds (Act 1, title, return at the close) | Birds Perungalathur Reserved Forest.wav (Tamil Nadu) | Mk170101 | CC BY 4.0 | https://commons.wikimedia.org/wiki/File:Birds_Perungalathur_Reserved_Forest.wav | 450 Hz to 5.2 kHz band-pass (removes rumble and the 6-8 kHz insect band), looped with crossfades, level envelope, ducked |
| Water, as the Vaigai at sunrise (Act 1, title scene, close) | 433589 jackthemurray stream-river-water-up-close.wav | jackthemurray (via Freesound 433589) | CC0 1.0 | https://commons.wikimedia.org/wiki/File:433589_jackthemurray_stream-river-water-up-close.wav | 120 Hz to 3.5 kHz band-pass (more distant, less hiss), looped with crossfades, level envelope, ducked |
| Distant temple chanting, courtyard (Act 1, close) | दिशांव्रतम् Disham Vratam.ogg (Samaveda recitation) | Seetharaman G.K. | CC0 1.0 | https://commons.wikimedia.org/wiki/File:%E0%A4%A6%E0%A4%BF%E0%A4%B6%E0%A4%BE%E0%A4%82%E0%A4%B5%E0%A5%8D%E0%A4%B0%E0%A4%A4%E0%A4%AE%E0%A5%8D_Disham_Vratam.ogg | 180 s excerpt from 60 s in, 220 Hz to 2.4 kHz band-pass, 75% synthetic-room reverb (far side of a stone courtyard), very low, ducked |

Attribution line for the end card / description (CC BY 4.0 requires it):
"Dawn birds: 'Birds Perungalathur Reserved Forest' by Mk170101, CC BY 4.0, via Wikimedia Commons (filtered, looped)."
CC0 sources need no attribution; they are credited anyway: ghanta by the_very_Real_Horst, stream by jackthemurray,
Samaveda chant by Seetharaman G.K.

## Original (synthesized for this film, no samples)

| Layer | How | Source |
| --- | --- | --- |
| Distant big temple bell (13.45 s, 178.6 s) | inharmonic bronze partials on C#3 (ratios 0.5 to 4.1), slow beating, long hum, low-passed + reverb | `tools/build_v2.py` `big_bell()` |
| Tanpura-like drone on C# (whole film, swells in Act 3 and the close) | additive synthesis, Pa-Sa-Sa-low Sa plucks every 1.15 s, jawari bloom on upper partials | `tools/build_v2.py` `tanpura()` |
| Soft melodic pad (from the title, swells in Act 3 and the close) | sine-stack tones in Mohanam (C# D# F G# A#), sustained Sa-Pa bed + an original slow line | `tools/build_v2.py` `pad()` |
| Room reverb | synthetic exponentially decaying noise impulse response | `tools/build_v2.py` `reverb_ir()` |
| v1 SFX stem (chisel tap 2.4 s, chimes 47.8-52 s, stone settles 74.5 s) | reused read-only from `ezhuthu-video/audio/sfx.wav` (synthesized by `audio-tools/synth_music.py`) | v1 |
| Narration | Amazon Polly, voice Arjun (en-IN, generative engine) | `tools/synth_v2.py`, `narration-v2.json` |

## Considered and rejected

- Ghonto (holophonic).flac (Odia ghanta, Subhashish Panigrahi): CC BY-SA 4.0. Rejected: share-alike.
- Dawn calls 20220311 sakleshpur.ogg (Shyamal): CC BY-SA 4.0. Rejected: share-alike (the Tamil Nadu CC BY recording was used).
- सुब्रह्मण्या आह्वानम् Subrahmanya chant.ogg: CC BY-SA 4.0. Rejected: share-alike.
- Thakil & Nadaswaram during temple Deeparadhana.ogg, Chenda melam at temple 02.ogg (CC BY 4.0): temple music, not ambience; the brief rules out music recordings.
- Aarti Puja chants (CC0): North Indian sung aarti, not South Indian temple ambience.
- Church/cathedral bells (CC BY-SA, European): wrong place.
- No temple crowd murmur under a usable licence was found on Commons; the soft chant carries the human presence.
  Freesound was not used (full-quality downloads need a login).
