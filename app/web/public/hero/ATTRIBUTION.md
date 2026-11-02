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
identify which published inscription it is**, so the hero shows no edition text and no error rate. The reading in the
hero is Ezhuthu's own (Reader: Sonnet 4.6, then Opus 4.6 on "read again"), at confidence 0.20, and is labelled as
unverified. How it was produced: `scripts/hero_read.py`, `scripts/hero_build.py` and
`app/web/src/hero/hero-reading.json`.

The letter boxes drawn over the photo were annotated by hand (`design/hero/boxes.json`,
checked against `design/hero/boxes-overlay.png`). They mark carved letters, not the reader's output letters: the
reader returns text line by line, not letter positions.
