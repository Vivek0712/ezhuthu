// Render blog/figures/html/*.html to blog/img/*.png (element #fig at its own size, 1x).
// Usage: node blog/figures/render.cjs [name-substring ...]
const path = require('path');
const fs = require('fs');
const PW = process.env.PW_PATH || '/Users/vivekrajaps/tamil-script/ezhuthu/app/web/node_modules/@playwright/test';
const { chromium } = require(PW);
const HTML = path.join(__dirname, 'html');
const IMG = path.join(__dirname, '..', 'img');
const only = process.argv.slice(2);

(async () => {
  fs.mkdirSync(IMG, { recursive: true });
  const b = await chromium.launch({ args: ['--allow-file-access-from-files'] });
  const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 1 });
  for (const f of fs.readdirSync(HTML).filter((f) => f.endsWith('.html')).sort()) {
    const name = f.replace(/\.html$/, '');
    if (only.length && !only.some((o) => name.includes(o))) continue;
    await p.goto('file://' + path.join(HTML, f), { waitUntil: 'load' });
    await p.evaluate(() => document.fonts.ready);
    await p.waitForTimeout(250);
    const el = p.locator('#fig');
    await el.screenshot({ path: path.join(IMG, name + '.png') });
    // overflow check: any text node box extending outside #fig
    const issues = await p.evaluate(() => {
      const fig = document.querySelector('#fig').getBoundingClientRect();
      const bad = [];
      for (const e of document.querySelectorAll('#fig *')) {
        const r = e.getBoundingClientRect();
        if (!r.width || !r.height) continue;
        if (r.right > fig.right + 1 || r.bottom > fig.bottom + 1 || r.left < fig.left - 1) bad.push(`${e.tagName}.${e.className.baseVal ?? e.className}:${(e.textContent || '').slice(0, 30)}`);
        if (e.scrollWidth > e.clientWidth + 2 && getComputedStyle(e).overflow === 'visible' && e.children.length === 0 && e.clientWidth) bad.push('overflowX ' + (e.textContent || '').slice(0, 30));
      }
      return bad.slice(0, 8);
    });
    console.log(name, issues.length ? 'CHECK: ' + issues.join(' | ') : 'ok');
  }
  await b.close();
})();
