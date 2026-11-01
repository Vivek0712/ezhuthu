# Fonts and licences

Every typeface is open-licence and comes from Google Fonts or the Noto project. No commercial or system-only fonts are used.

| Role | Family | Weights / axes used | Licence | Source |
| --- | --- | --- | --- | --- |
| Display, Tamil (headings, wordmark, mark) | **Noto Serif Tamil** | 500, 600, 700, 800, 900 (variable wght and wdth axes) | SIL Open Font License 1.1 | [fonts.google.com/noto/specimen/Noto+Serif+Tamil](https://fonts.google.com/noto/specimen/Noto+Serif+Tamil) · [notofonts/tamil](https://github.com/notofonts/tamil) |
| Body, Tamil (reading, UI in Tamil) | **Noto Sans Tamil** | 400, 500, 600, 700 | SIL OFL 1.1 | [fonts.google.com/noto/specimen/Noto+Sans+Tamil](https://fonts.google.com/noto/specimen/Noto+Sans+Tamil) |
| Era script: Tamil-Brahmi | **Noto Sans Brahmi** | 400 | SIL OFL 1.1 | [fonts.google.com/noto/specimen/Noto+Sans+Brahmi](https://fonts.google.com/noto/specimen/Noto+Sans+Brahmi) · [notofonts/brahmi](https://github.com/notofonts/brahmi) |
| Era script: Grantha (Pallava stage) | **Noto Sans Grantha** | 400 | SIL OFL 1.1 | [fonts.google.com/noto/specimen/Noto+Sans+Grantha](https://fonts.google.com/noto/specimen/Noto+Sans+Grantha) · [notofonts/grantha](https://github.com/notofonts/grantha) |
| Display, Latin (the one distinctive face) | **Fraunces** | 300–700, opsz 9–144, SOFT 0–100, WONK 0–1, italic | SIL OFL 1.1 | [fonts.google.com/specimen/Fraunces](https://fonts.google.com/specimen/Fraunces) · [undercasetype/Fraunces](https://github.com/undercasetype/Fraunces) |
| UI, Latin | **Instrument Sans** | 400–700 | SIL OFL 1.1 | [fonts.google.com/specimen/Instrument+Sans](https://fonts.google.com/specimen/Instrument+Sans) |
| Code, IDs, EpiDoc snippets (`--ez-font-mono`) | **JetBrains Mono** | 400, 500 | SIL OFL 1.1 | [fonts.google.com/specimen/JetBrains+Mono](https://fonts.google.com/specimen/JetBrains+Mono) · [JetBrains/JetBrainsMono](https://github.com/JetBrains/JetBrainsMono) |

Vatteluttu has no Unicode encoding and no font. Its glyphs are drawn as SVG in `design/glyphs/` (see `REFERENCES.md`).

## Why these

- **Noto Serif Tamil** has high contrast and a chiselled terminal that looks carved at display sizes, and it ships weights up to 900, which the mark needs. **Noto Sans Tamil** is the most legible screen Tamil at 16–18 px.
- **Fraunces** is an "Old Style soft" serif with an optical-size axis. At opsz 144 with SOFT 0 it has the contrast of letters cut in stone. Its italic carries emphasis ("*in Tamil.*"). Note: the app already ships Fraunces and Instrument Sans through `@fontsource`, so adoption costs nothing.
- One Latin display face only. Tamil carries the personality.

## Pairing rules

| Situation | Tamil | Latin |
| --- | --- | --- |
| Page title | Noto Serif Tamil 700 | Fraunces 500 (opsz auto) |
| Section heading | Noto Serif Tamil 600 | Fraunces 500 |
| Body | Noto Sans Tamil 400 | Instrument Sans 400 |
| Buttons, chips, labels | Noto Sans Tamil 600 | Instrument Sans 600 |
| ISO-15919 transliteration | n/a | Fraunces italic 400, `text-muted` |
| Numbers in results | n/a | Fraunces 600, tabular (`font-variant-numeric: tabular-nums`) |
| Era glyphs | Noto Sans Brahmi / Noto Sans Grantha / Noto Serif Tamil (Chola) / Noto Sans Tamil (modern) / drawn SVG (Vatteluttu) | n/a |

## Type scale and Tamil line heights

Major third (×1.25) on a 16 px root. Tamil needs more leading because of its tall vowel signs (ி ீ ு ூ ை) and stacked conjuncts, so each step has two line heights (from `tokens.json`):

| Token | Size | Latin line height | Tamil line height |
| --- | --- | --- | --- |
| `xs` | 0.8rem | 1.5 | 1.7 |
| `sm` | 0.9rem | 1.5 | 1.7 |
| `md` (body) | 1.0625rem (17 px) | 1.6 | 1.8 |
| `lg` | 1.25rem | 1.5 | 1.7 |
| `xl` | 1.5625rem | 1.3 | 1.5 |
| `2xl` | 1.95rem | 1.2 | 1.45 |
| `3xl` | 2.44rem | 1.12 | 1.4 |
| `4xl` | 3.05rem | 1.05 | 1.35 |
| `glyph` (era glyph in a card) | 4.5rem | 1 | 1.1 |

Further Tamil rules:

- When a heading is in Tamil, drop it one step (Tamil glyphs are wider and taller at the same em). Example: a `4xl` Latin h1 becomes `3xl` in Tamil.
- Measure: 60ch for Tamil, 68ch for Latin.
- Never letter-space Tamil. Never use `text-transform` on Tamil (it is a no-op, and fake small caps break).
- Do not use `font-synthesis`. Load the real weights.

## Fallback stacks (from `tokens.css`)

```css
--ez-font-display-ta:    'Fraunces', 'Noto Serif Tamil', 'Tamil Sangam MN', 'Latha', Georgia, serif;
--ez-font-body-ta:       'Instrument Sans', 'Noto Sans Tamil', 'Tamil MN', 'Latha', system-ui, sans-serif;
--ez-font-display-latin: 'Fraunces', 'Noto Serif Tamil', Georgia, 'Times New Roman', serif;
--ez-font-body:          'Instrument Sans', 'Noto Sans Tamil', system-ui, -apple-system, 'Segoe UI', sans-serif;
--ez-font-brahmi:        'Noto Sans Brahmi', sans-serif;
--ez-font-grantha:       'Noto Sans Grantha', 'Noto Sans Tamil', sans-serif;
--ez-font-mono:          'JetBrains Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace;
```

The Tamil-first stacks list the Latin brand face first on purpose. Fraunces and Instrument Sans have no Tamil
glyphs, so Tamil characters fall through to Noto, while Latin words, digits and punctuation inside a Tamil run
stay in the brand faces instead of picking up Noto's Latin.

## Licence obligations

The SIL OFL 1.1 lets you use, embed and bundle these fonts, including in logos. The logo SVGs embed glyph outlines of Noto Serif Tamil and Fraunces as paths, which is permitted. You must not sell the fonts on their own, and a modified font must not keep the Reserved Font Name. We do not modify or redistribute the font files. `design/tools/fetch_fonts.py` downloads them at build time into `~/.cache/ezhuthu-design-fonts` (outside the repo).
