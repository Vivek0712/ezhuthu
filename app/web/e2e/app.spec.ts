import { expect, test } from '@playwright/test';
import { expectFontsLoaded, expectNoHorizontalScroll, glyphWidth, gotoNav, setEnglish } from './helpers';

test.describe('home and language', () => {
  test('defaults to Tamil and renders Tamil, Brahmi and Grantha with the shipped web fonts', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ta');
    await expect(page.getByRole('heading', { level: 1 })).toContainText('கல்வெட்டைப் படிக்கக் கற்றுக்கொள்ளுங்கள்');
    await expect(page.getByTestId('stone-hero')).toBeVisible();
    await expect(page.getByTestId('evolution-hero')).toBeAttached();
    await expect(page.getByTestId('mock-banner')).toBeVisible();
    await expectFontsLoaded(page, [
      { family: 'Noto Sans Tamil', sample: 'க' },
      { family: 'Noto Serif Tamil', sample: 'க' },
      { family: 'Noto Sans Brahmi', sample: '\u{11013}' },
      { family: 'Noto Sans Grantha', sample: '\u{11315}' },
    ]);
    // Distinct letters get distinct advances in the real font (a tofu fallback gives identical boxes).
    const [ka, nnna] = [await glyphWidth(page, 'Noto Sans Brahmi', '\u{11013}'), await glyphWidth(page, 'Noto Sans Brahmi', '\u{11037}')];
    expect(ka).toBeGreaterThan(0);
    expect(ka).not.toBe(nnna);
    await expectNoHorizontalScroll(page);
  });

  test('switches to English and remembers it', async ({ page }) => {
    await page.goto('/');
    await page.getByTestId('lang-toggle').click();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Learn to read the stone. Help read the backlog.');
    await page.reload();
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });
});

test.describe('practice (was learn)', () => {
  test('Tamil-Brahmi lesson: hint in Tamil, then advance', async ({ page }) => {
    await page.goto('/');
    await gotoNav(page, 'பயிற்சி');
    await page.getByTestId('level-L5').click();
    await page.getByTestId('start-lesson').click();
    const tile = page.getByTestId('glyph-tile');
    await expect(tile).toHaveAttribute('data-level', 'L5');
    await expect(tile.locator('.script-brahmi')).toHaveText('\u{11013}');
    await page.getByTestId('answer-input').fill('ம');
    await page.getByTestId('check-answer').click();
    await expect(page.getByTestId('feedback')).toContainText('குறிப்பு');
    await page.getByTestId('answer-input').fill('க');
    await page.getByTestId('check-answer').click();
    await expect(page.getByTestId('feedback')).toContainText('சரி');
    await page.getByTestId('next-item').click();
    await expect(page.getByTestId('item-counter')).toContainText('2');
    await expect(page.getByTestId('lesson-context')).toContainText('மாங்குளம்');
    await expectNoHorizontalScroll(page);
  });

  test('Vatteluttu lesson renders the SVG glyph', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/practice');
    await page.getByTestId('level-L4').click();
    await page.getByTestId('start-lesson').click();
    const img = page.getByTestId('glyph-tile').locator('img');
    await expect(img).toBeVisible();
    expect(await img.evaluate((el: HTMLImageElement) => el.naturalWidth)).toBeGreaterThan(0);
  });
});

