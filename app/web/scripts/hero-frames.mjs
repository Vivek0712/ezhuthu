// Frames of one stone-hero cycle for review: screenshots of the hero every `step` ms, plus a contact sheet.
//   node scripts/hero-frames.mjs [url] [outDir] [--phone] [--dark] [--lang ta] [--step 1000]
// Needs a running app (npm run build:mock && npm run preview:mock). Tile them with scripts/hero_contact_sheet.py.
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const args = process.argv.slice(2);
const flag = (n) => args.includes(n);
const opt = (n, d) => (args.includes(n) ? args[args.indexOf(n) + 1] : d);
const pos = args.filter((a, i) => !a.startsWith('--') && !(i > 0 && args[i - 1].startsWith('--') && !['--phone', '--dark'].includes(args[i - 1])));
const URL = pos[0] ?? 'http://localhost:4173/';
const OUT = pos[1] ?? 'frames';
const phone = flag('--phone');
const step = Number(opt('--step', '1000'));
const lang = opt('--lang', 'en');
mkdirSync(OUT, { recursive: true });
const viewport = phone ? { width: 375, height: 740 } : { width: 1440, height: 900 };
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport, colorScheme: flag('--dark') ? 'dark' : 'light', deviceScaleFactor: 1 });
await ctx.addInitScript((l) => window.localStorage.setItem('ezhuthu.lang.v2', l), lang);
const page = await ctx.newPage();
await page.goto(URL);
await page.getByTestId('stone-hero').waitFor();
await page.evaluate(() => document.fonts.ready);
await page.addStyleTag({ content: '.mock-banner{display:none!important}' });
await page.waitForTimeout(800);
const target = phone ? null : page.getByTestId('stone-hero');
if (target) await target.scrollIntoViewIfNeeded();
else
  await page.evaluate(() => {
    const st = document.querySelector('.sh-stage').getBoundingClientRect().top + window.scrollY;
    const bar = document.querySelector('.topbar')?.getBoundingClientRect().height ?? 0;
    window.scrollTo(0, st - bar - 8);
  });
await page.getByTestId('stone-replay').evaluate((b) => b.click());
const cycle = await page.evaluate(() => {
  const a = document.querySelector('.sh-stage').getAnimations()[0];
  return a ? a.effect.getTiming().duration : 20000;
});
const n = Math.ceil(cycle / step);
const files = [];
for (let k = 0; k <= n; k++) {
  // Seek every animation to t = k*step (deterministic frames, no timing jitter).
  await page.evaluate((t) => {
    const hero = document.querySelector('.stone-hero');
    for (const a of document.getAnimations()) {
      const el = a.effect?.target;
      if (!(el instanceof Element) || !hero.contains(el)) continue;
      a.pause();
      const d = a.effect.getTiming();
      a.currentTime = Math.min(t, (d.delay ?? 0) + Number(d.duration) - 1);
    }
  }, Math.min(k * step, cycle - 1));
  const f = join(OUT, `f${String(k).padStart(3, '0')}.png`);
  if (target) await target.screenshot({ path: f });
  else await page.screenshot({ path: f });
  files.push(f);
}
console.log(`cycle ${cycle} ms, ${files.length} frames in ${OUT}`);
await browser.close();
