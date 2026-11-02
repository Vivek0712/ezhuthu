import { expect, test, type Page } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish, setTamil } from './helpers';

// The home hero's layout at the widths people use (user feedback 2026-11-02: letters collided in the reading panel at
// about 1126 px, and the heading area was unbalanced). The stone hero's story itself is e2e/stone-hero.spec.ts.

const WIDTHS: [number, number][] = [
  [375, 740],
  [390, 844],
  [1126, 960],
  [1280, 800],
  [1440, 900],
  [1920, 1080],
];

/** Pause every hero animation at `t` ms into the cycle. */
async function seek(page: Page, t: number) {
  await page.evaluate((t) => {
    const root = document.querySelector('.stone-hero')!;
    for (const a of document.getAnimations()) {
      const el = (a.effect as KeyframeEffect | null)?.target;
      if (el && root.contains(el)) {
        a.pause();
        a.currentTime = t;
      }
    }
  }, t);
}

/** Per line of the reading: overlapping letter pairs, letters past the line's column or into its chip, and letters
 * outside the line's own band (a wrapped or stray letter). */
const layoutFaults = (page: Page) =>
  page.locator('.sh-line').evaluateAll((lines) =>
    lines.flatMap((line, n) => {
      const ta = line.querySelector('.sh-ta')!.getBoundingClientRect();
      const chip = line.querySelector('.sh-lc')!.getBoundingClientRect();
      const ls = Array.from(line.querySelectorAll('.sh-l')).map((e) => e.getBoundingClientRect());
      const out: string[] = [];
      ls.forEach((a, i) => {
        if (a.right > ta.right + 0.5) out.push(`line ${n + 1} letter ${i} overflows its column by ${(a.right - ta.right).toFixed(1)} px`);
        if (a.right > chip.left - 2) out.push(`line ${n + 1} letter ${i} runs into the chip`);
        if (a.top < ta.top - 4 || a.bottom > ta.bottom + 4) out.push(`line ${n + 1} letter ${i} is off its line`);
        for (let j = i + 1; j < ls.length; j++) {
          const b = ls[j]!;
          const x = Math.min(a.right, b.right) - Math.max(a.left, b.left);
          const y = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
          if (x > 0.5 && y > 0.5) out.push(`line ${n + 1} letters ${i} and ${j} overlap by ${x.toFixed(1)} px`);
        }
      });
      return out;
    }),
  );

test.describe('home hero layout', () => {
  test.beforeEach(() => test.skip(test.info().project.name !== 'desktop', 'sets its own viewports'));

  for (const lang of ['en', 'ta'] as const) {
    test(`every landed letter of the reading has its own slot and every line fits (${lang})`, async ({ page }) => {
      test.setTimeout(120_000);
      if (lang === 'en') await setEnglish(page);
      else await setTamil(page);
      for (const [w, h] of WIDTHS) {
        await page.setViewportSize({ width: w, height: h });
        await page.goto('/');
        const hero = page.getByTestId('stone-hero');
        await expect(hero).toHaveAttribute('data-motion', 'animated');
        await page.evaluate(() => document.fonts.ready);
        await hero.locator('.sh-stage').scrollIntoViewIfNeeded();
        await expect(hero).toHaveAttribute('data-phase', 'running');
        const stage = hero.locator('.sh-stage');
        const landed = Number(await stage.getAttribute('data-t-landed'));
        const words = Number(await stage.getAttribute('data-t-words'));
        // Just landed (run together, as on the stone), then slid apart into words.
        for (const [phase, t] of [['landed', landed + 60], ['words', words + 60]] as const) {
          await seek(page, t);
          expect(await layoutFaults(page), `${w}x${h} ${lang} ${phase}`).toEqual([]);
          const opacities = await page.locator('.sh-l').evaluateAll((els) => els.map((e) => Number(getComputedStyle(e).opacity)));
          expect(Math.min(...opacities), `${w} ${phase}: every letter has landed`).toBeGreaterThan(0.99);
        }
        await expectNoHorizontalScroll(page);
      }
    });
  }

  test('the header is one balanced column, and the first screen shows it, the calls to action and the stone', async ({ page }) => {
    for (const lang of ['en', 'ta'] as const) {
      if (lang === 'en') await setEnglish(page);
      else await setTamil(page);
      for (const [w, h] of WIDTHS) {
        await page.setViewportSize({ width: w, height: h });
        await page.goto('/');
        await page.getByTestId('stone-hero').waitFor();
        await page.waitForFunction(() => document.querySelector('.page')?.getAnimations().every((a) => a.playState === 'finished'));
        await page.addStyleTag({ content: '.mock-banner{display:none!important}' }); // the live site has no demo banner
        const box = async (sel: string) => (await page.locator(sel).first().boundingBox())!;
        const head = page.getByTestId('hero-head');
        const kicker = await box('.hh-kicker');
        const h1 = (await page.getByRole('heading', { level: 1 }).boundingBox())!;
        const sub = await box('.hh-sub');
        const actions = (await page.getByTestId('hero-actions').boundingBox())!;
        const primary = (await page.getByTestId('cta-practice').boundingBox())!;
        const upload = (await page.getByTestId('cta-upload').boundingBox())!;
        await expect(head.locator('.btn-primary')).toHaveCount(1);
        // One column, read top to bottom.
        expect(kicker.y + kicker.height).toBeLessThanOrEqual(h1.y + 1);
        expect(h1.y + h1.height).toBeLessThanOrEqual(sub.y + 1);
        expect(sub.y + sub.height).toBeLessThanOrEqual(actions.y + 1);
        // The two buttons share a row, their tops aligned (wrapped only on a narrow phone).
        if (w >= 560) expect(Math.abs(primary.y - upload.y), `${lang} ${w}: button tops align`).toBeLessThan(2);
        if (w >= 560) {
          // Centred: kicker, headline, subline and the row of actions share one axis.
          const mid = (b: { x: number; width: number }) => b.x + b.width / 2;
          for (const [name, b] of [['kicker', kicker], ['h1', h1], ['sub', sub], ['actions', actions]] as const)
            expect(Math.abs(mid(b) - mid(h1)), `${lang} ${w}: ${name} centred with the headline`).toBeLessThan(3);
        } else {
          // Phones: left-aligned to one edge.
          for (const [name, b] of [['kicker', kicker], ['sub', sub], ['primary', primary]] as const)
            expect(Math.abs(b.x - h1.x), `${lang} ${w}: ${name} left edge`).toBeLessThan(2);
        }
        // First screen: the headline, the primary call to action (above a phone's tab bar) and the stone's start.
        const bottom = await page.evaluate(() => {
          const bar = document.querySelector('.tabbar');
          return bar && getComputedStyle(bar).display !== 'none' ? bar.getBoundingClientRect().top : window.innerHeight;
        });
        expect(primary.y + primary.height, `${lang} ${w}x${h}: call to action on the first screen`).toBeLessThanOrEqual(bottom);
        if (w >= 1000) {
          const photo = (await page.getByTestId('stone-hero').locator('.sh-frame').boundingBox())!;
          expect(bottom - photo.y, `${lang} ${w}x${h}: the stone starts on the first screen`).toBeGreaterThan(200);
        }
      }
    }
  });
});
