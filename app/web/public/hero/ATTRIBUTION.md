# Home hero photograph: attribution

The home hero animates **one real photograph**. It is shown in the app with a small credit line under the hero.

| | |
| --- | --- |
| **Photograph** | "Brihadishwara Temple, Dedicated to Shiva, built by Rajaraja I, completed in 1010, Thanjavur (38)" |
| **Author** | [Richard Mortel](https://www.flickr.com/people/43714545@N06) (from Riyadh, Saudi Arabia) |
| **Licence** | [Creative Commons Attribution 2.0 Generic (CC BY 2.0)](https://creativecommons.org/licenses/by/2.0/) |
| **Source** | [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:1010_CE_Brihadishwara_Shiva_Temple,_inscription,_built_by_Rajaraja_I,_Thanjavur_Tamil_Nadu_India.jpg), from [Flickr](https://www.flickr.com/photos/prof_richard/36826608993/), taken 1 September 2017 |
| **Changes** | Cropped to four lines of the inscription, resized to 480, 800 and 1568 px wide and re-encoded as AVIF, WebP and JPEG. EXIF and other metadata removed. No retouching. |
| **Files** | `thanjavur-{480,800,1568}.{avif,webp,jpg}`; the crop they are made from is `design/hero/thanjavur-crop.jpg` |

The stone is a Chola-period Tamil inscription on the Brihadisvara (Peruvudaiyar) temple in Thanjavur. **We could not
identify which published inscription it is** (it is not in the DHARMA split; two searches of Wikimedia Commons for an
openly licensed photo of a DHARMA inscription, on 2 November 2026, found none whose text could be matched to an
edition), so the hero shows no edition text and no match rate, and the words, phrase and meaning are credited in the
app as **"Meaning by Ezhuthu"**: they are the output of Ezhuthu's Interpreter, not a published translation.

The hero shows Ezhuthu's own letter-by-letter reading: for each box, the modern Tamil letter the Reader (Opus 4.6)
named and its own probability, and, for the one letter under 0.5, the Restorer's best fill and the Strands Decider's
decision (abstain); then the Interpreter's words (each with the letters it is made of), the phrase in today's Tamil and
its meaning in English and Tamil, with its own probability. How it was produced: `scripts/hero_read.py` (`glyphs`,
`restore --from-glyphs`, `interpret`),
`scripts/hero_build.py` and `app/web/src/hero/hero-reading.json`.

The letter boxes drawn over the photo were annotated by hand (`design/hero/boxes.json`, checked against
`design/hero/boxes-overlay.jpg`), one box per carved letter group; the Reader was shown the boxes numbered, so each
matched letter belongs to a box.
