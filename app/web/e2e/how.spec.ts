import { expect, test, type Page } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish } from './helpers';

// /how-it-works: the agents, the step-through flow, the ontology slice, models, cloud and people, on desktop and phone
// (both Playwright projects). HOW_SHOTS=<dir> also saves review screenshots there (English, full page + mid-play).
const SHOTS = process.env.HOW_SHOTS;

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
}

test.describe('How it works: the full system', () => {
  test.beforeEach(async ({ page }) => {
    await setEnglish(page);
  });

  test('every section renders, in order, with one card per agent', async ({ page }) => {
    await page.goto('/how-it-works');
    const ids = ['worked-example', 'how-agents', 'how-flow', 'how-ontology', 'how-models', 'how-cloud', 'how-people', 'how-limits'];
    const ys: number[] = [];
    for (const id of ids) {
      const el = page.getByTestId(id);
      await expect(el).toBeVisible();
      ys.push((await el.boundingBox())!.y);
    }
    expect([...ys].sort((a, b) => a - b)).toEqual(ys);
    await expect(page.getByTestId('agent-cards').locator('.agent-card')).toHaveCount(10);
    for (const k of ['reader', 'restorer', 'retrieval', 'ngram', 'ontology', 'check', 'decider', 'interpreter', 'tutor', 'review']) {
      await expect(page.getByTestId(`agent-ex-${k}`).locator('.bi-ta')).toBeVisible();
    }
    await expect(page.getByTestId('models-decider')).toContainText('Not used for restoration');
    await expect(page.getByTestId('onto-effect')).toContainText('Not measurably, yet');
    await expect(page.getByTestId('cloud-svg')).toBeVisible();
  });

  test('the flow plays hop by hop with a caption, and can be stepped by hand', async ({ page }, info) => {
    await page.goto('/how-it-works');
    const flow = page.getByTestId('flow');
    await flow.scrollIntoViewIfNeeded();
    await expect(page.getByTestId('flow-caption')).toContainText('Play the flow');
    await page.getByTestId('flow-play').click();
    await expect(page.getByTestId('flow-count')).toHaveText(/Step 1 of 11/);
    await expect(page.getByTestId('flow-caption')).toContainText('Photo path');
    await expect(page.locator('[data-node="reader"]')).toHaveClass(/is-active/);
    await expect(page.getByTestId('flow-count')).toHaveText(/Step 2 of 11/, { timeout: 6000 });
    await expect(page.locator('[data-node="reread"]')).toHaveClass(/is-active/);
    await expect(page.getByTestId('flow-count')).toHaveText(/Step 4 of 11/, { timeout: 9000 });
    if (SHOTS) {
      await page.getByTestId('flow-play').click(); // pause on a busy hop for the screenshot
      await settle(page);
      await flow.screenshot({ path: `${SHOTS}/flow-mid-play-${info.project.name}-en.png` });
    } else {
      await page.getByTestId('flow-play').click();
    }
    await expect(page.getByTestId('flow-play')).toHaveText('Play the flow');
    // Step by hand to the abstain branch and the expert loop.
    for (let i = 0; i < 5; i++) await page.getByTestId('flow-next').click();
    await expect(page.getByTestId('flow-caption')).toContainText('Abstain');
    await expect(page.locator('[data-node="open"]')).toHaveClass(/is-active/);
    await page.getByTestId('flow-next').click();
    await page.getByTestId('flow-next').click();
    await expect(page.getByTestId('flow-caption')).toContainText('Expert review');
    await expect(page.locator('[data-node="expert"]')).toHaveClass(/is-active/);
    await expect(page.getByTestId('flow-next')).toBeDisabled();
  });

  test('the ontology slice is interactive', async ({ page }) => {
    await page.goto('/how-it-works');
    await page.getByTestId('onto-node-ez:measure/kani').click();
    await expect(page.getByTestId('onto-detail')).toContainText('kāṇi');
    await expect(page.getByTestId('onto-detail')).toContainText('Named together on');
    await page.getByTestId('onto-node-ez:place/uttiramerur').press('Enter');
    await expect(page.getByTestId('onto-detail')).toContainText('Uttiramērūr');
  });

  test('home chips lead to the matching card', async ({ page }) => {
    await page.goto('/');
    const chips = page.getByTestId('agent-chips');
    await expect(chips.getByRole('link')).toHaveCount(8);
    await chips.getByRole('link', { name: 'Interpreter' }).click();
    await expect(page).toHaveURL(/\/how-it-works#agent-interpreter$/);
    await expect(page.getByTestId('agent-interpreter')).toBeInViewport();
  });

  test('screenshots (English, full page)', async ({ page }, info) => {
    test.skip(!SHOTS, 'set HOW_SHOTS=<dir> to save review screenshots');
    await page.goto('/how-it-works');
    await settle(page);
    await page.screenshot({ path: `${SHOTS}/how-it-works-full-${info.project.name}-en.png`, fullPage: true });
    await page.goto('/');
    await page.getByTestId('agent-chips').scrollIntoViewIfNeeded();
    await settle(page);
    await page.getByTestId('home-how').screenshot({ path: `${SHOTS}/home-how-chips-${info.project.name}-en.png` });
  });
});

test('small phone (375 px): how-it-works has no sideways scroll, and the diagrams stack vertically', async ({ browser }) => {
  const ctx = await browser.newContext({ viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/how-it-works');
  await expect(page.getByTestId('flow-svg')).toBeVisible();
  await expectNoHorizontalScroll(page);
  for (const id of ['flow-svg', 'cloud-svg']) {
    const box = (await page.getByTestId(id).boundingBox())!;
    expect(box.width, `${id} fits the screen`).toBeLessThanOrEqual(375);
    expect(box.height, `${id} is laid out vertically`).toBeGreaterThan(box.width);
  }
  await page.getByTestId('flow-play').click();
  await expect(page.getByTestId('flow-count')).toHaveText(/Step 1 of 11/);
  await expectNoHorizontalScroll(page);
  await ctx.close();
});

test('reduced motion: the active hop does not animate', async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/how-it-works');
  await page.getByTestId('flow-next').click();
  const anim = await page.locator('[data-edge="e-photo-reader"]').evaluate((el) => getComputedStyle(el).animationName);
  expect(anim).toBe('none');
  await ctx.close();
});
