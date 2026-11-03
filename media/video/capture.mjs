#!/usr/bin/env node
// Capture scripted product footage of the live Ezhuthu site for the launch video.
//
//   node media/video/capture.mjs [flow ...]        (default: all flows)
//
// Frames come from the Chrome DevTools screencast (JPEG, device pixels), are resampled to a constant
// 30 fps on their own timestamps and streamed straight into ffmpeg: no frame files touch the disk.
// Output: $EZ_VIDEO_DIR/footage/<flow>.mp4 (H.264, yuv420p, keyframe every 15 frames) plus
// footage/manifest.json with event markers (seconds from the start of each clip) so scenes can cut on them.
//
// The browser shows a drawn cursor and a laterite click ripple (headless Chrome has no cursor of its own).
// Playwright is resolved from $PLAYWRIGHT_FROM (default: the main checkout's app/web) because this worktree
// has no node_modules.
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const HOME = os.homedir();
const PW_FROM = process.env.PLAYWRIGHT_FROM || path.join(HOME, 'tamil-script/ezhuthu/app/web/');
const { chromium } = createRequire(PW_FROM.endsWith('/') ? PW_FROM : PW_FROM + '/')('playwright');
const SITE = process.env.EZ_SITE || 'https://ezhuthu.sparrowdecider.com';
const OUT = path.join(process.env.EZ_VIDEO_DIR || path.join(HOME, 'tamil-script/ezhuthu-video'), 'footage');
fs.mkdirSync(OUT, { recursive: true });
const FPS = 30;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- in-page helpers (cursor, ripple, eased scrolling) ----------
const PAGE_HELPERS = () => {
  if (window.__ezScroll) return;
  window.__ezScroll = (to, ms) => new Promise((res) => {
    const from = scrollY; const t0 = performance.now();
    const ease = (x) => (x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2);
    const step = (now) => { const k = Math.min(1, (now - t0) / ms); scrollTo(0, from + (to - from) * ease(k)); if (k < 1) requestAnimationFrame(step); else res(); };
    requestAnimationFrame(step);
  });
  const install = () => {
  if (window.__ezCursor || !document.body) return;
  const st = document.createElement('style');
  st.textContent = `
  #ez-cursor{position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;
    transform:translate(-3px,-2px);filter:drop-shadow(0 2px 6px rgba(0,0,0,.55));transition:none}
  .ez-ripple{position:fixed;z-index:2147483646;pointer-events:none;width:16px;height:16px;margin:-8px 0 0 -8px;
    border-radius:50%;border:3px solid #D9764F;box-shadow:0 0 18px #D9764F;animation:ezr .65s cubic-bezier(.2,0,0,1) forwards}
  @keyframes ezr{from{transform:scale(.4);opacity:1}to{transform:scale(4.2);opacity:0}}
  html{scroll-behavior:auto!important}`;
  document.documentElement.appendChild(st);
  const c = document.createElement('div');
  c.id = 'ez-cursor';
  c.innerHTML = `<svg viewBox="0 0 26 26" width="26" height="26"><path d="M3 2 L3 21 L8.2 16.4 L11.6 24 L15 22.5 L11.7 15 L19 15 Z" fill="#FBF8F1" stroke="#13100D" stroke-width="1.6" stroke-linejoin="round"/></svg>`;
  document.documentElement.appendChild(c);
  window.__ezCursor = c;
  const pos = window.__ezPos || { x: -50, y: -50 };
  c.style.left = pos.x + 'px'; c.style.top = pos.y + 'px';
  addEventListener('mousemove', (e) => { window.__ezPos = { x: e.clientX, y: e.clientY }; c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
  addEventListener('mousedown', (e) => { const r = document.createElement('div'); r.className = 'ez-ripple'; r.style.left = e.clientX + 'px'; r.style.top = e.clientY + 'px'; document.documentElement.appendChild(r); setTimeout(() => r.remove(), 700); }, true);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install); else install();
};

// ---------- recorder: CDP screencast -> CFR 30 fps -> ffmpeg ----------
async function startRecorder(page, file) {
  const cdp = await page.context().newCDPSession(page);
  const vp = page.viewportSize();
  const dsf = await page.evaluate(() => devicePixelRatio);
  const W = Math.round(vp.width * dsf), H = Math.round(vp.height * dsf);
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'mjpeg', '-i', '-',
    '-vf', `scale=${W}:${H}:flags=lanczos,setsar=1,format=yuv420p`, '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-g', '15',
    '-movflags', '+faststart', file], { stdio: ['pipe', 'inherit', 'inherit'] });
  let last = null, written = 0, t0 = null;
  const write = (buf) => new Promise((res) => { if (!ff.stdin.write(buf)) ff.stdin.once('drain', res); else res(); });
  let chain = Promise.resolve();
  cdp.on('Page.screencastFrame', (f) => {
    cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }).catch(() => {});
    const ts = f.metadata.timestamp;
    const buf = Buffer.from(f.data, 'base64');
    chain = chain.then(async () => {
      if (t0 === null) t0 = ts;
      const due = Math.round((ts - t0) * FPS);
      if (last) while (written < due) { await write(last); written++; }
      last = buf;
    });
  });
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: W, maxHeight: H, everyNthFrame: 1 });
  const wall0 = Date.now();
  const rec = {
    at: () => (Date.now() - wall0) / 1000, // marker time (s) relative to recording start
    async stop() {
      // keep the final frame on screen until "now"
      const endS = (Date.now() - wall0) / 1000;
      await cdp.send('Page.stopScreencast').catch(() => {});
      await chain;
      const due = Math.round(endS * FPS);
      if (last) { while (written < due) { await write(last); written++; } }
      ff.stdin.end();
      await new Promise((r) => ff.on('close', r));
      return written / FPS;
    },
  };
  // force a first frame even on a static page
  await page.evaluate(() => { document.body.style.outline = '0 solid transparent'; });
  return rec;
}

