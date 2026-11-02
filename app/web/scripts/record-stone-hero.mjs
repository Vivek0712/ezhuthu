// Record one full cycle of the home stone hero (StoneHero.tsx) for the README and the PR:
//   design/brand/banners/hero-stone.webm        light theme, 1440 x 900 desktop, one cycle (length read from the page)
//   design/brand/banners/hero-stone-dark.webm   dark theme
//   design/brand/banners/hero-stone-phone.webm  375 x 740 phone, Tamil, scrolled to the stone
//   design/brand/banners/hero-stone.gif         the light recording as a GIF (420 px, 6 fps) for places without video
//   design/brand/banners/hero-stone-poster.png  the composed final frame (what reduced-motion visitors see)
// Needs the mock preview running (npm run build:mock && npm run preview:mock) and ffmpeg on PATH.
// Usage (from app/web): node scripts/record-stone-hero.mjs
import { chromium } from '@playwright/test';
import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readdirSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const OUT = resolve(WEB, '../../design/brand/banners');
const URL = 'http://localhost:4173/';
mkdirSync(OUT, { recursive: true });
const browser = await chromium.launch();

// Poster: the static composed frame, English, light.
{
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce', deviceScaleFactor: 1 });
  await ctx.addInitScript(() => window.localStorage.setItem('ezhuthu.lang', 'en'));
  const p = await ctx.newPage();
  await p.goto(URL);
  await p.getByTestId('stone-hero').waitFor();
  await p.evaluate(() => document.fonts.ready);
  await p.addStyleTag({ content: '.mock-banner{display:none!important}' });
  await p.waitForTimeout(500);
  const poster = join(OUT, 'hero-stone-poster.png');
  await p.getByTestId('stone-hero').locator('.sh-stage').screenshot({ path: poster });
  await ctx.close();
  console.log(`wrote ${poster}`);
}

async function record({ name, theme = 'light', lang = 'en', viewport = { width: 1440, height: 900 }, fullScreen = false }) {
  const tmp = mkdtempSync(join(tmpdir(), 'ez-stone-'));
  const ctx = await browser.newContext({ viewport, colorScheme: theme, recordVideo: { dir: tmp, size: viewport } });
  await ctx.addInitScript((l) => window.localStorage.setItem('ezhuthu.lang', l), lang);
  const page = await ctx.newPage();
  const t0 = Date.now();
  await page.goto(URL);
  const hero = page.getByTestId('stone-hero');
  await hero.waitFor();
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200); // the page entrance and fonts settle
  // Hide the demo-mode banner so the clip shows the hero as visitors of the live site see it.
  await page.addStyleTag({ content: '.mock-banner{display:none!important}' });
  if (fullScreen) {
    // Phone: put the top of the stage just under the sticky header, so the stone, the pipeline and the reading share
    // the screen; replay from script (a real click would scroll to the button).
    await page.evaluate(() => {
      const st = document.querySelector('.sh-stage').getBoundingClientRect().top + window.scrollY;
      const bar = document.querySelector('.topbar').getBoundingClientRect().height;
      window.scrollTo(0, st - bar - 8);
    });
    await page.waitForTimeout(300);
  } else await hero.scrollIntoViewIfNeeded();
  const box = fullScreen ? { x: 0, y: 0, ...viewport } : await hero.locator('.sh-stage').boundingBox();
  const start = (Date.now() - t0) / 1000;
  await page.getByTestId('stone-replay').evaluate((b) => b.click());
  const cycleMs = await page.evaluate(() => Number(document.querySelector('.sh-stage').getAnimations()[0]?.effect.getTiming().duration ?? 20000));
  // One cycle, ending on the held final frame (before the 0.7 s fade and 0.3 s rest).
  const CLIP_S = (cycleMs - 1300) / 1000;
  await page.waitForTimeout(CLIP_S * 1000 + 400);
  await ctx.close();
  const raw = join(tmp, readdirSync(tmp).find((f) => f.endsWith('.webm')));
  const even = (n) => Math.floor(n / 2) * 2;
  const crop = `crop=${even(box.width)}:${even(box.height)}:${Math.round(box.x)}:${Math.round(box.y)}`;
  const webm = join(OUT, `${name}.webm`);
  execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-ss', start.toFixed(2), '-t', CLIP_S.toFixed(2), '-i', raw, '-vf', `${crop},scale='min(960,iw)':-2`, '-c:v', 'libvpx-vp9', '-b:v', '0', '-crf', '40', '-row-mt', '1', '-an', webm]);
  rmSync(tmp, { recursive: true, force: true });
  console.log(`wrote ${webm}`);
  return webm;
}

const light = await record({ name: 'hero-stone' });
await record({ name: 'hero-stone-dark', theme: 'dark' });
await record({ name: 'hero-stone-phone', lang: 'ta', viewport: { width: 375, height: 740 }, fullScreen: true });
await browser.close();

const gif = join(OUT, 'hero-stone.gif');
execFileSync('ffmpeg', ['-y', '-loglevel', 'error', '-i', light, '-vf', 'fps=6,scale=420:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=64:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle', gif]);
console.log(`wrote ${gif}`);
