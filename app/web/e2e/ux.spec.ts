import { expect, test, type Locator, type Page } from '@playwright/test';
import formulas from '../src/practice/banks/formulas.json' with { type: 'json' };
import gaps from '../src/practice/banks/gaps.json' with { type: 'json' };
import letters from '../src/practice/banks/letters.json' with { type: 'json' };
import words from '../src/practice/banks/words.json' with { type: 'json' };
import { expectNoHorizontalScroll, gotoNav, setEnglish, setTamil } from './helpers';

const ANSWER = new Map<string, number>(
  [letters, words, gaps, formulas].flatMap((b) => (b.items as { id: string; answer: number }[]).map((i) => [i.id, i.answer] as [string, number])),
);

// The UX revamp: home sections, instant practice (a full session and the timed trial) and How it works, in English
// and Tamil, on desktop and phone (both Playwright projects). UX_SHOTS=<dir> also saves review screenshots there.
const SHOTS = process.env.UX_SHOTS;

async function shot(page: Page, name: string, project: string, fullPage = false) {
  if (!SHOTS) return;
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(1200); // let the entrance animations finish
  await page.screenshot({ path: `${SHOTS}/${name}-${project}-en.png`, fullPage });
}

/** Answer the open question with the first option; returns whether that was the expected answer. */
async function answerFirst(q: Locator): Promise<boolean> {
  await q.getByTestId('option-0').click();
  await expect(q.getByTestId('q-feedback')).toBeVisible();
  return (await q.getByTestId('q-feedback').getAttribute('data-right')) === 'true';
}

