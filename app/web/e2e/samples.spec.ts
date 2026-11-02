import { expect, test } from '@playwright/test';
import samples from '../src/samples/samples.json' with { type: 'json' };
import { expectNoHorizontalScroll, setEnglish } from './helpers';

// Try-it samples and the animated hero, against the mock build (MSW answers /api/*).
const pallava = samples.find((s) => s.learn_level === 'L3')!;
const chola = samples.find((s) => s.era === 'chola')!;

test.describe('try-it samples', () => {
  test('sample -> restore -> learn, in English', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/');
    const gallery = page.getByTestId('sample-gallery');
    await expect(gallery.getByRole('article')).toHaveCount(samples.length);
    await expectNoHorizontalScroll(page);

    // One click from the gallery to a filled restore form.
    const card = page.getByTestId(`sample-${chola.id}`);
    await card.scrollIntoViewIfNeeded();
    await expect(card.getByText(chola.why_en)).toBeVisible();
    await card.getByRole('link', { name: 'Restore this' }).click();
    await expect(page).toHaveURL(new RegExp(`/restore\\?sample=${chola.id}$`));
    await expect(page.getByTestId('restore-input')).toHaveValue(chola.text_iso);
    await expect(page.getByTestId('gap-count')).toContainText(String(chola.gaps));
    await expect(page.getByTestId('restore-sample-source')).toContainText(chola.title_en);
    await page.getByTestId('restore-submit').click();
    await expect(page.getByTestId('restore-result')).toBeVisible();
    await expect(page.locator('[data-testid^="gap-"]').filter({ has: page.locator('h3') })).toHaveCount(chola.gaps);
    await expect(page.getByTestId('restore-credit')).toContainText('CC BY-SA 4.0');

    // Back to the gallery, then "Learn with this" starts a lesson on that inscription at its level.
    await page.goto('/#samples');
    await page.getByTestId('era-pallava').click();
    await page.getByTestId(`learn-${pallava.id}`).click();
    await expect(page).toHaveURL(/\/learn\?inscription=/);
    await expect(page.getByRole('heading', { level: 1, name: pallava.edition_title })).toBeVisible();
    await expect(page.getByTestId('lesson-source')).toContainText('CC BY-SA 4.0');
    await expect(page.getByTestId('glyph-tile')).toHaveAttribute('data-level', 'L3');
    await Promise.all([page.waitForResponse('**/api/answer'), (async () => {
      await page.getByTestId('answer-input').fill('க');
      await page.getByTestId('check-answer').click();
    })()]);
    await expect(page.getByTestId('feedback')).toBeVisible();
  });

  test('Tamil readers get the Tamil text; filters work on a phone too', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('cta-samples').click();
    await expect(page.getByRole('heading', { level: 2, name: 'உண்மையான கல்வெட்டை முயலுங்கள்' })).toBeFocused();
    await page.getByTestId('era-pandya').click();
    await expect(page.getByTestId('sample-gallery').getByRole('article')).toHaveCount(samples.filter((s) => s.era === 'pandya').length);
    await expectNoHorizontalScroll(page);
    const s = samples.find((x) => x.era === 'pandya')!;
    await page.getByTestId(`restore-${s.id}`).click();
    await expect(page.getByTestId('restore-input')).toHaveValue(s.text_tamil);
  });

  test('the primary CTA says what it does and lands on a form the reader can use', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/');
    const cta = page.getByTestId('cta-upload');
    await expect(cta).toHaveText('Upload a photo');
    await cta.click();
    await expect(page).toHaveURL(/\/restore$/);
    // The promise is kept: the photo tab with a file input, a camera input and sample plates.
    await expect(page.getByTestId('read-tab-photo')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('choose-photo')).toBeVisible();
    await expect(page.getByTestId('photo-input')).toHaveAttribute('type', 'file');
    await expect(page.getByTestId('sample-stone-tamil')).toBeVisible();
    // Typing is still one tab away.
    await page.getByTestId('read-tab-type').click();
    await expect(page.getByTestId('restore-input')).toBeEditable();
  });
});

