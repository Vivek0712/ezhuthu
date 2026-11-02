// Render the synthetic sample photos for the upload/OCR flow (no third-party images, nothing scraped).
// Input: src/samples/sample-images.json (built by scripts/build_samples.py from DHARMA train passages).
// Output: public/samples/<id>.jpg and public/samples/ATTRIBUTION.md.
// Usage (from app/web): node scripts/render-sample-images.mjs
// Each picture is an HTML page drawn in headless Chromium: SVG fractal-noise stone, the passage set in the
// Noto fonts from @fontsource (SIL OFL), and a chipped patch wherever the edition has a gap ([?N]).
import { chromium } from '@playwright/test';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const specs = JSON.parse(readFileSync(resolve(WEB, 'src/samples/sample-images.json'), 'utf8'));
// Fonts are inlined as data URLs: a page set with setContent() cannot load file:// fonts.
const font = (pkg, file) =>
  `data:font/woff2;base64,${readFileSync(resolve(WEB, 'node_modules/@fontsource', pkg, 'files', file)).toString('base64')}`;
const FONTS = `
@font-face { font-family: 'Serif Tamil'; font-weight: 600; src: url(${font('noto-serif-tamil', 'noto-serif-tamil-tamil-600-normal.woff2')}); }
@font-face { font-family: 'Sans Tamil'; font-weight: 500; src: url(${font('noto-sans-tamil', 'noto-sans-tamil-tamil-500-normal.woff2')}); }
@font-face { font-family: 'Fraunces'; font-weight: 400; src: url(${font('fraunces', 'fraunces-latin-ext-400-normal.woff2')}); unicode-range: U+0100-024F, U+1E00-1EFF, U+0300-036F; }
@font-face { font-family: 'Fraunces'; font-weight: 400; src: url(${font('fraunces', 'fraunces-latin-400-normal.woff2')}); unicode-range: U+0000-00FF, U+2000-206F; }
`;

const esc = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');
/** Deterministic jagged outline for a chipped patch (polygon in % of its box). */
function jagged(seed) {
  let x = seed * 9301 + 49297;
  const rnd = () => ((x = (x * 9301 + 49297) % 233280) / 233280);
  const pts = [];
  for (let i = 0; i < 18; i++) {
    const a = (i / 18) * 2 * Math.PI;
    const r = 0.36 + rnd() * 0.16;
    pts.push(`${(50 + Math.cos(a) * r * 100).toFixed(1)}% ${(50 + Math.sin(a) * r * 115).toFixed(1)}%`);
  }
  return `polygon(${pts.join(',')})`;
}
/** Text with every gap marker turned into a chipped patch about N letters wide (the page style prints the marker). */
function inscribe(line, printMarkers, seed) {
  let k = 0;
  return esc(line).replace(/\[\?(\d{0,3})\]/g, (m, n) =>
    printMarkers
      ? `<span class="marker">${m}</span>`
      : `<span class="spall" style="width:${Math.max(1.2, (Number(n) || 3) * 0.62)}em;clip-path:${jagged(seed + 13 * ++k)}"></span>`,
  );
}
/** Granite or basalt: fractal noise lit from the top left, tinted. */
const stone = (seed, tint, freq = 0.9) => `
<svg class="tex" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
  <filter id="g${seed}" x="0" y="0" width="100%" height="100%">
    <feTurbulence type="fractalNoise" baseFrequency="${freq}" numOctaves="4" seed="${seed}" result="n"/>
    <feDiffuseLighting in="n" lighting-color="${tint}" surfaceScale="2.2" result="l"><feDistantLight azimuth="225" elevation="48"/></feDiffuseLighting>
    <feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="2" seed="${seed + 7}" result="m"/>
    <feColorMatrix in="m" type="matrix" values="0 0 0 0 .2  0 0 0 0 .17  0 0 0 0 .13  0 0 0 -1.2 .9" result="mottle"/>
    <feBlend in="l" in2="mottle" mode="multiply"/>
  </filter>
  <rect width="100%" height="100%" filter="url(#g${seed})"/>
</svg>`;

