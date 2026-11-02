import { expect, test, type Page } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish } from './helpers';

// The home hero (StoneHero.tsx): a real photo, read by Ezhuthu, animated with WAAPI. One cycle is 16 s.

const pageSettled = async (page: Page) => {
  await page.getByTestId('stone-hero').waitFor(); // the app renders after the mock worker starts
  await page.waitForFunction(() => document.querySelector('.page')?.getAnimations().every((a) => a.playState === 'finished'));
};

/** Opacity of every landed letter of the reading (they end at 1 once the cycle has delivered them). */
const letterOpacities = (page: Page) =>
  page.locator('.sh-akw').evaluateAll((els) => els.map((e) => Number(getComputedStyle(e).opacity)));

test.describe('stone hero', () => {
  test('plays the whole story: letters light up, fly into the pipeline and land as the reading', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await expect(hero).toHaveAttribute('data-motion', 'animated');
    await expect(hero).toHaveAttribute('data-phase', 'running');
    // (b) letter boxes light up on the stone
    await expect.poll(() => hero.locator('.sh-box').first().evaluate((n) => Number(getComputedStyle(n).opacity)), { timeout: 5000 }).toBeGreaterThan(0.9);
    // (c) glowing fragments are in flight
    await expect.poll(() => hero.locator('.sh-frag').evaluateAll((els) => els.filter((e) => Number(getComputedStyle(e).opacity) > 0.5).length), { timeout: 8000 }).toBeGreaterThan(3);
    // (d) every letter lands, (e) then the verdict
    await expect.poll(async () => Math.min(...(await letterOpacities(page))), { timeout: 12_000 }).toBeGreaterThan(0.99);
    await expect.poll(() => hero.locator('.sh-review').evaluate((n) => Number(getComputedStyle(n).opacity)), { timeout: 4000 }).toBeGreaterThan(0.99);
    await expect(hero.locator('.sh-review')).toHaveText('Under 0.5, so this reading goes to expert review.');
    await expect(hero.locator('p[lang="ta"]')).toHaveCount(4);
    await expect(page.getByTestId('hero-credit')).toContainText('Richard Mortel');
    await expectNoHorizontalScroll(page);
  });

  test('does not shift the layout, and Pause / Replay work from the keyboard', async ({ page }) => {
    await setEnglish(page);
    await page.addInitScript(() => {
      (window as unknown as { __cls: number }).__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[])
          if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
      }).observe({ type: 'layout-shift', buffered: true });
    });
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await pageSettled(page);
    const box1 = await hero.boundingBox();
    await page.waitForTimeout(9000); // through the flight and the landing
    const box2 = await hero.boundingBox();
    expect(box2).toEqual(box1);
    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    expect(cls, 'cumulative layout shift on the home page').toBeLessThan(0.02);

    const toggle = page.getByTestId('stone-toggle');
    await toggle.focus();
    await page.keyboard.press('Enter');
    await expect(toggle).toHaveAttribute('aria-pressed', 'true');
    await expect(hero).toHaveAttribute('data-phase', 'paused');
    const t1 = await hero.locator('.sh-stage').evaluate((n) => n.getAnimations().map((a) => a.currentTime));
    await page.waitForTimeout(600);
    const t2 = await hero.locator('.sh-stage').evaluate((n) => n.getAnimations().map((a) => a.currentTime));
    expect(t2).toEqual(t1);
    await page.keyboard.press('Enter');
    await expect(hero).toHaveAttribute('data-phase', 'running');

    await page.getByTestId('stone-replay').focus();
    await page.keyboard.press('Enter');
    // Replay starts a fresh cycle: the letters are hidden again for a few seconds.
    await expect.poll(async () => Math.max(...(await letterOpacities(page))), { timeout: 2000 }).toBeLessThan(0.01);
  });

  test('pauses when scrolled out of view', async ({ page }) => {
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await expect(hero).toHaveAttribute('data-phase', 'running');
    await page.getByTestId('sample-gallery').scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await expect(hero).toHaveAttribute('data-phase', 'paused');
    await page.evaluate(() => window.scrollTo(0, 0));
    await expect(hero).toHaveAttribute('data-phase', 'running');
  });

  test('keeps a smooth frame rate while the fragments fly', async ({ page }) => {
    await page.goto('/');
    await pageSettled(page);
    await page.getByTestId('stone-replay').click();
    // Sample frame times from the lift-off through the landing (about 4.5 s to 10 s into the cycle).
    const deltas = await page.evaluate(
      () =>
        new Promise<number[]>((resolve) => {
          const out: number[] = [];
          let last = 0;
          const t0 = performance.now();
          const tick = (t: number) => {
            if (t - t0 > 4500) {
              if (last) out.push(t - last);
              last = t;
            }
            if (t - t0 < 10_000) requestAnimationFrame(tick);
            else resolve(out);
          };
          requestAnimationFrame(tick);
        }),
    );
    deltas.sort((a, b) => a - b);
    const p95 = deltas[Math.floor(deltas.length * 0.95)]!;
    // Headless Chromium on a shared CI box: allow some slack over 16.7 ms, but catch real jank.
    expect(p95, `p95 frame time ${p95.toFixed(1)} ms over ${deltas.length} frames`).toBeLessThan(34);
  });

  test('shows the composed final frame under reduced motion', async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: 'reduce' });
    await ctx.addInitScript(() => window.localStorage.setItem('ezhuthu.lang', 'en'));
    const page = await ctx.newPage();
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await expect(hero).toHaveAttribute('data-motion', 'static');
    await expect(page.getByTestId('stone-toggle')).toHaveCount(0);
    expect(Math.min(...(await letterOpacities(page)))).toBe(1);
    expect(await hero.locator('.sh-box').evaluateAll((els) => els.every((e) => Number(getComputedStyle(e).opacity) > 0.5))).toBe(true);
    await expect(hero.locator('.sh-flight')).toBeHidden();
    const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
    expect(running).toBe(0);
    await ctx.close();
  });

  test('reads well in dark mode', async ({ browser }) => {
    const ctx = await browser.newContext({ colorScheme: 'dark', reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    await page.goto('/');
    const stage = page.getByTestId('stone-hero').locator('.sh-stage');
    await expect(stage).toBeVisible();
    const [ink, bg] = await stage.evaluate((n) => [getComputedStyle(n.querySelector('.sh-out-head')!).color, getComputedStyle(document.body).backgroundColor]);
    expect(ink).not.toBe(bg);
    await ctx.close();
  });
});

