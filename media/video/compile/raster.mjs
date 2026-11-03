// Rasterise an HTML card to PNG with Chromium (correct Tamil shaping; the local PIL has no raqm).
// Usage: node raster.mjs PAGE.html OUT.png WIDTH HEIGHT [transparent]
// In the page, __VID__ and __REPO__ are replaced with file:// URLs of the binaries dir and the worktree root.
import { createRequire } from 'node:module';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const HERE = path.dirname(fileURLToPath(import.meta.url));
const [page, out, w, h, mode] = process.argv.slice(2);
const VID = process.env.VID || path.join(os.homedir(), 'tamil-script/ezhuthu-video');
const REPO = path.resolve(HERE, '..', '..', '..');
const PW_FROM = process.env.PLAYWRIGHT_FROM || path.join(os.homedir(), 'tamil-script/ezhuthu/app/web/');
const { chromium } = createRequire(PW_FROM)('playwright');
const html = fs.readFileSync(page, 'utf8').replaceAll('__VID__', 'file://' + VID).replaceAll('__REPO__', 'file://' + REPO);
const tmp = path.join(VID, 'build', path.basename(page, '.html') + '.render.html');
fs.mkdirSync(path.dirname(tmp), { recursive: true });
fs.writeFileSync(tmp, html);
const browser = await chromium.launch({ args: ['--force-color-profile=srgb', '--allow-file-access-from-files'] });
const p = await browser.newPage({ viewport: { width: +w, height: +h }, deviceScaleFactor: 1 });
await p.goto('file://' + tmp, { waitUntil: 'networkidle' });
await p.evaluate(() => document.fonts.ready);
await p.screenshot({ path: out, omitBackground: mode === 'transparent' });
await browser.close();
fs.rmSync(tmp);
console.log('raster', out);
