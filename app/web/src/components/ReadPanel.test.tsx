import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { base64Bytes, fitWithin, isHeic, looksLikeText } from '../lib/imagePrep';
import { api } from '../api/client';
import { ta } from '../i18n/strings';
import { READ_SAMPLES } from '../lib/readSamples';
import { epidocLines } from '../mocks/read';
import { server } from '../mocks/server';
import { renderApp } from '../test/render';

describe('imagePrep helpers', () => {
  it('fits the long side without upscaling', () => {
    expect(fitWithin(4032, 3024)).toEqual({ width: 2048, height: 1536 });
    expect(fitWithin(3024, 4032)).toEqual({ width: 1536, height: 2048 });
    expect(fitWithin(800, 600)).toEqual({ width: 800, height: 600 });
  });
  it('counts base64 bytes and recognises HEIC and text files', () => {
    expect(base64Bytes(btoa('abcd'))).toBe(4);
    expect(base64Bytes(btoa('abcde'))).toBe(5);
    expect(isHeic({ name: 'IMG_0001.HEIC', type: '' })).toBe(true);
    expect(isHeic({ name: 'a.jpg', type: 'image/jpeg' })).toBe(false);
    expect(looksLikeText({ name: 'x.xml', type: '' })).toBe(true);
    expect(looksLikeText({ name: 'x.png', type: 'image/png' })).toBe(false);
  });
  it('ships every sample file it lists under public/', async () => {
    const { existsSync } = await import('node:fs');
    for (const s of READ_SAMPLES) {
      expect(existsSync(`public${s.url}`), s.url).toBe(true);
      if (s.thumb) expect(existsSync(`public${s.thumb}`), s.thumb).toBe(true);
    }
  });
  it('names the TRAIN inscription of every sample, as SOURCES.json does (DATA_CARD leakage rule 2)', async () => {
    const { readFileSync } = await import('node:fs');
    const manifest = JSON.parse(readFileSync('public/samples/read/SOURCES.json', 'utf8')) as { files: { file: string; inscription_id: string; split: string }[] };
    for (const s of READ_SAMPLES) {
      const entry = manifest.files.find((f) => `/samples/read/${f.file}` === s.url);
      expect(entry, s.url).toBeDefined();
      expect(entry!.inscription_id).toBe(s.inscription_id);
      expect(entry!.split).toBe('train');
      expect(s.source).toBe(`https://dharmalekha.info/texts/${s.inscription_id}`);
    }
    // labels never pass a rendering off as a photograph
    for (const s of READ_SAMPLES.filter((x) => x.kind === 'photo')) expect(s.label_en).toMatch(/^Rendered plate/);
  });
  it('counts EpiDoc gaps like the server (Uttiramerur sample: 3 lines, 2 supplied + 1 gap)', async () => {
    const { readFileSync } = await import('node:fs');
    const { lines, masked } = epidocLines(readFileSync('public/samples/read/DHARMA_INSUttiramerur00001.xml', 'utf8'));
    expect(lines.length).toBe(3);
    expect(masked).toBe(2);
    expect(lines.reduce((a, l) => a + l.gaps, 0)).toBe(3);
  });
});

function textFile(name: string, body: string, type = 'text/plain') {
  return new File([body], name, { type });
}

