#!/usr/bin/env node
// Frame-accurate renderer for the Ezhuthu launch-video scenes.
//
//   node media/video/render.mjs                      render every scene in storyboard.json
//   node media/video/render.mjs s07-hero-read s17-headline
//   node media/video/render.mjs --stills 0.5,2,4.9 s01-hook   PNG stills only (scene-local seconds; "auto" = 5 spread)
//   node media/video/render.mjs --serve              preview server only (open the printed URL; scenes autoplay)
//   options: --concurrency 3  --fps 30  --png (lossless frames into ffmpeg, slower)  --crf 16
//
// How it works: a tiny static server maps "/" to the repo root, "/__fonts/" to $EZ_VIDEO_DIR/fonts (falls back to
// ~/.cache/ezhuthu-design-fonts), "/__footage/" to $EZ_VIDEO_DIR/footage, "/__stock/" to $EZ_VIDEO_DIR/stock (stock/web = graded-ready
// 4096 px photos) and "/__clips/" to $EZ_VIDEO_DIR/clips (all-intra trims made by prep-clips.sh), with HTTP Range so <video> can seek.
// Each scene page exposes window.__seek(t) (media/video/scenes/_lib/timeline.js). For frame i we await
// __seek(i / fps), take a 1920x1080 screenshot and pipe it into ffmpeg, so every frame is exactly where the timeline
// says it is, regardless of how slow the machine is. Output: $EZ_VIDEO_DIR/scenes/<id>.mp4 (H.264 High, yuv420p,
// 30 fps CFR, exactly round(duration_s * fps) frames; duration_s comes from storyboard.json).
import { createRequire } from 'node:module';
import { spawn, execFileSync } from 'node:child_process';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..'); // repo (worktree) root
const HOME = os.homedir();
const VIDEO = process.env.EZ_VIDEO_DIR || path.join(HOME, 'tamil-script/ezhuthu-video');
const PW_FROM = process.env.PLAYWRIGHT_FROM || path.join(HOME, 'tamil-script/ezhuthu/app/web/');
const { chromium } = createRequire(PW_FROM.endsWith('/') ? PW_FROM : PW_FROM + '/')('playwright');

// ---------- args ----------
const argv = process.argv.slice(2);
const opt = { fps: 30, concurrency: 2, png: false, crf: 16, stills: null, serve: false, port: 0 };
const ids = [];
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--fps') opt.fps = +argv[++i];
  else if (a === '--concurrency') opt.concurrency = +argv[++i];
  else if (a === '--png') opt.png = true;
  else if (a === '--crf') opt.crf = +argv[++i];
  else if (a === '--stills') opt.stills = argv[++i];
  else if (a === '--serve') opt.serve = true;
  else if (a === '--port') opt.port = +argv[++i];
  else ids.push(a);
}
const storyboard = JSON.parse(fs.readFileSync(path.join(HERE, 'storyboard.json'), 'utf8'));
const scenes = (ids.length ? ids.map((id) => storyboard.find((s) => s.id === id) || { id, duration_s: null }) : storyboard);

// ---------- static server with Range ----------
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.avif': 'image/avif', '.gif': 'image/gif',
  '.webm': 'video/webm', '.mp4': 'video/mp4', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.woff': 'font/woff' };
function resolveFile(urlPath) {
  const p = decodeURIComponent(urlPath.split('?')[0]);
  const tries = [];
  if (p.startsWith('/__fonts/')) { const f = p.slice(9); tries.push(path.join(VIDEO, 'fonts', f), path.join(HOME, '.cache/ezhuthu-design-fonts', f)); }
  else if (p.startsWith('/__footage/')) tries.push(path.join(VIDEO, 'footage', p.slice(11)));
  else if (p.startsWith('/__stock/')) tries.push(path.join(VIDEO, 'stock', p.slice(9)));
  else if (p.startsWith('/__clips/')) tries.push(path.join(VIDEO, 'clips', p.slice(9)));
  else tries.push(path.join(ROOT, p));
  for (const f of tries) { const r = path.resolve(f); if (fs.existsSync(r) && fs.statSync(r).isFile()) return r; }
  return null;
}
function serve(port) {
  const srv = http.createServer((req, res) => {
    if (req.url.startsWith('/favicon')) { res.writeHead(204); return res.end(); }
    const f = resolveFile(req.url === '/' ? '/media/video/scenes/index.html' : req.url);
    if (!f) { res.writeHead(404); return res.end('not found'); }
    const size = fs.statSync(f).size;
    const type = TYPES[path.extname(f).toLowerCase()] || 'application/octet-stream';
    const range = req.headers.range && /bytes=(\d*)-(\d*)/.exec(req.headers.range);
    if (range) {
      const start = range[1] ? +range[1] : size - +range[2];
      const end = range[1] && range[2] ? Math.min(+range[2], size - 1) : size - 1;
      res.writeHead(206, { 'Content-Type': type, 'Content-Range': `bytes ${start}-${end}/${size}`, 'Accept-Ranges': 'bytes', 'Content-Length': end - start + 1, 'Cache-Control': 'no-cache' });
      fs.createReadStream(f, { start, end }).pipe(res);
    } else {
      res.writeHead(200, { 'Content-Type': type, 'Content-Length': size, 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-cache' });
      fs.createReadStream(f).pipe(res);
    }
  });
  return new Promise((r) => srv.listen(port, '127.0.0.1', () => r(srv)));
}

const srv = await serve(opt.port);
const BASE = `http://127.0.0.1:${srv.address().port}`;
if (opt.serve) {
  console.log(`serving ${ROOT}\n${scenes.map((s) => `  ${BASE}/media/video/scenes/${s.id}.html`).join('\n')}`);
  await new Promise(() => {});
}

const launch = async () => {
  const args = ['--autoplay-policy=no-user-gesture-required', '--force-color-profile=srgb', '--disable-lcd-text', '--hide-scrollbars', '--mute-audio'];
  try { return await chromium.launch({ channel: process.env.EZ_CHANNEL ?? 'chrome', args }); } // Chrome decodes H.264 footage
  catch { return chromium.launch({ args }); }
};
const browser = await launch();

async function openScene(s) {
  const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1, colorScheme: 'dark', reducedMotion: 'no-preference' });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', (e) => errs.push(e.message));
  page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
  // Chrome cancels superseded media range requests while seeking (net::ERR_ABORTED): not an error
  page.on('requestfailed', (r) => { const f = r.failure(); if (!(f && /ERR_ABORTED/.test(f.errorText))) errs.push('request failed ' + r.url() + (f ? ' ' + f.errorText : '')); });
  page.on('response', (r) => { if (r.status() >= 400) errs.push(`${r.status()} ${r.url()}`); });
  await page.goto(`${BASE}/media/video/scenes/${s.id}.html?play=0`, { waitUntil: 'load' });
  await page.evaluate(() => window.__ready());
  const sceneDur = await page.evaluate(() => window.SCENE && window.SCENE.duration);
  return { ctx, page, errs, sceneDur };
}

