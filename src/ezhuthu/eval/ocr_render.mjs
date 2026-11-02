// Render synthetic "inscription photos" for the OCR evaluation (python -m ezhuthu.eval.ocr synth).
//
//   node src/ezhuthu/eval/ocr_render.mjs <manifest.json> <out_dir>
//
// Chromium does the text shaping (Tamil vowel-sign reordering, Brahmi/Grantha conjuncts), with the Noto fonts the
// web app already ships (@fontsource, SIL OFL 1.1). Each plate is a few lines on a procedural stone or paper
// texture (SVG feTurbulence, no photographs), carved-letter shading, rotation, perspective, blur and weathering
// patches by degradation level. Python adds sensor noise and JPEG compression afterwards. Deterministic per seed.
// Playwright comes from app/web/node_modules (run `npm ci` there first).
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, '..', '..', '..');
const web = path.join(root, 'app', 'web');
const require = createRequire(path.join(web, 'package.json'));
const { chromium } = require('@playwright/test');

const font = (pkg, file) => pathToFileURL(path.join(web, 'node_modules', '@fontsource', pkg, 'files', file)).href;
const FONTS = {
  'tamil-sans': { family: 'EzTamilSans', url: font('noto-sans-tamil', 'noto-sans-tamil-tamil-600-normal.woff2') },
  'tamil-serif': { family: 'EzTamilSerif', url: font('noto-serif-tamil', 'noto-serif-tamil-tamil-500-normal.woff2') },
  brahmi: { family: 'EzBrahmi', url: font('noto-sans-brahmi', 'noto-sans-brahmi-brahmi-400-normal.woff2') },
  grantha: { family: 'EzGrantha', url: font('noto-sans-grantha', 'noto-sans-grantha-grantha-400-normal.woff2') },
};

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 4294967296);
}

const LEVELS = {
  clean: { paper: true, rot: 0, persp: 0, blur: 0, patches: 0, freq: 0.9, contrast: 1 },
  photo: { paper: false, rot: 2.5, persp: 8, blur: 0.6, patches: 2, freq: 0.012, contrast: 0.75 },
  weathered: { paper: false, rot: 4, persp: 16, blur: 1.3, patches: 6, freq: 0.02, contrast: 0.5 },
};

function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function plateHtml(item) {
  const L = LEVELS[item.level];
  const r = rng(item.seed);
  const f = FONTS[item.font];
  const rot = (r() * 2 - 1) * L.rot;
  const ry = (r() * 2 - 1) * L.persp;
  const rx = (r() * 2 - 1) * L.persp * 0.5;
  const stone = `hsl(${30 + r() * 15}, ${10 + r() * 12}%, ${55 + r() * 12}%)`;
  const ink = L.paper ? '#1d1a17' : `hsl(30, 12%, ${Math.round(48 - 30 * L.contrast)}%)`;
  // Gap markers [?N] are drawn as chipped-away stretches (blank, rougher texture), about N letters wide.
  const lines = item.lines
    .map((ln) =>
      ln
        .split(/(\[\?\d*\])/)
        .map((part) => {
          const m = /^\[\?(\d*)\]$/.exec(part);
          if (!m) return `<span>${esc(part)}</span>`;
          const n = Math.max(1, Math.min(12, Number(m[1] || 4)));
          return `<span class="chip" style="width:${n * 0.9}em"></span>`;
        })
        .join(''),
    )
    .map((html) => `<div class="ln">${html}</div>`)
    .join('');
  const patches = Array.from({ length: L.patches }, () => {
    const w = 60 + r() * 160;
    return `<div class="patch" style="left:${r() * 90}%;top:${r() * 85}%;width:${w}px;height:${w * (0.4 + r() * 0.5)}px"></div>`;
  }).join('');
  return `<!doctype html><html><head><meta charset="utf-8"><style>
  @font-face { font-family: ${f.family}; src: url('${f.url}') format('woff2'); }
  html,body { margin:0; background:#3b3632; }
  #stage { width:1280px; height:${200 + item.lines.length * 110}px; display:flex; align-items:center; justify-content:center; perspective:1400px; }
  #plate { position:relative; padding:40px 56px; background:${L.paper ? '#f4efe4' : stone}; transform: rotateZ(${rot}deg) rotateY(${ry}deg) rotateX(${rx}deg);
           filter: blur(${L.blur}px); box-shadow: 0 10px 40px rgba(0,0,0,.45); overflow:hidden; border-radius:${L.paper ? 2 : 14}px; }
  #plate::before { content:''; position:absolute; inset:0; background-image:url("data:image/svg+xml;utf8,${encodeURIComponent(
    `<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='700'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='${L.freq}' numOctaves='4' seed='${item.seed % 997}'/><feColorMatrix values='0 0 0 0 0.5  0 0 0 0 0.45  0 0 0 0 0.4  0 0 0 ${L.paper ? 0.08 : 0.55} 0'/></filter><rect width='100%' height='100%' filter='url(#n)'/></svg>`,
  )}"); mix-blend-mode:multiply; pointer-events:none; }
  .ln { position:relative; font-family:${f.family}; font-size:${item.font === 'brahmi' || item.font === 'grantha' ? 50 : 44}px; line-height:1.75; color:${ink}; white-space:pre;
        text-shadow:${L.paper ? 'none' : '1px 1px 0 rgba(255,255,255,.35), -1px -1px 1px rgba(0,0,0,.45)'}; letter-spacing:.02em; }
  .chip { display:inline-block; height:.9em; vertical-align:middle; background:rgba(255,255,255,${L.paper ? 0 : 0.18}); border-radius:40% 55% 45% 60%;
          box-shadow: inset 2px 2px 6px rgba(0,0,0,${L.paper ? 0 : 0.35}); }
  .patch { position:absolute; border-radius:50% 40% 60% 45%; background:${stone}; opacity:.78; filter:blur(6px); }
  </style></head><body><div id="stage"><div id="plate">${lines}${patches}</div></div></body></html>`;
}

const [manifestPath, outDir] = process.argv.slice(2);
if (!manifestPath || !outDir) {
  console.error('usage: node ocr_render.mjs <manifest.json> <out_dir>');
  process.exit(2);
}
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'));
mkdirSync(outDir, { recursive: true });
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
for (const item of manifest.items) {
  await page.setContent(plateHtml(item), { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const stage = await page.$('#stage');
  await stage.screenshot({ path: path.join(outDir, `${item.id}.png`) });
}
await browser.close();
console.log(`rendered ${manifest.items.length} plates to ${outDir}`);