async function moveTo(page, locatorOrXY, ms = 700) {
  let x, y;
  if (Array.isArray(locatorOrXY)) [x, y] = locatorOrXY;
  else { const b = await locatorOrXY.boundingBox(); x = b.x + b.width / 2; y = b.y + b.height / 2; }
  await page.mouse.move(x, y, { steps: Math.max(8, Math.round(ms / 16)) });
  return [x, y];
}
async function clickSmooth(page, loc, ms = 700) { await loc.scrollIntoViewIfNeeded(); await page.evaluate(() => { if (scrollX) scrollTo(0, scrollY); }); await moveTo(page, loc, ms); await sleep(180); await page.mouse.down(); await sleep(90); await page.mouse.up(); }
const scrollTo = (page, y, ms) => page.evaluate(([y, ms]) => window.__ezScroll(y, ms), [y, ms]);
const yOf = (page, loc) => loc.evaluate((e) => e.getBoundingClientRect().top + scrollY);

async function newPage(browser, { mobile = false, tamil = false } = {}) {
  const ctx = await browser.newContext(mobile
    ? { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: false, colorScheme: 'dark' }
    : { viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1.5, colorScheme: 'dark' });
  await ctx.addInitScript(PAGE_HELPERS);
  if (tamil) await ctx.addInitScript(() => { try { for (const k of ['ezhuthu.lang', 'ez-lang', 'lang', 'ezhuthu:lang']) localStorage.setItem(k, 'ta'); } catch (e) {} });
  const page = await ctx.newPage();
  return { ctx, page };
}
async function settle(page, ms = 1200) { await page.waitForLoadState('networkidle', { timeout: 30000 }).catch(() => {}); await page.evaluate(() => document.fonts.ready); await sleep(ms); }
async function switchTamil(page) {
  const b = page.getByRole('button', { name: /Switch to Tamil|தமிழ்/ }).first();
  if (await b.count()) { await b.click(); await sleep(600); }
}