test('restore: fill with confidence, and "experts are unsure" on abstain', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/restore');
  await page.getByTestId('read-tab-type').click();
  await page.getByTestId('use-sample').click();
  await expect(page.getByTestId('gap-count')).toContainText('2');
  await page.getByTestId('restore-submit').click();
  await expect(page.getByTestId('restore-result')).toBeVisible();
  await expect(page.getByTestId('gap-0').getByRole('meter').first()).toHaveAttribute('aria-valuenow', '78');
  await expect(page.getByTestId('gap-1').getByTestId('abstain')).toContainText('Experts are unsure');
  await page.getByTestId('suggest-1').click();
  await page.getByTestId('reading-1').fill('paṉṉiraṇṭ');
  await page.getByTestId('send-1').click();
  await expect(page.getByText('An expert will review it')).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test('progress: pre-test after a lesson shows a score', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/practice');
  await page.getByTestId('start-lesson').click();
  await expect(page.getByTestId('glyph-tile')).toBeVisible();
  await gotoNav(page, 'Progress');
  await page.getByTestId('take-pre').click();
  const answers = ['க', 'ம', 'x', 'x', 'x', 'x', 'x', 'x', 'x', 'x'];
  for (const [i, a] of answers.entries()) {
    await expect(page.getByTestId('assessment-counter')).toHaveText(`${i + 1} / 10`);
    await page.getByTestId('assessment-input').fill(a);
    await page.getByTestId('assessment-next').click();
  }
  await expect(page.getByTestId('pre-score')).toHaveText('20%');
  await expect(page.getByTestId('post-score')).toContainText('not taken');
});

test('test page: sign-in gate, built-in benchmark, JSONL upload', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/benchmark');
  await expect(page.getByTestId('auth-gate')).toBeVisible();
  await page.getByTestId('auth-gate').getByRole('button', { name: 'Sign in' }).click();
  await page.getByTestId('run-benchmark').click();
  await expect(page.getByTestId('score-report')).toBeVisible();
  await expect(page.getByTestId('reliability-chart').locator('rect.bar').first()).toBeVisible();
  const rec = {
    id: 'DHARMA_X:1:0', inscription_id: 'DHARMA_X', collection: 'tfa-pallava-epigraphy', age_set: true, split: 'test',
    line_n: '1', left: 'kō vicaiya ', right: 'parumaṟku', target: 'nantivikkirama', gap_chars: 14, hard: false,
    source_url: 'https://dharmalekha.info/texts/DHARMA_X',
  };
  await page.getByTestId('jsonl-file').setInputFiles({
    name: 'items.jsonl',
    mimeType: 'application/x-ndjson',
    buffer: Buffer.from(`${JSON.stringify(rec)}\n${JSON.stringify({ ...rec, id: 'DHARMA_X:1:1' })}\n`),
  });
  await expect(page.getByTestId('jsonl-report')).toContainText('2 valid records');
  await page.getByTestId('evaluate-upload').click();
  await expect(page.getByTestId('score-report').locator('.stat').first()).toContainText('2');
});

test('review queue: expert approves an item', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/review');
  await page.getByTestId('auth-gate').getByRole('button', { name: 'Sign in' }).click();
  await page.getByTestId('approve-q-0002').click();
  await expect(page.getByTestId('reviewed')).toContainText('q-0002: approved → para');
});

test('about credits DHARMA and is reachable from navigation', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/');
  await gotoNav(page, 'About');
  await expect(page.getByTestId('credits')).toContainText('CC BY-SA 4.0');
  await expect(page.getByTestId('credits')).toContainText('Built with Strands Agents');
  await expectNoHorizontalScroll(page);
});

test('unknown routes show the bilingual 404 (SPA fallback works)', async ({ page }) => {
  await page.goto('/no/such/page');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('பக்கம் கிடைக்கவில்லை');
});

