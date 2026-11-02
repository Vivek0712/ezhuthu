import { expect, test, type Page } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish } from './helpers';

// /how-it-works: the animated overview at the top, then agents, flow, ontology, models, cloud and people, on desktop
// and phone (both Playwright projects). HOW_SHOTS=<dir> also saves review screenshots there (English, full page and
// mid-animation frames).
const SHOTS = process.env.HOW_SHOTS;

async function settle(page: Page) {
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(400);
}

/** Scroll the whole page once so every scroll-in reveal has run (for full-page screenshots). */
async function revealAll(page: Page) {
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < h; y += 400) {
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
    await page.waitForTimeout(80);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(900);
}

/** No two boxes of `sel` (inside the overview stage) overlap. */
async function expectNoOverlap(page: Page, sel: string) {
  const rects = await page.locator(sel).evaluateAll((els) =>
    els.map((e) => e.getBoundingClientRect()).filter((r) => r.width > 0).map((r) => [r.left, r.top, r.right, r.bottom]),
  );
  for (let i = 0; i < rects.length; i++)
    for (let j = i + 1; j < rects.length; j++) {
      const [a, b] = [rects[i]!, rects[j]!];
      const overlap = Math.min(a[2]!, b[2]!) - Math.max(a[0]!, b[0]!) > 1 && Math.min(a[3]!, b[3]!) - Math.max(a[1]!, b[1]!) > 1;
      expect(overlap, `${sel} #${i} and #${j} overlap`).toBe(false);
    }
}

test.describe('How it works: the full system', () => {
  test.beforeEach(async ({ page }) => {
    await setEnglish(page);
  });

  test('the overview is on the first screen, then every section in order, with one card per agent', async ({ page }) => {
    await page.goto('/how-it-works');
    const stage = page.getByTestId('hx-stage');
    await expect(stage).toBeVisible();
    const vh = page.viewportSize()!.height;
    expect((await stage.boundingBox())!.y, 'the overview starts on the first screen').toBeLessThan(vh * 0.6);
    const ids = ['how-hero', 'how-agents', 'how-flow', 'how-ontology', 'how-models', 'how-cloud', 'how-people', 'how-limits'];
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
    await expect(page.getByTestId('onto-coa')).toContainText('prepared, not running');
    await expect(page.getByTestId('cloud-svg')).toBeVisible();
    await expect(page.getByTestId('lim-top1')).toContainText('259 of 413');
  });

  test('the overview plays stone → Reader → Restorer → check → Interpreter → Tutor, and can be stopped on a station', async ({ page }, info) => {
    await page.goto('/how-it-works');
    await settle(page);
    const stage = page.getByTestId('hx-stage');
    await expect(stage).toHaveAttribute('data-scene', 'stone');
    await expect(stage).toHaveClass(/is-running/);
    if (SHOTS) await stage.screenshot({ path: `${SHOTS}/hero-0-stone-${info.project.name}-en.png` });
    for (const [i, k] of (['reader', 'restorer', 'check', 'interp', 'tutor'] as const).entries()) {
      await expect(stage).toHaveAttribute('data-scene', k, { timeout: 6000 });
      await expect(page.getByTestId(`hx-scene-${k}`)).toBeVisible();
      await expectNoOverlap(page, '.hx-letters .hx-ta');
      if (SHOTS) {
        await page.waitForTimeout(2200); // mid-scene, after its pieces have animated in
        await stage.screenshot({ path: `${SHOTS}/hero-${i + 1}-${k}-${info.project.name}-en.png` });
      }
    }
    await page.getByTestId('hx-step-check').click();
    await expect(stage).toHaveAttribute('data-scene', 'check');
    await expect(page.getByTestId('hx-play')).toHaveText('Play');
    await expect(page.getByTestId('hx-gauge-this')).toContainText('left open');
    await expect(page.getByTestId('hx-gauge-other')).toContainText('filled');
    await page.waitForTimeout(4500);
    await expect(stage).toHaveAttribute('data-scene', 'check');
    // Every scene card fits inside the stage.
    const sb = (await stage.boundingBox())!;
    const cb = (await page.getByTestId('hx-scene-check').boundingBox())!;
    expect(cb.y + cb.height).toBeLessThanOrEqual(sb.y + sb.height + 1);
    expect(cb.x + cb.width).toBeLessThanOrEqual(sb.x + sb.width + 1);
  });

  test('the flow starts playing when scrolled into view, and can be stepped by hand', async ({ page }, info) => {
    await page.goto('/how-it-works');
    const flow = page.getByTestId('flow');
    await flow.scrollIntoViewIfNeeded();
    await expect(page.getByTestId('flow-count')).toHaveText(/Step [12] of 11/);
    await expect(page.getByTestId('flow-count')).toHaveText(/Step 2 of 11/, { timeout: 6000 });
    await expect(page.locator('[data-node="reread"]')).toHaveClass(/is-active/);
    await expect(page.getByTestId('flow-count')).toHaveText(/Step 4 of 11/, { timeout: 9000 });
    await page.getByTestId('flow-play').click(); // pause
    await expect(page.getByTestId('flow-play')).toHaveText('Play the flow');
    if (SHOTS) {
      await settle(page);
      await flow.screenshot({ path: `${SHOTS}/flow-mid-play-${info.project.name}-en.png` });
    }
    const step = Number((await page.getByTestId('flow-count').textContent())!.match(/Step (\d+)/)![1]);
    for (let i = step; i < 9; i++) await page.getByTestId('flow-next').click();
    await expect(page.getByTestId('flow-caption')).toContainText('Abstain');
    await expect(page.locator('[data-node="open"]')).toHaveClass(/is-active/);
    await page.getByTestId('flow-next').click();
    await page.getByTestId('flow-next').click();
    await expect(page.getByTestId('flow-caption')).toContainText('Expert review');
    await expect(page.locator('[data-node="expert"]')).toHaveClass(/is-active/);
    await expect(page.getByTestId('flow-next')).toBeDisabled();
  });

  test('the cloud diagram sends a request along its path while on screen', async ({ page }, info) => {
    await page.goto('/how-it-works');
    const cloud = page.getByTestId('cloud');
    await cloud.scrollIntoViewIfNeeded();
    await expect(cloud.locator('[data-node="api"]')).toHaveClass(/is-active/, { timeout: 8000 });
    await expect(cloud.locator('[data-node="bedrock"]')).toHaveClass(/is-active/, { timeout: 8000 });
    if (SHOTS) await cloud.screenshot({ path: `${SHOTS}/cloud-mid-request-${info.project.name}-en.png` });
  });

  test('the ontology slice is interactive', async ({ page }, info) => {
    await page.goto('/how-it-works');
    await page.getByTestId('onto-slice').scrollIntoViewIfNeeded();
    await page.waitForTimeout(1500);
    if (SHOTS) await page.getByTestId('how-ontology').screenshot({ path: `${SHOTS}/ontology-${info.project.name}-en.png` });
    await page.getByTestId('onto-node-ez:measure/kani').click();
    await expect(page.getByTestId('onto-detail')).toContainText('kāṇi');
    await expect(page.getByTestId('onto-detail')).toContainText('Named together on');
    await page.getByTestId('onto-node-ez:place/uttiramerur').press('Enter');
    await expect(page.getByTestId('onto-detail')).toContainText('Uttiramērūr');
  });

  test('"More" opens the details of a card', async ({ page }) => {
    await page.goto('/how-it-works');
    const card = page.getByTestId('agent-check');
    await card.scrollIntoViewIfNeeded();
    await expect(card.getByText('Platt scaling')).toBeHidden();
    await card.getByText('More').click();
    await expect(card.getByText(/Platt scaling fitted on validation data/)).toBeVisible();
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
    await revealAll(page);
    await page.screenshot({ path: `${SHOTS}/how-it-works-full-${info.project.name}-en.png`, fullPage: true });
    await page.goto('/');
    await page.getByTestId('agent-chips').scrollIntoViewIfNeeded();
    await settle(page);
    await page.getByTestId('home-how').screenshot({ path: `${SHOTS}/home-how-chips-${info.project.name}-en.png` });
  });
});

