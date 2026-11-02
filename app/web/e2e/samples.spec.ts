import { expect, test } from '@playwright/test';
import samples from '../src/samples/samples.json' with { type: 'json' };
import { expectNoHorizontalScroll, setEnglish, setTamil } from './helpers';

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
    // Tamil script first, with the English-letter form under it, and the steps explained before the first run.
    await expect(page.getByTestId('restore-input')).toHaveValue(chola.text_tamil);
    await expect(page.getByTestId('input-preview')).toContainText('How it is written in English letters');
    await expect(page.getByTestId('gap-count')).toContainText(String(chola.gaps));
    await expect(page.getByTestId('restore-sample-source')).toContainText(chola.title_en);
    await expect(page.getByTestId('restore-sample-about')).toContainText(chola.why_en);
    await expect(page.getByTestId('restore-how').getByRole('listitem')).toHaveCount(4);
    await expect(page.getByTestId('restore-how').getByRole('listitem').nth(2)).toBeVisible();
    // The technical options are folded away under "Advanced options".
    await expect(page.getByTestId('restore-script')).toBeHidden();
    await page.getByTestId('restore-advanced').locator('summary').click();
    await expect(page.getByTestId('restore-script')).toBeVisible();
    await page.getByTestId('restore-submit').click();
    await expect(page.getByRole('button', { name: 'Restore missing letters' })).toBeVisible();
    await expect(page.getByTestId('restore-result')).toBeVisible();
    // One plain sentence first, then the line in Tamil with the English letters under it; the explainer folds away.
    await expect(page.getByTestId('restore-summary')).toContainText(chola.gaps === 1 ? /letters? (was|were) missing/ : /missing in \d+ places/);
    await expect(page.getByTestId('restored-tamil')).toBeVisible();
    await expect(page.getByTestId('restored-iso')).toContainText('How it is written in English letters');
    await expect(page.getByTestId('restore-how').getByRole('listitem').first()).toBeHidden();
    // Model ids only under "Technical details"; candidates carry plain labels.
    await expect(page.getByTestId('restore-result').getByText(/us\.anthropic/)).toBeHidden();
    await page.getByTestId('options-0').locator('summary').first().click();
    await expect(page.getByTestId('options-0').getByTestId('cand-source').first()).toHaveText(/AI proposal|Found in similar inscriptions/);
    await expect(page.locator('[data-testid^="gap-"]').filter({ has: page.locator('h3') })).toHaveCount(chola.gaps);
    await expect(page.getByTestId('restore-credit')).toContainText('CC BY-SA 4.0');
    // A masked sample: after the result, what the published edition reads and how the replayed live answer compares.
    expect(chola.group).toBe('masked');
    const reveal = page.getByTestId('edition-reveal');
    await expect(reveal).toBeVisible();
    await expect(reveal).toHaveAttribute('data-state', chola.recorded!.gaps[0]!.outcome);
    await expect(reveal.getByTestId('reveal-edition')).toContainText(chola.edition_reading!.text_iso);
    await expect(reveal.getByRole('link', { name: /DHARMA/ })).toHaveAttribute('href', chola.dharma_url);

    // Back to the gallery, then "Practise with this" starts a lesson on that inscription at its level.
    await page.goto('/#samples');
    await page.getByTestId('era-pallava').click();
    await page.getByTestId(`learn-${pallava.id}`).click();
    await expect(page).toHaveURL(/\/practice\?inscription=/);
    await expect(page.getByRole('heading', { level: 1, name: pallava.edition_title })).toBeVisible();
    await expect(page.getByTestId('lesson-source')).toContainText('CC BY-SA 4.0');
    await expect(page.getByTestId('glyph-tile')).toHaveAttribute('data-level', 'L3');
    await Promise.all([page.waitForResponse('**/api/answer'), (async () => {
      await page.getByTestId('answer-input').fill('க');
      await page.getByTestId('check-answer').click();
    })()]);
    await expect(page.getByTestId('feedback')).toBeVisible();
  });

  test('unsolved passages are a separate group whose result explains why there is nothing to compare', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/');
    const group = page.getByTestId('sample-group-unsolved');
    await group.scrollIntoViewIfNeeded();
    await expect(group.getByRole('heading', { name: 'Unsolved: even the editors left this blank' })).toBeVisible();
    const s = samples.find((x) => x.group === 'unsolved')!;
    await group.getByTestId(`restore-${s.id}`).click();
    await page.getByTestId('restore-submit').click();
    await expect(page.getByTestId('edition-reveal')).toHaveAttribute('data-state', 'unsolved');
    await expect(page.getByTestId('abstain').first()).toBeVisible();
  });

  test('Tamil readers get the Tamil text; filters work on a phone too', async ({ page }) => {
    await setTamil(page);
    await page.goto('/');
    await page.getByTestId('cta-samples').click();
    await expect(page.getByRole('heading', { level: 2, name: 'உண்மையான கல்வெட்டை முயலுங்கள்' })).toBeFocused();
    await page.getByTestId('era-pandya').click();
    await expect(page.getByTestId('sample-gallery').getByRole('article')).toHaveCount(samples.filter((s) => s.era === 'pandya').length);
    await expectNoHorizontalScroll(page);
    const s = samples.find((x) => x.era === 'pandya')!;
    await page.getByTestId(`restore-${s.id}`).click();
    await expect(page.getByTestId('restore-input')).toHaveValue(s.text_tamil);
    await expect(page.getByTestId('restore-how')).toContainText('அழுத்தினால் என்ன நடக்கும்');
    await page.getByTestId('restore-submit').click();
    await expect(page.getByTestId('restore-summary')).toContainText('விடுபட்டிருந்த');
    await expect(page.getByTestId('restored-iso')).toContainText('ஆங்கில எழுத்துகளில்');
    await expectNoHorizontalScroll(page);
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

// The era-evolution strip moved below the stone hero (positioning C); it still animates, pauses and has a static frame.
test.describe('era-evolution strip', () => {
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
    await hero.scrollIntoViewIfNeeded();
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
