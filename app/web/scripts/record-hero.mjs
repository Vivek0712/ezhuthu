// Record one full cycle of the home hero animation for the README: docs/media/hero-evolution{,-dark}.webm, plus a
// small still (docs/media/hero-evolution-poster.jpg: the reduced-motion frame, all five stages labelled) that the
// README shows inline and links to the video. No GIF: it was ~1 MB for what the WebM does in ~130 kB.
// Needs the mock preview running (npm run build:mock && npm run preview:mock) and ffmpeg on PATH.
// Usage (from app/web): node scripts/record-hero.mjs [light|dark] [--poster-only]
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = resolve(WEB, '../../docs/media');
const theme = process.argv.includes('dark') ? 'dark' : 'light';
const suffix = theme === 'dark' ? '-dark' : '';
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
if (theme === 'light') {
  const still = await browser.newContext({ viewport: { width: 1280, height: 760 }, reducedMotion: 'reduce', deviceScaleFactor: 1 });
  await still.addInitScript(() => window.localStorage.setItem('ezhuthu.lang', 'en'));
  const p = await still.newPage();
  await p.goto('http://localhost:4173/');
  await p.evaluate(() => document.fonts.ready);
  const poster = join(OUT, 'hero-evolution-poster.jpg');
  await p.getByTestId('evolution-hero').locator('.evo-stage').screenshot({ path: poster, type: 'jpeg', quality: 82 });
  await still.close();
  console.log(`wrote ${poster}`);
}
if (process.argv.includes('--poster-only')) {
  await browser.close();
  process.exit(0);
}
const tmp = mkdtempSync(join(tmpdir(), 'ez-hero-'));
const ctx = await browser.newContext({
  viewport: { width: 1280, height: 760 },
  colorScheme: theme,
  recordVideo: { dir: tmp, size: { width: 1280, height: 760 } },
});
await ctx.addInitScript(() => window.localStorage.setItem('ezhuthu.lang', 'en'));
const page = await ctx.newPage();
const t0 = Date.now();
await page.goto('http://localhost:4173/');
const hero = page.getByTestId('evolution-hero');
await hero.waitFor();
await page.evaluate(() => document.fonts.ready);
const box = (await hero.locator('.evo-stage').boundingBox());
const start = (Date.now() - t0) / 1000;
await page.waitForTimeout(14_400); // one 14 s cycle (5 stages x 2.8 s) plus the word drawing at the start
await ctx.close();
await browser.close();

const raw = join(tmp, readdirSync(tmp).find((f) => f.endsWith('.webm')));
const crop = `crop=${Math.round(box.width)}:${Math.round(box.height)}:${Math.round(box.x)}:${Math.round(box.y)}`;
const ss = Math.max(0, start - 0.2).toFixed(2);
const webm = join(OUT, `hero-evolution${suffix}.webm`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', ss, '-t', '14', '-i', raw, '-vf', crop, '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '36', '-an', webm]);
rmSync(tmp, { recursive: true, force: true });
console.log(`wrote ${webm}`);
