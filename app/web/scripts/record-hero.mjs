// Record one full cycle of the home hero animation for the README: docs/media/hero-evolution.{webm,gif}.
// Needs the mock preview running (npm run build:mock && npm run preview:mock) and ffmpeg on PATH.
// Usage (from app/web): node scripts/record-hero.mjs [light|dark]
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = resolve(WEB, '../../docs/media');
const theme = process.argv[2] === 'dark' ? 'dark' : 'light';
const suffix = theme === 'dark' ? '-dark' : '';
const tmp = mkdtempSync(join(tmpdir(), 'ez-hero-'));
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
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
const gif = join(OUT, `hero-evolution${suffix}.gif`);
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', ss, '-t', '14', '-i', raw, '-vf', crop, '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '36', '-an', webm]);
// The GIF (README fallback where video does not play) is made for the light theme only, to keep it small.
if (theme === 'light') execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', ss, '-t', '14', '-i', raw, '-vf',
  `${crop},fps=10,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none:diff_mode=rectangle`, gif]);
rmSync(tmp, { recursive: true, force: true });
console.log(`wrote ${webm}${theme === 'light' ? `\nwrote ${gif}` : ''}`);
