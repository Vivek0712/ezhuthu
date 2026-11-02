import { expect, type Page } from '@playwright/test';

/** Wait until the web fonts needed for `families` are actually loaded (not just declared). */
export async function expectFontsLoaded(page: Page, checks: { family: string; sample: string }[]) {
  await page.evaluate(() => document.fonts.ready);
  for (const { family, sample } of checks) {
    await expect
      .poll(
        () =>
          page.evaluate(
            async ([f, s]) => {
              await document.fonts.load(`48px "${f}"`, s);
              const loaded = [...document.fonts].some((ff) => ff.family.replace(/"/g, '') === f && ff.status === 'loaded');
              return loaded && document.fonts.check(`48px "${f}"`, s);
            },
            [family, sample] as const,
          ),
        { message: `${family} should render ${sample}` },
      )
      .toBe(true);
  }
}

/** The glyph must not render as a fallback box: its advance in the target font differs from .notdef in a font lacking it. */
export async function glyphWidth(page: Page, family: string, text: string): Promise<number> {
  return page.evaluate(
    ([f, t]) => {
      const c = document.createElement('canvas').getContext('2d')!;
      c.font = `64px "${f}"`;
      return c.measureText(t).width;
    },
    [family, text] as const,
  );
}

export async function expectNoHorizontalScroll(page: Page) {
  const [sw, iw] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  expect(sw, 'page must not scroll horizontally').toBeLessThanOrEqual(iw + 1);
}

/** Navigate like a person: top nav at 1000 px and wider; below that the bottom tabs, or the "More" sheet. */
export async function gotoNav(page: Page, name: RegExp | string) {
  const isMobile = (page.viewportSize()?.width ?? 1000) < 1000;
  if (!isMobile) {
    await page.getByRole('navigation', { name: 'primary' }).getByRole('link', { name }).click();
    return;
  }
  await page.getByTestId('tabbar').waitFor(); // the app renders after the mock worker starts
  const tab = page.getByTestId('tabbar').getByRole('link', { name });
  if (await tab.count()) {
    await tab.click();
    return;
  }
  await page.getByTestId('menu-toggle').click();
  await page.getByRole('navigation', { name: 'mobile' }).getByRole('link', { name }).click();
}

export async function setEnglish(page: Page) {
  await page.addInitScript(() => window.localStorage.setItem('ezhuthu.lang.v2', 'en'));
}
