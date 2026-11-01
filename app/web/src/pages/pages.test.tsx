import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { renderApp } from '../test/render';

describe('Restore page', () => {
  it('counts gaps, restores the sample and shows fill plus the experts-unsure state', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('use-sample'));
    expect(screen.getByTestId('gap-count')).toHaveTextContent('2');
    await user.click(screen.getByTestId('restore-submit'));
    const result = await screen.findByTestId('restore-result');
    expect(within(screen.getByTestId('gap-0')).getAllByRole('meter')[0]).toHaveAttribute('aria-valuenow', '78');
    expect(within(screen.getByTestId('gap-1')).getByTestId('abstain')).toHaveTextContent('Experts are unsure');
    expect(within(result).getAllByRole('link')[0]).toHaveAttribute('href', 'https://dharmalekha.info/');
  });
  it('sends a correction to the review queue', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('use-sample'));
    await user.click(screen.getByTestId('restore-submit'));
    await screen.findByTestId('restore-result');
    await user.click(screen.getByTestId('suggest-1'));
    await user.type(screen.getByTestId('reading-1'), 'paṉṉiraṇṭ');
    await user.click(screen.getByTestId('send-1'));
    expect(await screen.findByText(/An expert will review it/)).toBeInTheDocument();
  });
});

describe('Learn page', () => {
  it('starts a Tamil-Brahmi lesson, gives a hint on a wrong answer and advances on a right one', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn' });
    await user.click(screen.getByTestId('level-L5'));
    await user.click(screen.getByTestId('start-lesson'));
    expect(await screen.findByRole('heading', { level: 1, name: /Mangulam/ })).toBeInTheDocument();
    expect(screen.getByTestId('glyph-tile')).toHaveAttribute('data-level', 'L5');
    expect(screen.getByTestId('glyph-tile').querySelector('.script-brahmi')).toHaveTextContent('\u{11013}');
    expect(screen.queryByTestId('restored-text')).toBeNull(); // would leak the answer
    await user.type(screen.getByTestId('answer-input'), 'ம');
    await user.click(screen.getByTestId('check-answer'));
    expect(await screen.findByTestId('feedback')).toHaveTextContent('Hint');
    expect(screen.queryByTestId('restored-text')).toBeNull(); // a wrong answer must not reveal it either
    await user.type(screen.getByTestId('answer-input'), 'க');
    await user.click(screen.getByTestId('check-answer'));
    expect(await screen.findByTestId('restored-text')).toBeInTheDocument(); // resolved: safe to show
    await user.click(await screen.findByTestId('next-item'));
    expect(screen.getByTestId('item-counter')).toHaveTextContent('Item 2 of 4');
    expect(screen.queryByTestId('restored-text')).toBeNull();
    expect(window.localStorage.getItem('ezhuthu.session_id')).toMatch(/^mock-session-/);
  });
  it('renders Vatteluttu as an image, never as inline markup', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn' });
    await user.click(screen.getByTestId('level-L4'));
    await user.click(screen.getByTestId('start-lesson'));
    const tile = await screen.findByTestId('glyph-tile');
    expect(tile.querySelector('img')?.getAttribute('src')).toMatch(/^data:image\/svg\+xml/);
    expect(tile.querySelector('svg')).toBeNull();
  });
});

describe('Progress page', () => {
  it('asks for a lesson first when there is no session', () => {
    renderApp(<AppRoutes />, { route: '/progress' });
    expect(screen.getByTestId('no-session')).toBeInTheDocument();
  });
  it('runs a pre-test and shows the score', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn' });
    await user.click(screen.getByTestId('start-lesson'));
    await screen.findByTestId('glyph-tile');
    await user.click(screen.getAllByRole('link', { name: 'Progress' })[0]!);
    await user.click(await screen.findByTestId('take-pre'));
    for (let i = 0; i < 10; i++) {
      await screen.findByText(`${i + 1} / 10`);
      await user.click(screen.getByTestId('assessment-next'));
    }
    await waitFor(() => expect(screen.getByTestId('pre-score')).toHaveTextContent('0%'));
    expect(screen.getByTestId('post-score')).toHaveTextContent('not taken');
  });
});

describe('protected pages', () => {
  it('gates Test behind sign-in, then runs the benchmark and draws the reliability chart', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/test' });
    expect(screen.getByTestId('auth-gate')).toBeInTheDocument();
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    await user.click(await screen.findByTestId('run-benchmark'));
    expect(await screen.findByTestId('score-report')).toBeInTheDocument();
    expect(screen.getByTestId('reliability-chart').querySelectorAll('rect.bar').length).toBeGreaterThan(0);
  });
  it('lets an expert approve a queue item', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/review' });
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    await user.click(await screen.findByTestId('approve-q-0002'));
    expect(await screen.findByTestId('reviewed')).toHaveTextContent('q-0002: approved → para');
  });
});

describe('About page', () => {
  it('credits DHARMA under CC BY-SA 4.0 and uses the approved branding', () => {
    renderApp(<AppRoutes />, { route: '/about' });
    const credits = screen.getByTestId('credits');
    expect(credits).toHaveTextContent('DHARMA');
    expect(within(credits).getByRole('link', { name: 'CC BY-SA 4.0' })).toBeInTheDocument();
    expect(credits).toHaveTextContent('Built with Strands Agents.');
    expect(document.body.textContent).not.toMatch(/Context Ontology Accelerator|CC BY 4\.0/);
    expect(document.body.textContent).not.toMatch(/Strands AI|AWS AI\b/);
  });
});