test.describe('animated hero on a small phone (375 x 740)', () => {
  test.use({ viewport: { width: 375, height: 740 } });
  test('is the first thing on screen, above the tab bar, and still animating', async ({ page }) => {
    for (const lang of ['ta', 'en'] as const) {
      if (lang === 'en') await setEnglish(page);
      await page.goto('/');
      const hero = page.getByTestId('evolution-hero');
      await expect(hero).toHaveAttribute('data-motion', 'animated');
      await page.waitForFunction(() => document.querySelector('.page')!.getAnimations().every((a) => a.playState === 'finished'));
      const tabbarTop = await page.evaluate(() => {
        const bar = document.querySelector('.tabbar');
        return bar && getComputedStyle(bar).display !== 'none' ? bar.getBoundingClientRect().top : window.innerHeight;
      });
      const well = (await hero.locator('.evo-well').boundingBox())!;
      expect(well.y, `${lang}: well starts on screen`).toBeGreaterThanOrEqual(0);
      expect(well.y + well.height, `${lang}: well ends above the tab bar`).toBeLessThanOrEqual(tabbarTop);
      const label = (await hero.locator('.evo-labels').boundingBox())!;
      expect(label.y + label.height, `${lang}: stage label above the tab bar`).toBeLessThanOrEqual(tabbarTop);
      // The hero sits above the heading on a phone, and the primary CTA is still reachable without horizontal scroll.
      const h1 = (await page.getByRole('heading', { level: 1 }).boundingBox())!;
      expect(h1.y).toBeGreaterThan(well.y);
      await expect(hero.locator('.evo-frame').first()).toHaveCSS('animation-play-state', 'running');
      await expectNoHorizontalScroll(page);
    }
  });
});

test.describe('animated hero', () => {
  test('animates without layout shift and can be paused', async ({ page }) => {
    await setEnglish(page);
    await page.addInitScript(() => {
      (window as unknown as { __cls: number }).__cls = 0;
      new PerformanceObserver((list) => {
        for (const e of list.getEntries() as (PerformanceEntry & { value: number; hadRecentInput: boolean })[])
          if (!e.hadRecentInput) (window as unknown as { __cls: number }).__cls += e.value;
      }).observe({ type: 'layout-shift', buffered: true });
    });
    await page.goto('/');
    const hero = page.getByTestId('evolution-hero');
    await expect(hero).toHaveAttribute('data-motion', 'animated');
    // Let the page's own entrance (a transform, not a layout change) finish before measuring.
    await page.waitForFunction(() => document.querySelector('.page')!.getAnimations().every((a) => a.playState === 'finished'));
    const box1 = await hero.boundingBox();
    // The stage changes frames (one every 2.8 s); the box must not move or resize meanwhile.
    const opacityOf = (i: number) => hero.locator('.evo-frame').nth(i).evaluate((n) => Number(getComputedStyle(n).opacity));
    await expect.poll(() => opacityOf(0)).toBeGreaterThan(0.9);
    await expect.poll(() => opacityOf(1), { timeout: 8000 }).toBeGreaterThan(0.9);
    const box2 = await hero.boundingBox();
    expect(box2).toEqual(box1);
    const cls = await page.evaluate(() => (window as unknown as { __cls: number }).__cls);
    expect(cls, 'cumulative layout shift on the home page').toBeLessThan(0.02);

    await page.getByTestId('evo-toggle').click();
    await expect(hero).toHaveAttribute('data-paused', 'true');
    const state = await hero.locator('.evo-frame').first().evaluate((n) => getComputedStyle(n).animationPlayState);
    expect(state).toBe('paused');
    await expectNoHorizontalScroll(page);
  });

  test('shows a static frame when the visitor prefers reduced motion', async ({ browser }) => {
    const ctx = await browser.newContext({ reducedMotion: 'reduce' });
    const page = await ctx.newPage();
    await page.goto('/');
    const hero = page.getByTestId('evolution-hero');
    await expect(hero).toHaveAttribute('data-motion', 'static');
    await expect(hero.locator('.evo-frame')).toHaveCount(0);
    await expect(hero.locator('.evo-pip-label')).toHaveCount(5);
    await expect(page.getByTestId('evo-toggle')).toHaveCount(0);
    const running = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === 'running').length);
    expect(running).toBe(0);
    await ctx.close();
  });

  test('works in dark mode', async ({ browser }) => {
    const ctx = await browser.newContext({ colorScheme: 'dark' });
    const page = await ctx.newPage();
    await page.goto('/');
    const fill = await page.getByTestId('evo-word').locator('path').last().evaluate((n) => getComputedStyle(n).fill);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(fill).not.toBe(bg);
    await expect(page.getByTestId('evolution-hero')).toBeVisible();
    await ctx.close();
  });
});