test.describe('design system and states', () => {
  test('header shows the brand logo; bottom tabs only below 1000 px; no horizontal scroll on any page', async ({ page }) => {
    await page.goto('/');
    const width = page.viewportSize()!.width;
    const visibleLogo = page.getByTestId('brand').locator('img:visible');
    await expect(visibleLogo).toHaveCount(1);
    await expect(visibleLogo).toHaveAttribute('src', width < 560 ? /wordmark-ta-color/ : /lockup-horizontal-color/);
    if (width < 1000) {
      await expect(page.getByTestId('tabbar')).toBeVisible();
      await expect(page.getByRole('navigation', { name: 'primary' })).toBeHidden();
    } else {
      await expect(page.getByTestId('tabbar')).toBeHidden();
    }
    for (const path of ['/', '/practice', '/restore', '/progress', '/benchmark', '/review', '/about', '/nope']) {
      await page.goto(path);
      await expect(page.locator('main')).toBeVisible();
      await expectNoHorizontalScroll(page);
    }
  });

  test('dark mode uses the reversed logo and the dark tokens', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/');
    const visibleLogo = page.getByTestId('brand').locator('img:visible');
    await expect(visibleLogo).toHaveAttribute('src', (page.viewportSize()!.width < 560) ? /wordmark-ta-reversed/ : /lockup-horizontal-reversed/);
    const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
    expect(bg).toBe('rgb(19, 16, 13)'); // --ez-bg dark #13100D
  });

  test('keyboard focus is a visible 3 px outline', async ({ page }) => {
    await page.goto('/practice');
    await page.getByTestId('start-lesson').focus();
    await page.keyboard.press('Shift+Tab');
    await page.keyboard.press('Tab');
    const outline = await page.getByTestId('start-lesson').evaluate((el) => {
      const s = getComputedStyle(el);
      return `${s.outlineStyle} ${s.outlineWidth}`;
    });
    expect(outline).toBe('solid 3px');
  });

  test('tutor: "decided by rules" instead of confidence 0%, and the explanation updates after an answer', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/practice');
    await page.getByTestId('level-L5').click();
    await page.getByTestId('start-lesson').click();
    await expect(page.getByTestId('explanation-pending')).toBeVisible();
    await expect(page.getByTestId('lesson-source')).toContainText('CC BY-SA 4.0');
    for (let i = 0; i < 3; i++) {
      await page.getByTestId('answer-input').fill('ம');
      await Promise.all([page.waitForResponse('**/api/answer'), page.getByTestId('check-answer').click()]);
      await expect(page.getByTestId('busy')).toHaveCount(0);
      if (i === 0) {
        await expect(page.getByTestId('explanation')).toContainText('Mangulam caves');
        await expect(page.getByTestId('explanation-updated')).toBeVisible();
        await expect(page.getByTestId('explanation-pending')).toHaveCount(0);
      }
    }
    await expect(page.getByTestId('decided-by-rules')).toHaveText('decided by rules');
    await expect(page.getByTestId('feedback')).not.toContainText('0%');
    await expectNoHorizontalScroll(page);
  });

  test('review: a second review (409) leaves the queue calmly, without an error', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/review');
    await page.getByTestId('auth-gate').getByRole('button', { name: 'Sign in' }).click();
    await page.getByTestId('approve-q-0004').click();
    await expect(page.getByTestId('review-notice')).toContainText('This item is no longer in the queue');
    await expect(page.getByTestId('queue-q-0004')).toHaveCount(0);
    await expect(page.getByRole('alert')).toHaveCount(0);
  });

  test('licence: DHARMA CC BY-SA 4.0 in the footer, restore result and Test page; never CC BY 4.0', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/restore');
    await expect(page.getByTestId('footer-credit')).toHaveText('Inscription texts: DHARMA, CC BY-SA 4.0');
    await page.getByTestId('read-tab-type').click();
    await page.getByTestId('use-sample').click();
    await page.getByTestId('restore-submit').click();
    await expect(page.getByTestId('restore-credit')).toContainText('CC BY-SA 4.0');
    await page.goto('/benchmark');
    await page.getByTestId('auth-gate').getByRole('button', { name: 'Sign in' }).click();
    await expect(page.getByTestId('benchmark-credit')).toContainText('CC BY-SA 4.0');
    for (const path of ['/', '/practice', '/restore', '/about', '/benchmark']) {
      await page.goto(path);
      await expect(page.locator('body')).not.toContainText('CC BY 4.0');
    }
  });

  test('head: favicon, manifest and social preview are served', async ({ page, request }) => {
    await page.goto('/');
    for (const href of ['/favicon.svg', '/favicon-32.png', '/apple-touch-icon-180.png', '/manifest.webmanifest', '/og-image.png', '/icon-maskable-512.png']) {
      const r = await request.get(href);
      expect(r.status(), href).toBe(200);
    }
    await expect(page.locator('meta[property="og:image"]')).toHaveAttribute('content', '/og-image.png');
  });
});
