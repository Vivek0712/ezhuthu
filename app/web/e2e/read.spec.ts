import { readFileSync } from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { expectNoHorizontalScroll, setEnglish, setTamil } from './helpers';

// Upload + OCR flow on /restore against the MSW mock of POST /api/read (contracts/restore-api.md).
const samplePhoto = path.join(import.meta.dirname, '..', 'public', 'samples', 'read', 'stone-tamil.jpg');

test.describe('restore: upload a photo', () => {
  test('photo is the default input; upload -> shrink -> read -> edit -> restore', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/restore');
    await expect(page.getByTestId('read-tab-photo')).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('camera-input')).toHaveAttribute('capture', 'environment');
    const [req] = await Promise.all([
      page.waitForRequest('**/api/read'),
      page.getByTestId('photo-input').setInputFiles(samplePhoto),
    ]);
    const body = req.postDataJSON() as { image_base64: string; media_type: string };
    expect(body.media_type).toBe('image/jpeg');
    // The browser re-encoded the photo: a JPEG without an EXIF APP1 segment.
    const bytes = Buffer.from(body.image_base64, 'base64');
    expect(bytes.subarray(0, 2).toString('hex')).toBe('ffd8');
    expect(bytes.includes(Buffer.from('Exif\0\0'))).toBe(false);
    const result = page.getByTestId('read-result');
    await expect(result).toBeVisible();
    // Bilingual experimental label.
    await expect(page.getByTestId('read-experimental')).toContainText('Experimental reading');
    await expect(page.getByTestId('read-experimental')).toContainText('சோதனை வாசிப்பு');
    await expect(result.locator('img')).toBeVisible();
    await page.getByTestId('read-script-iso15919').click();
    // The mock replays Sonnet 4.6's real reading of this plate (eval/reports/2026-11-02-ocr-app-samples.jsonl).
    await expect(page.getByTestId('read-line-0')).toHaveValue('śrī tirukkaḻukunṟattu peṟumāṉ');
    await page.getByTestId('read-line-0').fill('śrī tiru-k-kaḻu-kuṉṟattu [?2]');
    await expectNoHorizontalScroll(page);
    await Promise.all([page.waitForResponse('**/api/restore'), page.getByTestId('read-use-restore').click()]);
    await expect(page.getByTestId('restore-input')).toHaveValue(/^śrī tiru-k-kaḻu-kuṉṟattu \[\?2\]\n/);
    await expect(page.getByTestId('restore-result')).toBeVisible();
    await expectNoHorizontalScroll(page);
  });

  test('sample plates work without a camera, and warnings are localised', async ({ page }) => {
    await setTamil(page);
    await page.goto('/restore');
    await page.getByTestId('sample-stone-brahmi').click();
    await expect(page.getByTestId('read-result')).toBeVisible();
    await expect(page.getByTestId('read-experimental')).toBeVisible();
    const warning = page.locator('[data-code="low_reliability_script"]');
    await expect(warning).toContainText('வட்டெழுத்து');
    await expect(warning).not.toContainText('reliably');
    // Low confidence and no time for Opus (the mock's stand-in): a one-time "read again" is offered.
    await expect(page.getByTestId('read-again')).toBeVisible();
    await page.getByTestId('read-reset').click();
    await expect(page.getByTestId('dropzone')).toBeVisible();
  });

  test('a HEIC file this browser cannot decode gets a plain-language fix', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/restore');
    await page.getByTestId('photo-input').setInputFiles({ name: 'IMG_0420.HEIC', mimeType: 'image/heic', buffer: Buffer.from('....ftypheic....') });
    await expect(page.getByTestId('read-error')).toContainText('cannot open HEIC');
  });

  test('a text file and a DHARMA EpiDoc file flow into restore', async ({ page }) => {
    await setEnglish(page);
    await page.goto('/restore');
    await page.getByTestId('read-tab-file').click();
    await page.getByTestId('sample-dharma-xml').click();
    await expect(page.getByTestId('read-result')).toBeVisible();
    await expect(page.getByTestId('read-experimental')).toHaveCount(0);
    await page.getByTestId('read-reset').click();
    const txt = readFileSync(path.join(import.meta.dirname, '..', 'public', 'samples', 'read', 'chola-opening.txt'));
    await page.getByTestId('file-input').setInputFiles({ name: 'lines.txt', mimeType: 'text/plain', buffer: txt });
    await expect(page.getByTestId('read-line-0')).toHaveValue(/கோப்\[\?4\]கேசரி/);
    await Promise.all([page.waitForResponse('**/api/restore'), page.getByTestId('read-use-restore').click()]);
    await expect(page.getByTestId('restore-result')).toBeVisible();
  });
});
