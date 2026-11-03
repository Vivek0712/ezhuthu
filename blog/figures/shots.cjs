// Live-site captures for the blog figures. Raw captures go to ezhuthu-video/blog-shots (never git).
// Usage: node blog/figures/shots.cjs <hero|practice|restore|benchmark|all>
const PW = process.env.PW_PATH || '/Users/vivekrajaps/tamil-script/ezhuthu/app/web/node_modules/@playwright/test';
const { chromium } = require(PW);
const SITE = 'https://ezhuthu.sparrowdecider.com';
const OUT = process.env.SHOTS_DIR || '/Users/vivekrajaps/tamil-script/ezhuthu-video/blog-shots';
const which = process.argv[2] || 'all';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function hero(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1.5 });
  const p = await ctx.newPage();
  await p.goto(SITE + '/', { waitUntil: 'networkidle' });
  const t0 = Date.now();
  const card = p.locator('.hero-stage, [class*="hero"]').filter({ has: p.locator('img, canvas, svg') }).first();
  const box = await card.boundingBox();
  console.log('hero box', box);
  for (const s of [3, 6, 8, 10, 13, 17, 22]) {
    await sleep(Math.max(0, s * 1000 - (Date.now() - t0)));
    await p.screenshot({ path: `${OUT}/hero-${s}.png`, clip: { x: 170, y: 330, width: 1100, height: 600 } });
  }
  await ctx.close();
}

async function practice(b) {
  for (const [name, vp, dsf] of [['desk', { width: 1440, height: 1060 }, 1.5], ['mob', { width: 390, height: 1130 }, 2]]) {
    const ctx = await b.newContext({ viewport: vp, deviceScaleFactor: dsf });
    await ctx.addInitScript(() => { try { localStorage.setItem('ezhuthu.lang.v2', 'ta'); } catch (e) {} });
    const p = await ctx.newPage();
    let done = false;
    for (let k = 0; k < 40 && !done; k++) {
      await p.goto(SITE + '/practice/letters?level=3', { waitUntil: 'networkidle' });
      await sleep(600);
      const t = await p.evaluate(() => document.querySelector('main').innerText);
      if (!/வட்டெழுத்து/.test(t.split('எழுத்து?')[1] || '')) continue;
      await p.locator('main button').nth(3).click();
      await sleep(700);
      const t2 = await p.evaluate(() => document.querySelector('main').innerText);
      if (/✓/.test(t2)) continue; // want the gentle-mistake hint, not the praise
      done = true;
      console.log(name, t2.replace(/\n+/g, ' | ').slice(0, 600));
      await p.evaluate(() => window.scrollTo(0, 0));
      await p.screenshot({ path: `${OUT}/practice-${name}.png`, });
    }
    if (!done) console.log('practice: no wrong-answer Vatteluttu item found for', name);
    await ctx.close();
  }
}

async function restore(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });
  const p = await ctx.newPage();
  const order = (process.env.SAMPLES || 'tiruvavaduturai-taxes-paid-in-gold,tiruvalisvaram-district-name,sirkazhi-feeding-house').split(',');
  for (const s of order) {
    await p.goto(`${SITE}/restore?sample=${s}`, { waitUntil: 'networkidle' });
    await p.addStyleTag({ content: 'header,.site-header,[class*="topbar"]{position:static!important}' });
    await p.getByRole('button', { name: 'Restore missing letters' }).click();
    for (let i = 0; i < 20; i++) { await sleep(3000); const t = await p.evaluate(() => document.body.innerText); if (!/Reading the stone/.test(t)) break; }
    await sleep(1000);
    const t = await p.evaluate(() => document.body.innerText);
    const filled = /fill matches the editors/.test(t); // want a fill that matches the edition
    console.log(s, 'filled?', filled);
    for (const lbl of [/Show the options anyway|Other options considered/]) {
      const el = p.locator('summary').filter({ hasText: lbl }).first();
      if (await el.count()) { await el.click().catch(() => {}); await sleep(500); }
    }
    const tag = filled ? 'match' : 'other-' + Date.now();
    await p.screenshot({ path: `${OUT}/restore-${s}-${tag}.png`, fullPage: true });
    const r = await p.evaluate(() => {
      const h = [...document.querySelectorAll('h1,h2,h3,p,div')].find((e) => e.textContent.trim() === 'Result' || /^\s*\d+ letters? (was|were) missing/.test(e.textContent) && e.children.length < 3);
      const y0 = h ? h.getBoundingClientRect().top + scrollY : 0;
      const tail = [...document.querySelectorAll('*')].find((e) => /evidence, not proof/.test(e.textContent) && e.children.length === 0);
      const y1 = tail ? tail.getBoundingClientRect().bottom + scrollY : y0 + 2000;
      return { y0, y1 };
    });
    console.log(s, r);
    require('fs').writeFileSync(`${OUT}/restore-${s}-${tag}.json`, JSON.stringify(r));
    console.log(t.slice(t.indexOf('Result'), t.indexOf('Result') + 2200).replace(/\n+/g, ' | '));
    if (filled) break;
  }
  await ctx.close();
}

async function benchmark(b) {
  const ctx = await b.newContext({ viewport: { width: 1440, height: 1880 }, deviceScaleFactor: 1600 / 1440 });
  const p = await ctx.newPage();
  await p.goto(SITE + '/benchmark', { waitUntil: 'networkidle' });
  await sleep(2500);
  await p.screenshot({ path: `${OUT}/benchmark-full.png`, fullPage: true });
  await ctx.close();
}

(async () => {
  const b = await chromium.launch();
  const jobs = { hero, practice, restore, benchmark };
  for (const [k, f] of Object.entries(jobs)) if (which === 'all' || which === k) await f(b);
  await b.close();
})();