for (const width of [375, 1920]) {
  test(`${width} px: how-it-works has no sideways scroll, no overlapping letters, and the diagrams fit`, async ({ browser }) => {
    const ctx = await browser.newContext(
      width === 375 ? { viewport: { width: 375, height: 740 }, isMobile: true, hasTouch: true } : { viewport: { width: 1920, height: 1080 } },
    );
    const page = await ctx.newPage();
    await setEnglish(page);
    await page.goto('/how-it-works');
    await expect(page.getByTestId('hx-stage')).toBeVisible();
    await expectNoHorizontalScroll(page);
    await expect(page.getByTestId('hx-stage')).toHaveAttribute('data-scene', 'reader', { timeout: 6000 });
    await page.waitForTimeout(2200);
    await expectNoOverlap(page, '.hx-letters .hx-ta');
    for (const id of ['flow-svg', 'cloud-svg']) {
      const box = (await page.getByTestId(id).boundingBox())!;
      expect(box.width, `${id} fits the screen`).toBeLessThanOrEqual(width);
      if (width === 375) expect(box.height, `${id} is laid out vertically`).toBeGreaterThan(box.width);
    }
    await page.getByTestId('flow').scrollIntoViewIfNeeded();
    await expect(page.getByTestId('flow-count')).toHaveText(/Step \d+ of 11/);
    await expectNoHorizontalScroll(page);
    await ctx.close();
  });
}

test('dark theme: the overview and sections render without sideways scroll', async ({ browser }) => {
  const ctx = await browser.newContext({ colorScheme: 'dark', viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/how-it-works');
  await expect(page.getByTestId('hx-stage')).toBeVisible();
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  expect(bg).not.toBe('rgb(255, 255, 255)');
  await expectNoHorizontalScroll(page);
  if (SHOTS) {
    await revealAll(page);
    await page.screenshot({ path: `${SHOTS}/how-it-works-full-dark-en.png`, fullPage: true });
  }
  await ctx.close();
});

test('reduced motion: a still overview with every scene, and nothing animates', async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await setEnglish(page);
  await page.goto('/how-it-works');
  const stage = page.getByTestId('hx-stage');
  await expect(stage).toHaveClass(/hx-still/);
  await expect(page.getByTestId('hx-play')).toHaveCount(0);
  for (const k of ['stone', 'reader', 'restorer', 'check', 'interp', 'tutor']) await expect(page.getByTestId(`hx-scene-${k}`)).toBeVisible();
  await page.waitForTimeout(4500);
  expect(await stage.getAttribute('class')).not.toMatch(/is-running/);
  // The flow does not start by itself; stepping it does not animate the edge.
  await page.getByTestId('flow').scrollIntoViewIfNeeded();
  await expect(page.getByTestId('flow-play')).toHaveText('Play the flow');
  await page.getByTestId('flow-next').click();
  const anim = await page.locator('[data-edge="e-photo-reader"]').evaluate((el) => getComputedStyle(el).animationName);
  expect(anim).toBe('none');
  expect(await page.locator('.agent-card').first().evaluate((el) => getComputedStyle(el).opacity)).toBe('1');
  if (SHOTS) await stage.screenshot({ path: `${SHOTS}/hero-reduced-motion-still-en.png` });
  await ctx.close();
});