test.describe('stone hero on a small phone (375 x 740)', () => {
  test.use({ viewport: { width: 375, height: 740 } });
  test('leads the page: the stone is on screen above the heading, no horizontal scroll', async ({ page }) => {
    for (const lang of ['ta', 'en'] as const) {
      if (lang === 'en') await setEnglish(page);
      await page.goto('/');
      const hero = page.getByTestId('stone-hero');
      await expect(hero).toHaveAttribute('data-motion', 'animated');
      await pageSettled(page);
      const photo = (await hero.locator('.sh-frame').boundingBox())!;
      const tabbarTop = await page.evaluate(() => {
        const bar = document.querySelector('.tabbar');
        return bar && getComputedStyle(bar).display !== 'none' ? bar.getBoundingClientRect().top : window.innerHeight;
      });
      expect(photo.y, `${lang}: photo starts on screen`).toBeGreaterThanOrEqual(0);
      expect(photo.y + photo.height, `${lang}: photo ends above the tab bar`).toBeLessThanOrEqual(tabbarTop);
      const h1 = (await page.getByRole('heading', { level: 1 }).boundingBox())!;
      expect(h1.y).toBeGreaterThan(photo.y);
      // The pipeline is a row under the photo on a phone.
      const nodes = await hero.locator('.sh-node-dot').evaluateAll((els) => els.map((e) => e.getBoundingClientRect().top));
      expect(Math.max(...nodes) - Math.min(...nodes)).toBeLessThan(2);
      await expectNoHorizontalScroll(page);
    }
  });
});
