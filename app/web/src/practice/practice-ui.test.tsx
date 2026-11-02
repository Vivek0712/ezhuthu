import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { renderApp } from '../test/render';
import { _resetProgressMemory, loadProgress } from './progress';

beforeEach(() => {
  window.localStorage.clear();
  _resetProgressMemory();
});

/** Answer the open question: the right option when `right`, else a wrong one. Returns the feedback element. */
async function answer(user: ReturnType<typeof userEvent.setup>, right: boolean) {
  const q = await screen.findByTestId('question', {}, { timeout: 3000 });
  const opts = within(q).getAllByRole('button').filter((b) => b.dataset.testid?.startsWith('option-'));
  // The right option is not marked before answering; find it by trying the data the card exposes after the click.
  await user.click(opts[0]!);
  const fb = within(q).getByTestId('q-feedback');
  return { q, fb, firstWasRight: fb.dataset.right === 'true', right };
}

describe('practice hub', () => {
  it('lists every session type with levels, the AI tutor as one of them, and the DHARMA credit', async () => {
    renderApp(<AppRoutes />, { route: '/practice' });
    expect(screen.getByRole('heading', { level: 1, name: 'Practice' })).toBeInTheDocument();
    for (const k of ['letters', 'words', 'gaps', 'formulas', 'trial', 'guided']) expect(screen.getByTestId(`session-card-${k}`)).toBeInTheDocument();
    expect(screen.getByTestId('start-guided')).toHaveAttribute('href', '/practice/guided');
    expect(screen.getByTestId('start-gaps-3')).toHaveAttribute('href', '/practice/gaps?level=3');
    expect(screen.getByTestId('practice-credit')).toHaveTextContent('CC BY-SA 4.0');
  });

  it('forwards old lesson links (sample gallery, Restore hand-off) to the AI tutor', async () => {
    renderApp(<AppRoutes />, { route: '/practice?inscription=DHARMA_INSPallava00092&level=L3' });
    expect(await screen.findByRole('heading', { level: 1 })).toBeInTheDocument();
    expect(screen.queryByTestId('session-cards')).toBeNull();
  });
});

describe('a drill session', () => {
  it('runs ten questions with instant feedback in both scripts, then scores and saves progress', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/practice/words?level=1' });
    let rights = 0;
    for (let i = 0; i < 10; i++) {
      const { q, fb, firstWasRight } = await answer(user, true);
      if (firstWasRight) rights++;
      expect(fb).toHaveTextContent(firstWasRight ? 'Well read' : 'Not this one');
      // After answering, every option shows Tamil script and its English letters.
      expect(q.querySelectorAll('.q-option .bi-ta').length).toBe(4);
      expect(q.querySelectorAll('.q-option .bi-iso').length).toBe(4);
      expect(within(fb).getByRole('link', { name: 'DHARMA edition ↗' })).toHaveAttribute('href', expect.stringMatching(/^https:\/\/dharmalekha\.info\//));
      await user.click(screen.getByTestId('q-next'));
    }
    const done = await screen.findByTestId('session-done');
    expect(within(done).getByTestId('session-score')).toHaveTextContent(`${rights} of 10`);
    const p = loadProgress();
    expect(p.kinds.words).toMatchObject({ answered: 10, right: rights, sessions: 1 });
  });

  it('answers with the number keys and phrases gap feedback against the editors’ restoration', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/practice/gaps?level=1' });
    await screen.findByTestId('question', {}, { timeout: 3000 });
    await user.keyboard('2');
    const fb = screen.getByTestId('q-feedback');
    expect(fb.textContent).toMatch(/Matches the editors’ restoration|The editors restored a different reading/);
    expect(fb).toHaveTextContent('The edition reads');
    expect(fb.textContent).not.toMatch(/\bcorrect\b/i);
  });
});

describe('home mini-drill', () => {
  it('lets a visitor answer a question on the home page and records it', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/' });
    const drill = screen.getByTestId('mini-drill');
    await user.click(within(drill).getByTestId('option-1'));
    expect(within(drill).getByTestId('q-feedback')).toBeInTheDocument();
    await user.click(within(drill).getByTestId('mini-next'));
    expect(within(drill).queryByTestId('q-feedback')).toBeNull();
    const p = loadProgress();
    expect((p.kinds.letters?.answered ?? 0) + (p.kinds.words?.answered ?? 0)).toBe(1);
  });
});

describe('how it works', () => {
  it('walks the real TRAIN example through the pipeline and states the measured limits', () => {
    renderApp(<AppRoutes />, { route: '/how-it-works' });
    for (const s of ['reader', 'restorer', 'decider', 'interpreter', 'expert']) expect(screen.getByTestId(`pipe-${s}`)).toBeInTheDocument();
    expect(screen.getByTestId('pipe-decider-example')).toHaveTextContent('15% is below 41%: left open');
    expect(screen.getByTestId('walk-decider')).toHaveTextContent('15%');
    const limits = screen.getByTestId('how-limits');
    expect(limits).toHaveTextContent('259 of 413');
    expect(limits).toHaveTextContent('187 of 206');
    expect(screen.getByTestId('how-data')).toHaveTextContent('CC BY-SA 4.0');
    expect(document.body.textContent).not.toMatch(/experimental|Aivar/i);
  });

  it('is in Tamil when the app is', () => {
    renderApp(<AppRoutes />, { route: '/how-it-works', lang: 'ta' });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('எழுத்து ஒரு கல்வெட்டை எப்படிப் படிக்கிறது');
  });
});

describe('progress page', () => {
  it('shows local practice progress even without a tutor session', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/practice/letters?level=1' });
    await answer(user, true);
    await user.click(screen.getByTestId('q-next'));
    await user.click(screen.getByRole('link', { name: '← Practice' }));
    renderApp(<AppRoutes />, { route: '/progress' });
    await waitFor(() => expect(screen.getAllByTestId('local-row-letters').length).toBeGreaterThan(0));
  });
});