const BASE = `*{box-sizing:border-box;margin:0} html,body{width:100%;height:100%} body{overflow:hidden}
.tex{position:absolute;inset:0;width:100%;height:100%}
.ln{white-space:nowrap;width:max-content;max-width:none}
.spall{display:inline-block;height:1.25em;vertical-align:-0.25em;margin:0 .1em;
  background:radial-gradient(ellipse at 35% 30%, rgba(255,250,240,.38), rgba(120,105,88,.25) 45%, rgba(40,32,24,.45) 100%), rgba(176,166,150,.9);
  box-shadow: inset 3px 4px 6px rgba(0,0,0,.55), inset -2px -2px 3px rgba(255,255,255,.3)}
`;

function page(spec) {
  const seed = [...spec.id].reduce((a, c) => a + c.charCodeAt(0), 0) % 97;
  const lines = spec.lines.map((l, i) => `<div class="ln">${inscribe(l, spec.style === 'page', seed + 31 * i)}</div>`).join('');
  const rough = `<svg width="0" height="0" style="position:absolute"><filter id="rough"><feTurbulence baseFrequency=".9" numOctaves="2" seed="${seed}"/><feDisplacementMap in="SourceGraphic" scale="6"/></filter></svg>`;
  if (spec.style === 'stone' || spec.style === 'photo') {
    const photo = spec.style === 'photo';
    return {
      w: 1280,
      h: photo ? 860 : 820,
      html: `<style>${FONTS}${BASE}
body{background:${photo ? 'linear-gradient(160deg,#6f6250,#2e271f)' : '#8d8579'}}
.wall{position:absolute;inset:${photo ? '70px 60px 90px 90px' : '0'};overflow:hidden;${photo ? 'transform:perspective(1400px) rotateY(-11deg) rotateX(5deg) rotate(-1.6deg);box-shadow:0 30px 60px rgba(0,0,0,.55);border-radius:6px' : ''}}
.courses{position:absolute;inset:0;background:repeating-linear-gradient(180deg,transparent 0 158px,rgba(40,30,20,.45) 158px 162px,rgba(255,255,255,.12) 162px 163px)}
.text{position:absolute;inset:0;display:flex;flex-direction:column;justify-content:center;padding:0 70px;gap:26px;font-family:'Serif Tamil';font-weight:600;font-size:${photo ? 46 : 44}px;line-height:1.5;color:rgba(52,44,36,.78);
  text-shadow:0 -1px 1px rgba(0,0,0,.55),0 1.5px 0 rgba(255,255,255,.35);letter-spacing:.01em}
.light{position:absolute;inset:0;background:${photo ? 'radial-gradient(ellipse at 20% 10%,rgba(255,226,170,.35),transparent 55%),linear-gradient(90deg,transparent 60%,rgba(0,0,0,.35))' : 'radial-gradient(ellipse at 30% 20%,rgba(255,255,255,.12),transparent 60%),radial-gradient(ellipse at 50% 50%,transparent 55%,rgba(0,0,0,.35))'}}
</style>${rough}<div class="wall">${stone(seed, '#cfc6b6', 0.85)}<div class="text">${lines}</div><div class="light"></div></div>`,
    };
  }
  if (spec.style === 'hero') {
    return {
      w: 960,
      h: 1200,
      html: `<style>${FONTS}${BASE}
body{background:linear-gradient(180deg,#9fae8a 0%,#6d7d55 62%,#4c5a37 100%)}
.slab{position:absolute;left:150px;right:150px;top:90px;bottom:120px;border-radius:46% 46% 6% 6% / 22% 22% 3% 3%;overflow:hidden;box-shadow:12px 24px 40px rgba(0,0,0,.45)}
.text{position:absolute;inset:150px 40px 80px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;font-family:'Serif Tamil';font-weight:600;font-size:48px;line-height:1.45;color:rgba(30,28,26,.8);
  text-shadow:0 -1px 1px rgba(0,0,0,.6),0 1.5px 0 rgba(255,255,255,.22)}
.light{position:absolute;inset:0;background:radial-gradient(ellipse at 25% 15%,rgba(255,255,255,.18),transparent 55%),linear-gradient(90deg,transparent 70%,rgba(0,0,0,.3))}
.ground{position:absolute;left:0;right:0;bottom:0;height:150px;background:linear-gradient(180deg,rgba(60,50,30,0),rgba(50,42,25,.85))}
</style>${rough}<div class="slab">${stone(seed, '#a9a296', 1.1)}<div class="text">${lines}</div><div class="light"></div></div><div class="ground"></div>`,
    };
  }
  // page: a printed transliteration handout photographed on a desk
  return {
    w: 1100,
    h: 1300,
    html: `<style>${FONTS}${BASE}
body{background:#3b3027}
.sheet{position:absolute;inset:70px 90px 80px 80px;background:linear-gradient(175deg,#fbf8f1,#efe8da);transform:rotate(1.3deg);box-shadow:0 18px 40px rgba(0,0,0,.5);padding:70px 80px;font-family:'Fraunces';color:#2a241e}
h1{font-size:28px;font-weight:400;margin-bottom:6px} .sub{font-size:18px;color:#6b6155;margin-bottom:34px}
.ln{font-size:31px;line-height:1.62;white-space:pre} .marker{font-weight:400}
.foot{position:absolute;left:80px;right:80px;bottom:48px;font-size:15px;color:#7a6f62}
</style><div class="sheet"><h1>${esc(spec.title_en)}</h1><div class="sub">${esc(spec.inscription_id)} · ISO-15919</div>${lines}<div class="foot">Text: DHARMA, CC BY-SA 4.0</div></div>`,
  };
}

