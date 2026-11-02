#!/usr/bin/env node
// Frame-accurate renderer for the 30 s social cuts (same method as media/video/render.mjs, any frame size).
//
//   node media/social/render.mjs teaser-16x9 teaser-1x1 reel-9x16     render formats from social.json (+ mux mix.wav)
//   node media/social/render.mjs --stills 0,1,2 reel-9x16               PNG stills (seconds) into ezhuthu-video/social/frames/
//   node media/social/render.mjs --serve                                 preview server (pages autoplay)
//   options: --concurrency 4  --crf 17  --noaudio
//
// Server roots: "/" = worktree root (so pages load /media/social/vo.json, /design/...), "/__fonts/", "/__stock/"
// (4096 px plates), "/__clips/" (main-film all-intra clips), "/__scenes/" (ezhuthu-video/social/clips = all-intra
// copies of the rendered main-film scenes). Each page exposes window.__seek(t) (media/video/scenes/_lib/timeline.js).
// Frames are JPEG q95 screenshots written to ezhuthu-video/social/work/<fmt>/, then encoded (H.264 High, yuv420p,
// 30 fps CFR, exactly duration*fps frames) with the mixed soundtrack (AAC 320k, 48 kHz) -> ezhuthu-video/social/out/.
// The 4:5 feed variant is a crop of the 9:16 render (social.json formats.reel-4x5.crop).
import { createRequire } from 'node:module';
import { spawnSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const HOME = os.homedir();
const VIDEO = process.env.EZ_VIDEO_DIR || path.join(HOME, 'tamil-script/ezhuthu-video');
const SOC = path.join(VIDEO, 'social');
const PW_FROM = process.env.PLAYWRIGHT_FROM || path.join(HOME, 'tamil-script/ezhuthu/app/web/');
const { chromium } = createRequire(PW_FROM)('playwright');
const CUT = JSON.parse(fs.readFileSync(path.join(HERE, 'social.json'), 'utf8'));

const argv = process.argv.slice(2);
const opt = { concurrency: 4, crf: 17, stills: null, serve: false, audio: true };
const ids = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--concurrency') opt.concurrency = +argv[++i];
  else if (a === '--crf') opt.crf = +argv[++i];
  else if (a === '--stills') opt.stills = argv[++i];
  else if (a === '--serve') opt.serve = true;
  else if (a === '--noaudio') opt.audio = false;
  else ids.push(a);
}

const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.mp4': 'video/mp4',
  '.webm': 'video/webm', '.ttf': 'font/ttf', '.woff2': 'font/woff2' };