// answer the open letter drill correctly: read the Tamil-Brahmi glyph on screen, look it up in the practice bank
const BANK = JSON.parse(fs.readFileSync(new URL('../../app/web/src/practice/banks/letters.json', import.meta.url), 'utf8')).items;
async function answerDrill(page, ms = 900) {
  const glyph = await page.evaluate(() => { const m = document.querySelector('main').innerText.match(/[\u{11000}-\u{1107F}]+/u); return m && m[0]; });
  const item = BANK.find((it) => it.glyph === glyph);
  const opts = page.locator('main button[data-testid^="option-"]');
  let pick = opts.first();
  if (item) {
    const want = item.options[item.answer].ta;
    for (let i = 0; i < await opts.count(); i++) { const tx = (await opts.nth(i).innerText()).split('\n').map((x) => x.trim()); if (tx.includes(want)) { pick = opts.nth(i); break; } }
  }
  await clickSmooth(page, pick, ms);
  return { glyph, matched: !!item };
}

// ---------- flows ----------
const FLOWS = {
  // Home hero: the real Thanjavur stone read letter by letter (Reader -> Restorer -> Confidence -> Interpreter)
  async 'home-hero'(browser) {
    const { ctx, page } = await newPage(browser);
    await page.goto(SITE + '/', { waitUntil: 'domcontentloaded' });
    await settle(page, 400);
    // frame the hero panel: stone photo near the top of the viewport so the whole panel and its stepper show
    const stone = page.locator('img[src*="thanjavur"], picture img').first();
    if (await stone.count()) { const y = await yOf(page, stone); await page.evaluate((y) => scrollTo(0, y), Math.max(0, y - 40)); }
    await sleep(300);
    await page.mouse.move(1270, 715);
    const replay = page.getByRole('button', { name: 'Replay' });
    const rec = await startRecorder(page, path.join(OUT, 'home-hero.mp4'));
    const m = {};
    if (await replay.count()) { await replay.evaluate((b) => b.click()); }
    m.replay = rec.at();
    await sleep(23500);
    m.heroDone = rec.at();
    await sleep(1000);
    const d = await rec.stop(); await ctx.close();
    return { duration: d, markers: m, viewport: '1280x720@1.5', framing: 'scrolled to the hero panel' };
  },

  // Practice (Tamil UI): hub -> letter drill -> answer one item
  async practice(browser) {
    const { ctx, page } = await newPage(browser);
    await page.goto(SITE + '/practice', { waitUntil: 'domcontentloaded' });
    await settle(page); await switchTamil(page); await settle(page, 600);
    await page.mouse.move(900, 200);
    const rec = await startRecorder(page, path.join(OUT, 'practice.mp4'));
    const m = {};
    await sleep(900);
    await scrollTo(page, 260, 1400); await sleep(500);
    const card = page.locator('a[href="/practice/letters?level=1"]').nth(1);
    m.openDrill = rec.at();
    await clickSmooth(page, card, 900);
    await settle(page, 900);
    // answer the drill correctly, show the feedback, then the next question
    const q = page.locator('main button[data-testid^="option-"]').first();
    if (await q.count()) {
      const y = await yOf(page, page.getByText(/எந்தத் தமிழ் எழுத்து|Which modern Tamil letter/).first());
      await scrollTo(page, Math.max(0, y - 120), 1100); await sleep(400);
      m.answer = rec.at();
      m.drill = await answerDrill(page, 900);
      await sleep(2800);
    }
    const d = await rec.stop(); await ctx.close();
    return { duration: d, markers: m, viewport: '1280x720@1.5', ui: 'ta' };
  },

  async 'practice-mobile'(browser) {
    const { ctx, page } = await newPage(browser, { mobile: true });
    await page.goto(SITE + '/practice', { waitUntil: 'domcontentloaded' });
    await settle(page); await switchTamil(page); await settle(page, 600);
    const rec = await startRecorder(page, path.join(OUT, 'practice-mobile.mp4'));
    await sleep(800); await scrollTo(page, 500, 2200); await sleep(600);
    const card = page.locator('a[href="/practice/letters?level=1"]').nth(1);
    if (await card.count()) { await clickSmooth(page, card, 600); await settle(page, 800); }
    const q = page.locator('main button[data-testid^="option-"]').first();
    if (await q.count()) {
      // scroll vertically only (scrollIntoView also scrolled the page sideways: the drill page overflows at 390 px)
      const y = await yOf(page, q); await scrollTo(page, Math.max(0, y - 330), 900); await page.evaluate(() => scrollTo(0, scrollY)); await sleep(400);
      await answerDrill(page, 600); await page.evaluate(() => scrollTo(0, scrollY));
    }
    await sleep(2500);
    const d = await rec.stop(); await ctx.close();
    return { duration: d, markers: {}, viewport: '390x844@2' };
  },

  // Restore a masked gallery sample the recorded run fills (edition reading shown after)
  async 'restore-fill'(browser) { return restoreFlow(browser, process.env.EZ_FILL_SAMPLE || 'tiruvalisvaram-district-name', 'restore-fill'); },
  async 'restore-fill-stills'(browser) { return restoreStills(browser, process.env.EZ_FILL_SAMPLE || 'tiruvalisvaram-district-name', 'restore-fill'); },
  async 'restore-open-stills'(browser) { return restoreStills(browser, 'mamallapuram-calf-pasture', 'restore-open'); },
  // Restore a genuine lacuna: proposes options, leaves it open for an expert
  async 'restore-open'(browser) { return restoreFlow(browser, 'mamallapuram-calf-pasture', 'restore-open'); },

  // How it works: the animated overview
  async how(browser) {
    const { ctx, page } = await newPage(browser);
    await page.goto(SITE + '/how-it-works', { waitUntil: 'domcontentloaded' });
    await settle(page, 800);
    await page.mouse.move(1150, 600);
    const rec = await startRecorder(page, path.join(OUT, 'how.mp4'));
    const m = {};
    await sleep(700);
    const play = page.getByRole('button', { name: /Play the flow/ });
    if (await play.count()) { const y = await yOf(page, play); await scrollTo(page, Math.max(0, y - 560), 1400); m.play = rec.at(); await clickSmooth(page, play, 800); }
    await scrollTo(page, 0, 1200);
    await sleep(20000);
    m.flowDone = rec.at();
    const d = await rec.stop(); await ctx.close();
    return { duration: d, markers: m, viewport: '1280x720@1.5' };
  },

  // Benchmark: leaderboard, then reliability chart, with a slow scripted scroll
  async benchmark(browser) {
    const { ctx, page } = await newPage(browser);
    await page.goto(SITE + '/benchmark', { waitUntil: 'domcontentloaded' });
    await settle(page, 1000);
    await page.mouse.move(1180, 650);
    const rec = await startRecorder(page, path.join(OUT, 'benchmark.mp4'));
    const m = {};
    await sleep(1500);
    const H = await page.evaluate(() => document.body.scrollHeight - innerHeight);
    m.scrollStart = rec.at();
    await scrollTo(page, Math.min(H, 1000), 4000); await sleep(1200);
    const hard = page.getByRole('button', { name: /Hard gaps/ });
    if (await hard.count() && await hard.isVisible()) { m.hard = rec.at(); await clickSmooth(page, hard, 700); await sleep(1500); }
    await scrollTo(page, Math.min(H, 2300), 5000); await sleep(1500);
    await scrollTo(page, Math.min(H, 3300), 4000); await sleep(1500);
    const d = await rec.stop(); await ctx.close();
    return { duration: d, markers: m, viewport: '1280x720@1.5' };
  },
};

