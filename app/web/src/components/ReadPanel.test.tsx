import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { base64Bytes, fitWithin, isHeic, looksLikeText } from '../lib/imagePrep';
import { READ_SAMPLES } from '../lib/readSamples';
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
    for (const s of READ_SAMPLES) expect(existsSync(`public${s.url}`), s.url).toBe(true);
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
      http.get('/samples/read/DHARMA_INSPallava00205.xml', () =>
        HttpResponse.text(
          '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><title>Uttiramērūr</title></teiHeader><text><body><div type="edition"><p><lb n="1"/>svasti śrī kō<supplied reason="lost">vicaiya</supplied> <lb n="2"/>yāṇṭu eṭṭāvatu</p></div><div type="apparatus"/></body></text></TEI>',
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
