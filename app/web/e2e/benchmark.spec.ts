import { expect, test } from '@playwright/test';
import { expectNoHorizontalScroll, gotoNav, setEnglish } from './helpers';

// The public results page: anyone can read the measured numbers; only the runner asks for sign-in.
// BENCH_SHOTS=<dir> also saves full-page English screenshots there (desktop and phone).
const SHOTS = process.env.BENCH_SHOTS;

test('benchmark results are public: leaderboard, stopping, gap length, photos, decider, method', async ({ page }, info) => {
  await setEnglish(page);
  await page.goto('/');
  await gotoNav(page, 'Benchmark results');
  await expect(page).toHaveURL(/\/benchmark$/);
  await expect(page.getByRole('heading', { level: 1, name: 'Benchmark results' })).toBeVisible();
  await expect(page.getByTestId('auth-gate')).toHaveCount(0);
  const table = page.getByTestId('leaderboard-table');
  await expect(table.getByRole('row').nth(1)).toContainText('0.6271 [0.5787–0.6731]');
  await expect(page.getByTestId('leaderboard-chart').locator('.hbar-row.hi .hbar-ci')).toBeVisible();
  await expect(page.getByTestId('reliability-chart').locator('rect.bar')).toHaveCount(10);
  for (const id of ['bench-stop', 'bench-gaps', 'bench-ocr', 'bench-decider', 'bench-method']) await expect(page.getByTestId(id)).toBeVisible();
  await expect(page.getByTestId('runner-gate')).toContainText('Sign in to run it yourself');
  await expect(page.getByTestId('run-benchmark')).toHaveCount(0);
  await expectNoHorizontalScroll(page);
  await page.getByTestId('subset-hard').click();
  await expect(table.getByRole('row').nth(1)).toContainText('0.5741');
  await page.getByTestId('subset-full').click();
  if (SHOTS) {
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: `${SHOTS}/benchmark-${info.project.name}-en.png`, fullPage: true });
  }
});

test('benchmark results fit a 375 px phone in light and dark', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await setEnglish(page);
  for (const scheme of ['light', 'dark'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/benchmark');
    await expect(page.getByTestId('leaderboard')).toBeVisible();
    await expectNoHorizontalScroll(page);
    // The bar label and value are on screen, not clipped.
    const box = await page.getByTestId('leaderboard-chart-deployed').locator('.hbar-value').boundingBox();
    expect(box!.x + box!.width).toBeLessThanOrEqual(375);
    if (SHOTS && scheme === 'dark') await page.screenshot({ path: `${SHOTS}/benchmark-375-dark-en.png`, fullPage: true });
  }
});

test('home "For scholars" and How it works link to the results', async ({ page }) => {
  await setEnglish(page);
  await page.goto('/how-it-works');
  await page.getByTestId('how-results').click();
  await expect(page.getByTestId('leaderboard')).toBeVisible();
  await page.goto('/');
  await expect(page.getByTestId('scholars-benchmark')).toHaveText('See the benchmark results →');
});
