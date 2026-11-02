import { expect, test, type Page } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish } from './helpers';

// The home hero (StoneHero.tsx): a real photo, read letter by letter by Ezhuthu, then put into words, a phrase in
// today's Tamil and its meaning; animated with WAAPI (~24 s cycle).

const pageSettled = async (page: Page) => {
  await page.getByTestId('stone-hero').waitFor(); // the app renders after the mock worker starts
  await page.waitForFunction(() => document.querySelector('.page')?.getAnimations().every((a) => a.playState === 'finished'));
};
const hideDemoBanner = (page: Page) => page.addStyleTag({ content: '.mock-banner{display:none!important}' });
/** On phones the headline comes first: bring the stone on screen so its cycle starts. */
const showHero = async (page: Page) => {
  const hero = page.getByTestId('stone-hero');
  await hero.locator('.sh-stage').scrollIntoViewIfNeeded();
  await expect(hero).toHaveAttribute('data-phase', 'running');
  return hero;
};

/** Opacity of every letter of the reading (each ends at 1 once it has landed). */
const letterOpacities = (page: Page) => page.locator('.sh-l').evaluateAll((els) => els.map((e) => Number(getComputedStyle(e).opacity)));
const shown = (page: Page, sel: string) => page.locator(sel).evaluateAll((els) => els.filter((e) => Number(getComputedStyle(e).opacity) > 0.5).length);