// Restore as crisp stills (DPR 3 = 3840 px wide): the input page and the result page, plus every visible text leaf's
// box in CSS px (page coordinates) so a2-10 / a2-11 can frame, ring and cut on exact elements. No scroll capture,
// so no half-painted screencast frames. Writes footage/stills/<name>-{input,result}.jpg and <name>.json.
async function restoreStills(browser, sample, name) {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 3, colorScheme: 'dark' });
  const page = await ctx.newPage();
  const dir = path.join(OUT, 'stills'); fs.mkdirSync(dir, { recursive: true });
  await page.goto(`${SITE}/restore?sample=${sample}`, { waitUntil: 'domcontentloaded' });
  await settle(page, 800);
  const leaves = () => page.evaluate(() => [...document.querySelectorAll('main *')].filter((el) => {
    const b = el.getBoundingClientRect(); return el.children.length === 0 && el.textContent.trim() && b.width > 1; })
    .map((el) => { const b = el.getBoundingClientRect(); return { tag: el.tagName, cls: el.className.toString(), text: el.textContent.trim().slice(0, 140),
      x: +b.x.toFixed(1), y: +(b.y + scrollY).toFixed(1), w: +b.width.toFixed(1), h: +b.height.toFixed(1) }; }));
  const H = 2300; // CSS px from the top: input form, result, edition comparison, first gap card
  const shot = (f) => page.screenshot({ path: path.join(dir, f), type: 'jpeg', quality: 93, fullPage: true, clip: { x: 0, y: 0, width: 1280, height: H } });
  await page.evaluate(() => scrollTo(0, 0));
  const input = await leaves(); await shot(`${name}-input.jpg`);
  const resp = page.waitForResponse((r) => r.url().includes('/api/restore'), { timeout: 60000 }).catch(() => null);
  const t0 = Date.now();
  await page.getByRole('button', { name: 'Restore missing letters' }).click();
  const r = await resp; const wait = (Date.now() - t0) / 1000;
  await sleep(1500); await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => scrollTo(0, 0)); await page.mouse.move(-10, -10);
  const result = await leaves(); await shot(`${name}-result.jpg`);
  fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify({ sample, site: SITE, captured: new Date().toISOString(), dpr: 3, width: 1280, height: H,
    status: r ? r.status() : null, wait_s: wait, input, result }, null, 1));
  await ctx.close();
  return { duration: 0, markers: { wait_s: wait, status: r ? r.status() : null }, viewport: '1280x' + H + '@3 stills', sample };
}

