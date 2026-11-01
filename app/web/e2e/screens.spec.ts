import { expect, test, type Page } from '@playwright/test';
import { setEnglish } from './helpers';

// Captures the PR screenshots into app/web/screenshots/. Runs as a normal smoke test unless UPDATE_SCREENSHOTS=1.
const SAVE = process.env.UPDATE_SCREENSHOTS === '1';
test.use({ contextOptions: { reducedMotion: 'reduce' }, deviceScaleFactor: 1 });

async function shot(page: Page, name: string, project: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(150);
  if (SAVE) await page.screenshot({ path: `screenshots/${project}-${name}.png`, fullPage: true });
}

test('@screens capture every page', async ({ page }, info) => {
  const p = info.project.name;
  await page.goto('/');
  await expect(page.getByTestId('evolution-hero')).toBeVisible();
  await shot(page, '01-home-ta', p);

  await page.goto('/learn');
  await page.getByTestId('level-L5').click();
  await shot(page, '02-learn-levels-ta', p);
  await page.getByTestId('start-lesson').click();
  await page.getByTestId('answer-input').fill('ம');
  await page.getByTestId('check-answer').click();
  await expect(page.getByTestId('feedback')).toBeVisible();
  await shot(page, '03-learn-brahmi-hint-ta', p);

  await page.goto('/restore');
  await page.getByTestId('use-sample').click();
  await page.getByTestId('restore-submit').click();
  await expect(page.getByTestId('restore-result')).toBeVisible();
  await shot(page, '04-restore-ta', p);

  await setEnglish(page);
  await page.goto('/');
  await shot(page, '05-home-en', p);

  await page.goto('/learn');
  await page.getByTestId('level-L4').click();
  await page.getByTestId('start-lesson').click();
  await expect(page.getByTestId('glyph-tile').locator('img')).toBeVisible();
  await shot(page, '06-learn-vatteluttu-en', p);

  await page.goto('/progress');
  await page.getByTestId('take-pre').click();
  for (let i = 0; i < 10; i++) {
    await expect(page.getByTestId('assessment-counter')).toHaveText(`${i + 1} / 10`);
    await page.getByTestId('assessment-input').fill(i < 4 ? ['க', 'ம', 'க', 'ட'][i]! : 'x');
    await page.getByTestId('assessment-next').click();
  }
  await expect(page.getByTestId('pre-score')).toHaveText('40%');
  await page.getByTestId('take-post').click();
  for (let i = 0; i < 10; i++) {
    await expect(page.getByTestId('assessment-counter')).toHaveText(`${i + 1} / 10`);
    await page.getByTestId('assessment-input').fill(['க', 'ம', 'க', 'ட', 'க', 'ந', 'க', 'ப', 'க', 'ந'][i]!);
    await page.getByTestId('assessment-next').click();
  }
  await expect(page.getByTestId('gain')).toHaveText('+60 pts');
  await shot(page, '07-progress-en', p);

  await page.goto('/test');
  await page.getByTestId('auth-gate').getByRole('button', { name: 'Sign in' }).click();
  await page.getByTestId('run-benchmark').click();
  await expect(page.getByTestId('score-report')).toBeVisible();
  await shot(page, '08-test-report-en', p);

  await page.goto('/review');
  await expect(page.getByTestId('queue-q-0001')).toBeVisible();
  await shot(page, '09-review-en', p);

  await page.goto('/about');
  await shot(page, '10-about-en', p);
});