mkdirSync(resolve(WEB, 'public/samples'), { recursive: true });
const browser = await chromium.launch();
for (const spec of specs) {
  const { w, h, html } = page(spec);
  const p = await browser.newPage({ viewport: { width: w, height: h } });
  await p.setContent(`<!doctype html><meta charset="utf-8">${html}`, { waitUntil: 'load' });
  await p.evaluate(() => document.fonts.ready);
  // One edition line per picture line: shrink the type until the longest line fits (so expected_text lines match).
  await p.evaluate(() => {
    const box = document.querySelector('.text, .sheet');
    if (!box) return;
    let size = parseFloat(getComputedStyle(box.querySelector('.ln')).fontSize);
    const fits = () => [...box.querySelectorAll('.ln')].every((l) => l.getBoundingClientRect().right <= box.getBoundingClientRect().right - 40);
    while (!fits() && size > 14) {
      size -= 1;
      box.querySelectorAll('.ln').forEach((l) => (l.style.fontSize = `${size}px`));
    }
  });
  await p.screenshot({ path: resolve(WEB, 'public', spec.file), type: 'jpeg', quality: 80 });
  await p.close();
  console.log(`wrote public/${spec.file}`);
}
await browser.close();

const rows = specs
  .map((s) => `| \`${s.file.split('/').pop()}\` | ${s.title_en} | [${s.inscription_id}](${s.dharma_url}) | ${s.licence} |`)
  .join('\n');
writeFileSync(
  resolve(WEB, 'public/samples/ATTRIBUTION.md'),
  `# Sample images: attribution

These pictures are **synthetic renders made by the Ezhuthu team**, not photographs of real stones. They exist so
that people can try the upload and OCR flow without a photo of their own. Generated by
\`app/web/scripts/render-sample-images.mjs\` from \`app/web/src/samples/sample-images.json\`
(\`scripts/build_samples.py\`). No third-party photograph or scraped image is used.

- **Text:** passages from DHARMA editions (train split of the Ezhuthu benchmark), licensed
  [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). The renders are adaptations of that text and are
  shared under the same licence. The Tamil-script pictures show a modern Tamil transcription derived from the
  edition's ISO-15919 text, not the original letterforms on the stone.
- **Fonts:** Noto Serif Tamil and Fraunces (SIL Open Font License 1.1), via @fontsource.
- **Stone, paper and damage:** procedural (SVG fractal noise). A chipped patch marks each gap \`[?N]\` of the edition;
  its width is only roughly N letters.

| File | Picture | Source edition | Licence |
| --- | --- | --- | --- |
${rows}
`,
);
console.log('wrote public/samples/ATTRIBUTION.md');