async function stills(s) {
  const out = path.join(VIDEO, 'stills'); fs.mkdirSync(out, { recursive: true });
  const { ctx, page, errs, sceneDur } = await openScene(s);
  const dur = s.duration_s ?? sceneDur;
  const ts = opt.stills === 'auto' ? [0.12, 0.35, 0.6, 0.82, 0.985].map((k) => +(k * dur).toFixed(2)) : opt.stills.split(',').map(Number);
  const files = [];
  for (const t of ts) {
    await page.evaluate((t) => window.__seek(t), t);
    const f = path.join(out, `${s.id}@${t.toFixed(2)}.png`);
    await page.screenshot({ path: f, type: 'png' }); files.push(f);
  }
  await ctx.close();
  return { id: s.id, files, errs };
}

async function render(s) {
  const out = path.join(VIDEO, 'scenes'); fs.mkdirSync(out, { recursive: true });
  const { ctx, page, errs, sceneDur } = await openScene(s);
  const dur = s.duration_s ?? sceneDur;
  if (s.duration_s && sceneDur && Math.abs(sceneDur - s.duration_s) > 1e-6) errs.push(`scene duration ${sceneDur} != storyboard ${s.duration_s}`);
  const frames = Math.round(dur * opt.fps);
  const file = path.join(out, `${s.id}.mp4`);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(opt.fps), '-c:v', opt.png ? 'png' : 'mjpeg', '-i', '-',
    '-frames:v', String(frames), '-c:v', 'libx264', '-preset', 'slow', '-crf', String(opt.crf), '-profile:v', 'high', '-pix_fmt', 'yuv420p',
    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709', '-r', String(opt.fps), '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
  const write = (buf) => new Promise((r) => (ff.stdin.write(buf) ? r() : ff.stdin.once('drain', r)));
  const t0 = Date.now();
  for (let i = 0; i < frames; i++) {
    await page.evaluate((t) => window.__seek(t), i / opt.fps);
    const buf = await page.screenshot(opt.png ? { type: 'png' } : { type: 'jpeg', quality: 96 });
    await write(buf);
    if (i % 60 === 0) process.stdout.write(`  ${s.id} ${i}/${frames}\r`);
  }
  ff.stdin.end();
  await new Promise((r) => ff.on('close', r));
  await ctx.close();
  let got = null;
  try { got = parseInt(execFileSync('ffprobe', ['-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames', '-of', 'csv=p=0', file]).toString(), 10); } catch {}
  if (got !== frames) errs.push(`frame count ${got} != ${frames}`);
  return { id: s.id, file, frames, seconds: frames / opt.fps, took_s: Math.round((Date.now() - t0) / 1000), errs };
}

// ---------- run with a small worker pool ----------
const queue = [...scenes];
const results = [];
async function worker() { while (queue.length) { const s = queue.shift(); try { results.push(await (opt.stills ? stills(s) : render(s))); } catch (e) { results.push({ id: s.id, errs: [e.message] }); } } }
await Promise.all(Array.from({ length: Math.max(1, opt.concurrency) }, worker));
await browser.close(); srv.close();
results.sort((a, b) => a.id.localeCompare(b.id));
for (const r of results) console.log(`${r.id.padEnd(22)} ${r.file ? `${r.frames} frames ${r.seconds.toFixed(2)} s (${r.took_s} s)` : (r.files || []).length + ' stills'}${r.errs.length ? '  ERR ' + [...new Set(r.errs)].join(' | ') : ''}`);
if (!opt.stills) fs.writeFileSync(path.join(VIDEO, 'scenes', 'render-report.json'), JSON.stringify(results, null, 2));
process.exit(results.some((r) => r.errs.length) ? 1 : 0);