test.describe('stone hero', () => {
  test('plays the whole story: scan, match cards, cascade, gap, assembly, words, phrase, meaning, verdict', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/');
    await expect(page.getByTestId('stone-hero')).toHaveAttribute('data-motion', 'animated');
    const hero = await showHero(page);
    // (b) the carved letters light up
    await expect.poll(() => hero.locator('.sh-box').first().evaluate((n) => Number(getComputedStyle(n).opacity)), { timeout: 5000 }).toBeGreaterThan(0.9);
    // (c) the first match card: carved glyph -> modern letter, confidence ring
    await expect.poll(() => shown(page, '.sh-card[data-card="0"]'), { timeout: 6000 }).toBe(1);
    await expect(hero.locator('.sh-card[data-card="0"] .sh-card-ta')).toHaveText('கி');
    await expect(hero.locator('.sh-card[data-card="0"] .sh-ring b')).toHaveText('80%');
    // ... then the cascade puts a badge on every box
    const boxes = await hero.locator('.sh-box').count();
    await expect.poll(() => shown(page, '.sh-badge'), { timeout: 8000 }).toBe(boxes);
    // ... all of each badge inside the photo, the bottom line's included (letter and % readable)
    const outside = await hero.locator('.sh-frame').evaluate((f) => {
      const fr = f.getBoundingClientRect();
      return Array.from(f.querySelectorAll('.sh-badge')).filter((b) => {
        const r = b.getBoundingClientRect();
        return r.top < fr.top - 0.5 || r.bottom > fr.bottom + 0.5 || r.left < fr.left - 0.5 || r.right > fr.right + 0.5;
      }).map((b) => { const r = b.getBoundingClientRect(); return `${(b as HTMLElement).dataset.idx}: ${Math.round(r.left - fr.left)},${Math.round(r.top - fr.top)},${Math.round(fr.right - r.right)},${Math.round(fr.bottom - r.bottom)}`; });
    });
    expect(outside).toEqual([]);
    // (d) the gap: the Decider abstains and the badge turns to "?"
    await expect.poll(() => shown(page, '.sh-badge-gap .sh-badge-b'), { timeout: 6000 }).toBe(1);
    // (e) every letter lands, (f) then the verdict
    await expect.poll(async () => Math.min(...(await letterOpacities(page))), { timeout: 12_000 }).toBeGreaterThan(0.99);
    await expect.poll(() => shown(page, '.sh-verdict'), { timeout: 4000 }).toBe(1);
    await expect(hero.locator('.sh-verdict')).toContainText('46 letters matched to modern Tamil');
    // (f) the letters open up into words, each underlined
    const lines = await hero.locator('.sh-wline').count();
    expect(lines).toBeGreaterThan(4);
    await expect.poll(() => shown(page, '.sh-wline'), { timeout: 4000 }).toBe(lines);
    // (g, h) the phrase in today's Tamil, then the meaning in English and in Tamil; the reading pane gives way
    await expect.poll(() => shown(page, '.sh-mean'), { timeout: 6000 }).toBe(1);
    await expect.poll(() => shown(page, '.sh-mean-ta'), { timeout: 6000 }).toBe(1);
    expect(await shown(page, '.sh-read')).toBe(0);
    await expect(hero.locator('.sh-phrase')).toContainText('குளம்');
    await expect(hero.locator('.sh-mean-en')).toContainText('tank');
    await expect(hero.locator('.sh-verdict')).toContainText('11 words');
    await expect(hero.locator('.sh-ta[lang="ta"]')).toHaveCount(4);
    await expect(hero).not.toContainText(/experimental|not checked against/i);
    await expect(page.getByTestId('hero-credit')).toContainText('Richard Mortel');
    await expect(hero).toContainText('Reading by Ezhuthu, built with Strands Agents');
    await expect(hero).toContainText('Meaning by Ezhuthu');
    await expectNoHorizontalScroll(page);
  });

  test('loops without the photo blinking out', async ({ page }) => {
    await page.goto('/');
    await pageSettled(page);
    const hero = await showHero(page);
    // Jump every hero animation to just before the end of the cycle, then let the next cycle start.
    const opacityAcrossSeam = await page.evaluate(async () => {
      const stage = document.querySelector('.sh-stage')!;
      const clock = stage.getAnimations()[0]!;
      const C = Number(clock.effect!.getTiming().duration);
      for (const a of document.getAnimations()) if (a.effect?.getTiming().duration === C) a.currentTime = C - 120;
      const kb = document.querySelector('.sh-kb')!;
      const seen: number[] = [];
      const t0 = performance.now();
      await new Promise<void>((res) => {
        const tick = () => {
          seen.push(Number(getComputedStyle(kb).opacity));
          if (performance.now() - t0 < 600) requestAnimationFrame(tick);
          else res();
        };
        requestAnimationFrame(tick);
      });
      return seen;
    });
    expect(Math.min(...opacityAcrossSeam)).toBeGreaterThan(0.99);
    await expect(hero).toHaveAttribute('data-phase', 'running');
  });

  test('carries the meaning over the loop seam and crossfades it into the next scan', async ({ page }) => {
    await page.goto('/');
    await pageSettled(page);
    await showHero(page);
    const seen = await page.evaluate(async () => {
      const stage = document.querySelector('.sh-stage')!;
      const clock = stage.getAnimations()[0]!;
      const C = Number(clock.effect!.getTiming().duration);
      for (const a of document.getAnimations()) if (a.effect?.getTiming().duration === C) a.currentTime = C - 150;
      const mean = document.querySelector('.sh-mean')!;
      const read = document.querySelector('.sh-read')!;
      const out: { t: number; mean: number; read: number }[] = [];
      const t0 = performance.now();
      await new Promise<void>((res) => {
        const tick = () => {
          out.push({ t: performance.now() - t0, mean: Number(getComputedStyle(mean).opacity), read: Number(getComputedStyle(read).opacity) });
          if (performance.now() - t0 < 2200) requestAnimationFrame(tick);
          else res();
        };
        requestAnimationFrame(tick);
      });
      return out;
    });
    // On screen through the seam and the first moments of the next cycle; gone, with the reading back, by ~1.5 s.
    expect(Math.min(...seen.filter((s) => s.t < 600).map((s) => s.mean))).toBeGreaterThan(0.99);
    const late = seen.filter((s) => s.t > 1900);
    expect(Math.max(...late.map((s) => s.mean))).toBeLessThan(0.01);
    expect(Math.min(...late.map((s) => s.read))).toBeGreaterThan(0.99);
  });

  test('desktop composition: the photo is the hero, the reading sits beside it', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop', 'desktop layout');
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await pageSettled(page);
    const stage = (await hero.locator('.sh-stage').boundingBox())!;
    const photo = (await hero.locator('.sh-frame').boundingBox())!;
    const out = (await hero.locator('.sh-out').boundingBox())!;
    expect(photo.width / stage.width).toBeGreaterThan(0.58);
    expect(out.x).toBeGreaterThan(photo.x + photo.width);
    // No empty band: the pipeline sits right under the photo's caption, and the stage ends soon after it.
    const pipe = (await hero.locator('.sh-pipe').boundingBox())!;
    const sum = (await hero.locator('.sh-sum').boundingBox())!;
    expect(pipe.y - (photo.y + photo.height)).toBeLessThan(70);
    expect(stage.y + stage.height - (pipe.y + pipe.height)).toBeLessThan(sum.height + 90);
    // The reading and meaning column is no taller than the stone and the pipeline beside it.
    expect(out.height).toBeLessThan(pipe.y + pipe.height - photo.y + 40);
    // The browser picks a photo at least as wide as it is drawn (srcset sizes match the layout).
    const { natural, drawn, dpr } = await hero.locator('.sh-kb > picture img').evaluate((img: HTMLImageElement) => ({ natural: img.naturalWidth, drawn: img.getBoundingClientRect().width, dpr: window.devicePixelRatio }));
    expect(natural).toBeGreaterThanOrEqual(Math.min(1568, drawn * dpr * 0.98));
    // Row confidence chips are aligned in one right-hand column.
    const xs = await hero.locator('.sh-lc').evaluateAll((els) => els.map((e) => Math.round(e.getBoundingClientRect().right)));
    expect(new Set(xs).size).toBe(1);
    // Each line of the reading stays on one line (no orphaned letters).
    const heights = await hero.locator('.sh-ta').evaluateAll((els) => els.map((e) => e.getBoundingClientRect().height));
    for (const h of heights) expect(h).toBeLessThan(heights[0]! * 1.4);
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
    await pageSettled(page);
    const hero = await showHero(page);
    const box1 = await hero.boundingBox();
    await page.waitForTimeout(9000); // through the match and the gap stage
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
    // Replay starts a fresh cycle: the letters are hidden again for several seconds.
    await expect.poll(async () => Math.max(...(await letterOpacities(page))), { timeout: 2000 }).toBeLessThan(0.01);
  });

  test('pauses when scrolled out of view', async ({ page }) => {
    await page.goto('/');
    await pageSettled(page);
    const hero = await showHero(page);
    await page.getByTestId('sample-gallery').scrollIntoViewIfNeeded();
    await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight));
    await expect(hero).toHaveAttribute('data-phase', 'paused');
    await hero.locator('.sh-stage').scrollIntoViewIfNeeded();
    await expect(hero).toHaveAttribute('data-phase', 'running');
  });

  test('keeps a smooth frame rate through the cascade and the assembly', async ({ page }) => {
    await page.goto('/');
    await pageSettled(page);
    await showHero(page);
    await page.getByTestId('stone-replay').click();
    // Sample frame times from the cascade through the assembly (about 7 s to 14 s into the cycle).
    const deltas = await page.evaluate(
      () =>
        new Promise<number[]>((resolve) => {
          const out: number[] = [];
          let last = 0;
          const t0 = performance.now();
          const tick = (t: number) => {
            if (t - t0 > 7000) {
              if (last) out.push(t - last);
              last = t;
            }
            if (t - t0 < 14_000) requestAnimationFrame(tick);
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

  test('shows the composed static frame under reduced motion', async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: 'reduce' });
    await ctx.addInitScript(() => window.localStorage.setItem('ezhuthu.lang.v2', 'en'));
    const page = await ctx.newPage();
    await page.goto('/');
    const hero = page.getByTestId('stone-hero');
    await expect(hero).toHaveAttribute('data-motion', 'static');
    await expect(page.getByTestId('stone-toggle')).toHaveCount(0);
    expect(Math.min(...(await letterOpacities(page)))).toBe(1);
    expect(await hero.locator('.sh-box').evaluateAll((els) => els.every((e) => Number(getComputedStyle(e).opacity) > 0.5))).toBe(true);
    await expect(hero.locator('.sh-card:visible')).toHaveCount(2);
    // The static frame shows the words, the phrase and the meaning together.
    await expect(hero.locator('.sh-mean')).toBeVisible();
    expect(await shown(page, '.sh-mean-en')).toBe(1);
    expect(await shown(page, '.sh-badge')).toBe(await hero.locator('.sh-box').count());
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
  test('the headline and calls to action share the first screen; the stone follows, full width', async ({ page }) => {
    for (const lang of ['ta', 'en'] as const) {
      if (lang === 'en') await setEnglish(page);
      await page.goto('/');
      const hero = page.getByTestId('stone-hero');
      await expect(hero).toHaveAttribute('data-motion', 'animated');
      await pageSettled(page);
      await hideDemoBanner(page); // the live site has no demo banner
      const tabbarTop = await page.evaluate(() => {
        const bar = document.querySelector('.tabbar');
        return bar && getComputedStyle(bar).display !== 'none' ? bar.getBoundingClientRect().top : window.innerHeight;
      });
      const h1 = (await page.getByRole('heading', { level: 1 }).boundingBox())!;
      const cta = (await page.getByTestId('cta-upload').boundingBox())!;
      expect(h1.y, `${lang}: heading on screen`).toBeGreaterThanOrEqual(0);
      expect(cta.y + cta.height, `${lang}: first call to action above the tab bar`).toBeLessThanOrEqual(tabbarTop);
      const photo = (await hero.locator('.sh-frame').boundingBox())!;
      expect(photo.y).toBeGreaterThan(cta.y);
      expect(photo.width).toBeGreaterThanOrEqual(375 - 48);
      // The pipeline is a row under the photo on a phone.
      const nodes = await hero.locator('.sh-node-dot').evaluateAll((els) => els.map((e) => e.getBoundingClientRect().top));
      expect(Math.max(...nodes) - Math.min(...nodes)).toBeLessThan(2);
      await expectNoHorizontalScroll(page);
    }
  });
});
