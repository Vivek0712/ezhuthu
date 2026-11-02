import { readFileSync } from 'node:fs';
import * as path from 'node:path';
import { describe, expect, it } from 'vitest';

// vitest runs from app/web (package root).
const web = (p: string) => path.resolve(process.cwd(), p);
const repo = (p: string) => path.resolve(process.cwd(), '..', '..', p);

// public/ holds copies because favicons and the manifest need fixed URLs; design/ stays the source of truth.
const ICONS = ['favicon.svg', 'favicon-32.png', 'apple-touch-icon-180.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-192.png', 'icon-maskable-512.png', 'og-image.png'];

describe('brand assets', () => {
  it.each(ICONS)('public/%s is identical to design/brand/icons', (f) => {
    expect(readFileSync(web(`public/${f}`)).equals(readFileSync(repo(`design/brand/icons/${f}`)))).toBe(true);
  });

  it('links the icons, manifest and social preview from index.html', () => {
    const html = readFileSync(web('index.html'), 'utf8');
    expect(html).toContain('<html lang="ta">');
    for (const s of [
      '<link rel="icon" type="image/svg+xml" href="/favicon.svg" />',
      '<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png" />',
      '<link rel="apple-touch-icon" href="/apple-touch-icon-180.png" />',
      '<link rel="manifest" href="/manifest.webmanifest" />',
      '<meta property="og:image" content="/og-image.png" />',
      '<meta name="twitter:card" content="summary_large_image" />',
      'content="#F4EEE2" media="(prefers-color-scheme: light)"',
    ])
      expect(html).toContain(s);
    expect(html).toMatch(/Built with Strands Agents/);
    expect(html).not.toMatch(/Strands AI|AWS AI\b/);
  });

  it('has a PWA manifest with any and maskable icons and the stone theme colour', () => {
    const m = JSON.parse(readFileSync(web('public/manifest.webmanifest'), 'utf8')) as {
      name: string; theme_color: string; background_color: string; icons: { src: string; purpose: string; sizes: string }[];
    };
    expect(m.name).toBe('எழுத்து · Ezhuthu');
    expect(m.theme_color).toBe('#F4EEE2');
    expect(m.background_color).toBe('#F4EEE2');
    expect(m.icons.filter((i) => i.purpose === 'any').map((i) => i.sizes)).toEqual(['192x192', '512x512']);
    expect(m.icons.filter((i) => i.purpose === 'maskable').map((i) => i.sizes)).toEqual(['192x192', '512x512']);
    for (const i of m.icons) expect(ICONS).toContain(i.src.slice(1));
  });

  it('takes colours from the design tokens, not from its own :root palette', () => {
    const css = readFileSync(web('src/styles/app.css'), 'utf8');
    const main = readFileSync(web('src/main.tsx'), 'utf8');
    expect(main.indexOf('design/tokens/tokens.css')).toBeGreaterThan(-1);
    expect(main.indexOf('design/tokens/tokens.css')).toBeLessThan(main.indexOf('design/tokens/app-compat.css'));
    expect(main.indexOf('design/tokens/app-compat.css')).toBeLessThan(main.indexOf('./styles/app.css'));
    // No hex colours in the app stylesheet: every colour is a token (the #000 in the frieze mask is alpha only).
    const hexes = css.replace(/url\("data:[^"]*"\)/g, '').match(/#[0-9a-fA-F]{3,8}\b/g) ?? [];
    expect(hexes.filter((h) => h !== '#000')).toEqual([]);
    expect(css).toContain('outline: 3px solid var(--ez-focus)');
    expect(css).toMatch(/\.abstain \{[^}]*var\(--ez-unsure\)/);
  });
});