function resolveFile(u) {
  const p = decodeURIComponent(u.split('?')[0]);
  const tries = [];
  if (p.startsWith('/__fonts/')) tries.push(path.join(VIDEO, 'fonts', p.slice(9)), path.join(HOME, '.cache/ezhuthu-design-fonts', p.slice(9)));
  else if (p.startsWith('/__stock/')) tries.push(path.join(VIDEO, 'stock', p.slice(9)));
  else if (p.startsWith('/__clips/')) tries.push(path.join(VIDEO, 'clips', p.slice(9)));
  else if (p.startsWith('/__scenes/')) tries.push(path.join(SOC, 'clips', p.slice(10)));
  else tries.push(path.join(ROOT, p));
  for (const f of tries) { const r = path.resolve(f); if (fs.existsSync(r) && fs.statSync(r).isFile()) return r; }
  return null;
}
const srv = http.createServer((req, res) => {
  const f = resolveFile(req.url);
  if (!f) { res.writeHead(404); return res.end('not found'); }
  const size = fs.statSync(f).size;
  const type = TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream';
  const m = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
  if (m) {
    const start = m[1] ? +m[1] : size - +m[2];
    const end = m[1] && m[2] ? Math.min(+m[2], size - 1) : size - 1;
    res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1, 'Cache-Control': 'no-cache' });
    fs.createReadStream(f, { start, end }).pipe(res);
  } else {
    res.writeHead(200, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
    fs.createReadStream(f).pipe(res);
  }
});
await new Promise((r) => srv.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${srv.address().port}`;
if (opt.serve) {
  for (const [k, f] of Object.entries(CUT.formats)) if (f.page) console.log(`${k}: ${BASE}/media/social/${f.page}`);
  await new Promise(() => {});
}

const args = ['--autoplay-policy=no-user-gesture-required', '--force-color-profile=srgb', '--disable-lcd-text', '--hide-scrollbars', '--mute-audio'];
let browser;
try { browser = await chromium.launch({ channel: process.env.EZ_CHANNEL ?? 'chrome', args }); } catch { browser = await chromium.launch({ args }); }

async function open(f) {
  const ctx = await browser.newContext({ viewport: { width: f.w, height: f.h }, deviceScaleFactor: 1, colorScheme: 'dark' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  page.on('requestfailed', (r) => { const x = r.failure(); if (!(x && /ERR_ABORTED/.test(x.errorText))) errs.push('request failed ' + r.url()); });
  page.on('response', (r) => { if (r.status() >= 400) errs.push(`${r.status()} ${r.url()}`); });
  const sep = f.page.includes('?') ? '&' : '?';
  await page.goto(`${BASE}/media/social/${f.page}${sep}play=0`, { waitUntil: 'load' });
  await page.evaluate(() => window.__ready());
  return { ctx, page, errs };
}

const FPS = CUT.fps, DUR = CUT.duration_s, NF = Math.round(FPS * DUR);
for (const id of ids) {
  const f = CUT.formats[id];
  if (!f) { console.error('unknown format', id); continue; }
  if (f.from) { crop(id, f); continue; }
  if (opt.stills) {
    const out = path.join(SOC, 'frames', id); fs.mkdirSync(out, { recursive: true });
    const { ctx, page, errs } = await open(f);
    for (const t of opt.stills.split(',').map(Number)) {
      await page.evaluate((x) => window.__seek(x), t);
      await page.screenshot({ path: path.join(out, `t${t.toFixed(2).padStart(5, '0')}.png`) });
    }
    if (errs.length) console.log(id, 'errors:', errs.slice(0, 5));
    await ctx.close();
    console.log('stills ->', out);
    continue;
  }
  const dir = path.join(SOC, 'work', id); fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir, { recursive: true });
  const t0 = Date.now();
  const allErrs = [];
  const chunk = Math.ceil(NF / opt.concurrency);
  await Promise.all([...Array(opt.concurrency).keys()].map(async (w) => {
    const { ctx, page, errs } = await open(f);
    for (let i = w * chunk; i < Math.min(NF, (w + 1) * chunk); i++) {
      await page.evaluate((x) => window.__seek(x), i / FPS);
      await page.screenshot({ path: path.join(dir, `f${String(i).padStart(4, '0')}.jpg`), type: 'jpeg', quality: 95 });
    }
    allErrs.push(...errs);
    await ctx.close();
  }));
  const out = path.join(SOC, 'out', f.out); fs.mkdirSync(path.dirname(out), { recursive: true });
  const mix = path.join(SOC, 'audio', 'mix.wav');
  const a = ['-y', '-v', 'error', '-framerate', String(FPS), '-i', path.join(dir, 'f%04d.jpg')];
  if (opt.audio && fs.existsSync(mix)) a.push('-i', mix, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '320k', '-ar', '48000');
  a.push('-c:v', 'libx264', '-profile:v', 'high', '-preset', 'slow', '-crf', String(opt.crf), '-pix_fmt', 'yuv420p',
    '-r', String(FPS), '-frames:v', String(NF), '-t', DUR.toFixed(3), '-movflags', '+faststart', out);
  const r = spawnSync('ffmpeg', a, { stdio: 'inherit' });
  console.log(`${id}: ${NF} frames in ${((Date.now() - t0) / 1000).toFixed(0)} s -> ${out} (ffmpeg ${r.status})` + (allErrs.length ? `\n  page errors: ${[...new Set(allErrs)].slice(0, 6).join(' | ')}` : ''));
}

function crop(id, f) {
  const src = path.join(SOC, 'out', CUT.formats[f.from].out);
  const out = path.join(SOC, 'out', f.out);
  const r = spawnSync('ffmpeg', ['-y', '-v', 'error', '-i', src, '-vf', `crop=${f.crop}`, '-c:v', 'libx264', '-profile:v', 'high',
    '-preset', 'slow', '-crf', String(opt.crf), '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart', out], { stdio: 'inherit' });
  console.log(`${id}: cropped ${f.crop} from ${f.from} -> ${out} (ffmpeg ${r.status})`);
}

await browser.close();
srv.close();