async function restoreFlow(browser, sample, name) {
  const { ctx, page } = await newPage(browser);
  await page.goto(`${SITE}/restore?sample=${sample}`, { waitUntil: 'domcontentloaded' });
  await settle(page, 800);
  const ta = page.locator('textarea').first();
  const btn = page.getByRole('button', { name: 'Restore missing letters' });
  await page.mouse.move(1100, 360);
  const rec = await startRecorder(page, path.join(OUT, `${name}.mp4`));
  const m = {};
  await sleep(600);
  const yT = await yOf(page, ta);
  await scrollTo(page, Math.max(0, yT - 170), 1800); await sleep(500);
  const resp = page.waitForResponse((r) => r.url().includes('/api/restore'), { timeout: 60000 }).catch(() => null);
  m.click = rec.at();
  await clickSmooth(page, btn, 900);
  await page.mouse.move(1180, 640, { steps: 30 });
  const r = await resp; m.response = rec.at(); m.status = r ? r.status() : null;
  await sleep(1200);
  // scroll to the result: first element below the button that mentions the edition or the decision
  const yB = await yOf(page, btn);
  m.resultScroll = rec.at();
  await scrollTo(page, yB - 40, 1800);
  await sleep(4500);
  await scrollTo(page, yB + 380, 2200);
  await sleep(3500);
  m.end = rec.at();
  const d = await rec.stop(); await ctx.close();
  return { duration: d, markers: m, viewport: '1280x720@1.5', sample };
}

// ---------- main ----------
const want = process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(FLOWS);
const channel = process.env.EZ_CHANNEL ?? 'chrome';
const browser = await chromium.launch(channel ? { channel } : {}).catch(() => chromium.launch());
const manPath = path.join(OUT, 'manifest.json');
const manifest = fs.existsSync(manPath) ? JSON.parse(fs.readFileSync(manPath, 'utf8')) : {};
for (const f of want) {
  if (!FLOWS[f]) { console.error('unknown flow', f); continue; }
  process.stdout.write(`capturing ${f} ... `);
  try {
    const info = await Promise.race([FLOWS[f](browser), sleep(240000).then(() => { throw new Error('flow timeout 240 s'); })]);
    manifest[f] = { file: `${f}.mp4`, fps: FPS, size: '1920x1080', captured: new Date().toISOString(), site: SITE, ...info };
    console.log(`${info.duration.toFixed(2)} s`, JSON.stringify(info.markers));
  } catch (e) { console.log('FAILED', e.message); manifest[f] = { error: e.message }; }
  fs.writeFileSync(manPath, JSON.stringify(manifest, null, 2));
}
await browser.close();
