// Rasterise design SVGs / HTML pages to PNG with headless Chromium (Playwright 1.56, chromium-headless-shell).
// Usage: node design/tools/render.mjs [filter]     reads design/tools/renders.json
// Each entry: { "src": "brand/logo/mark-color.svg", "out": "renders/x.png", "w": 512, "h": 512,
//               "bg": "#F4EEE2" | null, "page": false, "scale": 1, "full": false }
import { chromium } from 'playwright';
import { readFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const DESIGN = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const jobs = JSON.parse(readFileSync(resolve(DESIGN, 'tools/renders.json'), 'utf8'));
const filter = process.argv[2];
const browser = await chromium.launch();
let n = 0;
for (const j of jobs) {
  if (filter && !j.src.includes(filter) && !j.out.includes(filter)) continue;
  const scale = j.scale ?? 1;
  const page = await browser.newPage({ viewport: { width: j.w, height: j.h }, deviceScaleFactor: scale });
  const src = pathToFileURL(resolve(DESIGN, j.src)).href;
  if (j.page) {
    await page.goto(src + (j.hash ?? ''));
    if (j.theme) await page.evaluate((t) => document.documentElement.setAttribute('data-theme', t), j.theme);
  } else {
    // Open the SVG document itself, size it to the viewport and paint the optional backdrop.
    await page.goto(src);
    await page.evaluate(({ w, h, bg }) => {
      const s = document.documentElement;
      s.setAttribute('width', w); s.setAttribute('height', h);
      s.setAttribute('preserveAspectRatio', 'xMidYMid meet');
      s.style.background = bg || 'transparent';
      s.style.display = 'block';
    }, { w: j.w, h: j.h, bg: j.bg ?? null });
  }
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(j.page ? 900 : 150);
  const out = resolve(DESIGN, j.out);
  mkdirSync(dirname(out), { recursive: true });
  await page.screenshot({ path: out, fullPage: !!j.full, omitBackground: !j.bg && !j.page });
  await page.close();
  n++;
}
await browser.close();
console.log(`rendered ${n} file(s) with Chromium ${browser.version()}`);