describe('Restore page upload', () => {
  it('opens on the photo tab with drop zone, camera capture and samples; typing is secondary', () => {
    renderApp(<AppRoutes />, { route: '/restore' });
    expect(screen.getByTestId('read-tab-photo')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('dropzone')).toBeInTheDocument();
    expect(screen.getByTestId('camera-input')).toHaveAttribute('capture', 'environment');
    expect(screen.getByTestId('photo-input').getAttribute('accept')).toContain('image/heic');
    expect(within(screen.getByTestId('read-samples-photo')).getAllByRole('button').length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByTestId('restore-input')).toBeNull();
  });

  it('reads a text file, lets the learner edit and untick lines, then restores', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(
      screen.getByTestId('file-input'),
      textFile('lines.txt', 'svasti śrī kōp[?4]kēcaripaṉmaṟku\nyāṇṭu [?] āvatu\nno gap here\n'),
    );
    const result = await screen.findByTestId('read-result');
    expect(screen.queryByTestId('read-experimental')).toBeNull(); // only photo readings are experimental
    await user.click(screen.getByTestId('read-script-iso15919'));
    expect(screen.getByTestId('read-line-0')).toHaveValue('svasti śrī kōp[?4]kēcaripaṉmaṟku');
    await user.click(within(result).getByRole('checkbox', { name: /3$/ }));
    await user.clear(screen.getByTestId('read-line-1'));
    await user.type(screen.getByTestId('read-line-1'), 'yāṇṭu [[?2] āvatu');
    await user.click(screen.getByTestId('read-use-restore'));
    expect(screen.getByTestId('read-tab-type')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('restore-input')).toHaveValue('svasti śrī kōp[?4]kēcaripaṉmaṟku\nyāṇṭu [?2] āvatu');
    expect(await screen.findByTestId('restore-result')).toBeInTheDocument();
  });

  it('reads a DHARMA EpiDoc sample with supplied text as gaps', async () => {
    const user = userEvent.setup();
    server.use(
      http.get('/samples/read/DHARMA_INSUttiramerur00001.xml', () =>
        HttpResponse.text(
          '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc><titleStmt><title>Uttiramērūr</title></titleStmt><publicationStmt><idno type="filename">DHARMA_INSUttiramerur00001.xml</idno><availability><licence target="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</licence></availability></publicationStmt></fileDesc></teiHeader><text><body><div type="edition"><p><lb n="1"/>svasti śrī kō<supplied reason="lost">vicaiya</supplied> <lb n="2"/>yāṇṭu eṭṭāvatu</p></div><div type="apparatus"/></body></text></TEI>',
          { headers: { 'Content-Type': 'application/xml' } },
        ),
      ),
    );
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.click(screen.getByTestId('sample-dharma-xml'));
    await screen.findByTestId('read-result');
    expect(screen.getByTestId('read-line-0')).toHaveValue('svasti śrī kō[?3]');
    expect(screen.getByTestId('read-meta')).toHaveTextContent('Uttiramērūr');
    const edition = screen.getByTestId('read-edition');
    expect(within(edition).getByRole('link', { name: 'DHARMA_INSUttiramerur00001' })).toHaveAttribute('href', 'https://dharmalekha.info/texts/DHARMA_INSUttiramerur00001');
    expect(within(edition).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by-sa/4.0/');
    expect(screen.getByTestId('read-warning')).toHaveAttribute('data-code', 'masked_supplied');
  });

  it('shows server warnings in Tamil from their codes, not as raw English', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore', lang: 'ta' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(
      screen.getByTestId('file-input'),
      textFile('e.xml', '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div type="edition"><p><lb n="1"/>kō<supplied>vicaiya</supplied> yāṇṭu</p></div></body></text></TEI>', 'application/xml'),
    );
    await screen.findByTestId('read-result');
    const w = screen.getByTestId('read-warning');
    expect(w).toHaveTextContent(ta['read.warn.masked_supplied'].replace('{n}', '1'));
    expect(w).not.toHaveTextContent('editorial restoration');
  });

  it('asks before a script switch throws away edited lines', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(screen.getByTestId('file-input'), textFile('s.txt', 'svasti śrī [?2]\n'));
    await screen.findByTestId('read-result');
    await user.click(screen.getByTestId('read-script-iso15919'));
    await user.type(screen.getByTestId('read-line-0'), ' kō');
    await user.click(screen.getByTestId('read-script-tamil'));
    expect(screen.getByTestId('read-switch-confirm')).toBeInTheDocument();
    await user.click(screen.getByTestId('read-switch-no'));
    expect(screen.getByTestId('read-line-0')).toHaveValue('svasti śrī [?2] kō');
    expect(screen.getByTestId('read-script-iso15919')).toHaveAttribute('aria-checked', 'true');
    await user.click(screen.getByTestId('read-script-tamil'));
    await user.click(screen.getByTestId('read-switch-yes'));
    expect(screen.queryByTestId('read-switch-confirm')).toBeNull();
    expect(screen.getByTestId('read-script-tamil')).toHaveAttribute('aria-checked', 'true');
  });

  it('says when a long reading will be cut for Learn, and Learn says it was cut', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    const long = Array.from({ length: 50 }, () => 'svasti śrī kōpparakēcaripaṉmaṟku yāṇṭu irupattu').join('\n');
    await user.upload(screen.getByTestId('file-input'), textFile('long.txt', long));
    await screen.findByTestId('read-result');
    expect(screen.getByTestId('read-learn-cut')).toBeInTheDocument();
    await user.click(screen.getByTestId('read-use-learn'));
    expect(await screen.findByTestId('learn-text-cut')).toBeInTheDocument();
  });

  it('sends the reading to Learn when there is nothing to restore', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(screen.getByTestId('file-input'), textFile('a.txt', 'யாண்டு மூன்றாவது\n'));
    await screen.findByTestId('read-result');
    expect(screen.getByTestId('read-use-restore')).toBeDisabled();
    await user.click(screen.getByTestId('read-use-learn'));
    expect(await screen.findByDisplayValue('யாண்டு மூன்றாவது')).toBeInTheDocument();
  });

  it('explains server errors in words (no_text, reader unavailable)', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(screen.getByTestId('file-input'), textFile('a.txt', '!!! ### 123'));
    expect(await screen.findByTestId('read-error')).toHaveTextContent('No Tamil or ISO-15919 text');
    server.use(http.post('/api/read', () => HttpResponse.json({ error: { code: 'reader_unavailable', message: 'x' } }, { status: 503 })));
    await user.upload(screen.getByTestId('file-input'), textFile('b.txt', 'svasti'));
    expect(await screen.findByTestId('read-error')).toHaveTextContent('Photo reading is switched off');
  });

  it('mock photo reads mirror the server: warning codes, a one-time token for reading again', async () => {
    const r = await api.read({ image_base64: 'AAAA', media_type: 'image/jpeg', filename: 'stone-brahmi.jpg' });
    expect(r.warning_codes).toEqual([{ code: 'low_reliability_script', params: { script: 'vatteluttu' } }]);
    expect(r.escalation_skipped).toBe('time_budget');
    await expect(api.read({ image_base64: 'AAAA', filename: 'stone-brahmi.jpg', router: 'opus' })).rejects.toMatchObject({ status: 403 });
    const again = await api.read({ image_base64: 'AAAA', filename: 'stone-brahmi.jpg', router: 'opus', reread_token: r.reread_token! });
    expect(again.escalation_skipped).toBe('error');
    await expect(api.read({ image_base64: 'AAAA', filename: 'stone-brahmi.jpg', router: 'opus', reread_token: r.reread_token! })).rejects.toMatchObject({ status: 403 });
    const plain = await api.read({ image_base64: 'AAAA', filename: 'stone-tamil.jpg' });
    expect(plain.warnings).toEqual([]);
    expect(plain.escalation_skipped).toBeUndefined();
  });

  it('warns when the chosen lines have more gaps than restore accepts', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('read-tab-file'));
    await user.upload(screen.getByTestId('file-input'), textFile('g.txt', 'a [?] b [?] c [?]\nd [?] e [?] f [?]\n'));
    await screen.findByTestId('read-result');
    expect(screen.getByTestId('read-too-many-gaps')).toBeInTheDocument();
    expect(screen.getByTestId('read-use-restore')).toBeDisabled();
  });
});