for (const lang of ['en', 'ta'] as const) {
  const T = lang === 'en'
    ? { practice: 'Practice', how: /How it works|How/, howTitle: 'How Ezhuthu reads an inscription', done: 'Session complete', trial: 'Your score', limits: '259 of 413' }
    : { practice: 'பயிற்சி', how: /எப்படி இயங்குகிறது|விளக்கம்/, howTitle: 'எழுத்து ஒரு கல்வெட்டை எப்படிப் படிக்கிறது', done: 'பயிற்சி முடிந்தது', trial: 'உங்கள் மதிப்பெண்', limits: '413-இல் 259' };

  test.describe(`UX revamp (${lang})`, () => {
    test.beforeEach(async ({ page }) => {
      await (lang === 'en' ? setEnglish(page) : setTamil(page));
    });

    test('home: hero, what you can do, a question to answer here, how it works, scholars', async ({ page }, info) => {
      await page.goto('/');
      await expect(page.getByTestId('stone-hero')).toBeVisible();
      await expect(page.getByTestId('hero-actions').locator('.btn-primary')).toHaveCount(1);
      // Sections in order, and no sample gallery on home (it lives on Restore).
      const ys = [];
      for (const id of ['stone-hero', 'home-features', 'home-practice', 'home-how', 'scholars']) ys.push((await page.getByTestId(id).boundingBox())!.y);
      expect([...ys].sort((a, b) => a - b)).toEqual(ys);
      await expect(page.getByTestId('sample-gallery')).toHaveCount(0);
      await expect(page.getByTestId('home-samples-link')).toHaveAttribute('href', '/restore#samples');
      // Four feature cards, each with Tamil script and English letters.
      for (const f of ['practice', 'restore', 'read', 'how']) {
        const card = page.getByTestId(`feature-${f}`);
        await expect(card.locator('.bi-ta')).toBeVisible();
        await expect(card.locator('.bi-iso')).toBeVisible();
      }
      // The primary call to action lands on the question; it is answered within seconds.
      await page.getByTestId('cta-practice').click();
      const drill = page.getByTestId('mini-drill');
      await expect(drill).toBeInViewport();
      const q = drill.getByTestId('question');
      await answerFirst(q);
      await expect(q.locator('.bi-iso').first()).toBeVisible();
      await drill.getByTestId('mini-next').click();
      await expect(drill.getByTestId('q-feedback')).toHaveCount(0);
      // How it works: five steps with real examples in Tamil and English letters.
      const pipe = page.getByTestId('pipeline');
      await expect(pipe.locator('.pipe-step')).toHaveCount(5);
      await expect(pipe.getByTestId('pipe-reader').locator('.bi-ta')).toContainText('[?2]');
      await expect(pipe.getByTestId('pipe-reader').locator('.bi-iso')).toContainText('[?2]');
      await expect(page.getByTestId('scholars-benchmark')).toHaveAttribute('href', '/benchmark');
      await expectNoHorizontalScroll(page);
      if (lang === 'en') {
        await page.evaluate(() => window.scrollTo(0, 0));
        await shot(page, 'home', info.project.name);
        await shot(page, 'home-full', info.project.name, true);
      }
    });

    test('the sample link on home opens the gallery on Restore', async ({ page }) => {
      await page.goto('/');
      await page.getByTestId('home-samples-link').click();
      await expect(page).toHaveURL(/\/restore#samples$/);
      await expect(page.getByTestId('sample-gallery')).toBeInViewport();
    });

    test('a full practice session: ten questions, instant feedback, score, progress saved', async ({ page }, info) => {
      await page.goto('/');
      await gotoNav(page, T.practice);
      await expect(page).toHaveURL(/\/practice$/);
      if (lang === 'en') await shot(page, 'practice-hub', info.project.name, true);
      await page.getByTestId('start-letters').click();
      await expect(page).toHaveURL(/\/practice\/letters\?level=1$/);
      let right = 0;
      for (let i = 0; i < 10; i++) {
        const q = page.getByTestId('question');
        await expect(page.getByTestId('q-counter')).toContainText(String(i + 1));
        await expect(q.getByTestId('q-glyph')).toBeVisible();
        if (i === 2 && lang === 'en') await shot(page, 'drill-mid-question', info.project.name);
        if (await answerFirst(q)) right++;
        // Feedback names the letter in Tamil script and English letters.
        await expect(q.getByTestId('q-feedback')).toBeVisible();
        await page.getByTestId('q-next').click();
      }
      await expect(page.getByTestId('session-done')).toContainText(T.done);
      await expect(page.getByTestId('session-score')).toContainText(String(right));
      await expectNoHorizontalScroll(page);
      await page.goto('/progress');
      await expect(page.getByTestId('local-row-letters')).toContainText('10');
    });

    test('keyboard: a gap question answered with a number key, feedback against the editors’ restoration', async ({ page }) => {
      await page.goto('/practice/gaps?level=1');
      const q = page.getByTestId('question');
      await expect(q.getByTestId('q-passage')).toContainText('[?1]');
      await page.keyboard.press('3');
      await expect(q.getByTestId('q-feedback')).toBeVisible();
      await expect(q.getByTestId('q-source').getByRole('link', { name: 'CC BY-SA 4.0' })).toBeVisible();
      await expect(page.getByTestId('q-next')).toBeFocused();
      await page.keyboard.press('Enter');
      await expect(page.getByTestId('q-counter')).toContainText('2');
    });

    test('timed trial: ten mixed questions against the clock, then a score and the best', async ({ page }, info) => {
      await page.goto('/practice/trial');
      await page.getByTestId('trial-start').click();
      await expect(page.getByTestId('trial-clock')).toBeVisible();
      const kinds = new Set<string>();
      // Answer eight of ten as the banks expect (by item id), so the result shows a real score and a new best.
      for (let i = 0; i < 10; i++) {
        const q = page.getByTestId('question');
        kinds.add((await q.getAttribute('data-kind'))!);
        const expected = ANSWER.get((await q.getAttribute('data-item-id'))!)!;
        await q.getByTestId(`option-${i < 8 ? expected : (expected + 1) % 4}`).click();
        await expect(q.getByTestId('q-feedback')).toHaveAttribute('data-right', String(i < 8));
        await page.getByTestId('q-next').click();
      }
      expect(kinds.size).toBe(4);
      await expect(page.getByTestId('trial-score')).toContainText('8 / 10');
      await expect(page.getByTestId('trial-done')).toContainText(T.trial);
      await expect(page.getByTestId('trial-score')).toContainText('/ 10');
      await expect(page.getByTestId('trial-newbest')).toBeVisible();
      await expectNoHorizontalScroll(page);
      if (lang === 'en') await shot(page, 'trial-result', info.project.name, true);
    });

    test('how it works: the pipeline on a real example, the measured limits and the DHARMA credit', async ({ page }, info) => {
      await page.goto('/');
      await gotoNav(page, T.how);
      await expect(page).toHaveURL(/\/how-it-works$/);
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(T.howTitle);
      await expect(page.getByTestId('pipeline').locator('.pipe-step')).toHaveCount(5);
      await expect(page.getByTestId('worked-example').locator('.bi-ta').first()).toContainText('மகன்');
      await expect(page.getByTestId('how-limits')).toContainText(T.limits);
      await expect(page.getByTestId('how-credit').getByRole('link', { name: 'CC BY-SA 4.0' })).toBeVisible();
      await expectNoHorizontalScroll(page);
      if (lang === 'en') await shot(page, 'how-it-works', info.project.name, true);
    });
  });
}

test('reduced motion: practice and how-it-works render without animations', async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/practice');
  const anim = await page.getByTestId('session-card-letters').evaluate((el) => getComputedStyle(el).animationName);
  expect(anim).toBe('none');
  await page.goto('/how-it-works');
  expect(await page.locator('.pipe-step').first().evaluate((el) => getComputedStyle(el).animationName)).toBe('none');
  await ctx.close();
});

test('small phone (375 px): the new pages fit without horizontal scroll and the tabs reach every section', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await setEnglish(page);
  for (const path of ['/', '/practice', '/practice/words?level=3', '/practice/formulas?level=2', '/practice/trial', '/how-it-works', '/progress']) {
    await page.goto(path);
    await expect(page.locator('main')).toBeVisible();
    await expectNoHorizontalScroll(page);
  }
  const tabs = page.getByTestId('tabbar');
  for (const name of ['Home', 'Practice', 'Restore', 'How']) await expect(tabs.getByRole('link', { name, exact: true })).toBeVisible();
  await page.getByTestId('menu-toggle').click();
  for (const name of ['Progress', 'Benchmark', 'About']) await expect(page.getByRole('navigation', { name: 'mobile' }).getByRole('link', { name })).toBeVisible();
  await ctx.close();
});

test('home is short: at most about five screens at 1440 x 900', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/');
  await expect(page.getByTestId('scholars')).toBeVisible();
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  expect(h, `home height ${h}px`).toBeLessThanOrEqual(5 * 900);
  if (SHOTS) await page.screenshot({ path: `${SHOTS}/after-home-full-1440.png`, fullPage: true });
  await ctx.close();
});
