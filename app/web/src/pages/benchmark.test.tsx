import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { SUMMARY } from '../benchmark/summary';
import { enBench, taBench } from '../i18n/strings-bench';
import { renderApp } from '../test/render';

describe('Benchmark results page (/benchmark)', () => {
  it('renders anonymously with the leaderboard, and hides the runner until sign-in', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/benchmark' });
    expect(screen.queryByTestId('auth-gate')).toBeNull();
    expect(screen.getByRole('heading', { level: 1, name: 'Benchmark results' })).toBeInTheDocument();
    const board = screen.getByTestId('leaderboard');
    // Deployed first, with its interval and the paired tests against it, numbers straight from summary.json.
    const rows = within(screen.getByTestId('leaderboard-table')).getAllByRole('row').slice(1);
    expect(rows.map((r) => within(r).getByRole('rowheader').textContent)).toEqual([
      'Ezhuthu, as deployed',
      'Character 5-gram',
      'Routed with a local 2B decider',
      'Copy the best parallel',
      'Sonnet 4.6 alone',
    ]);
    expect(rows[0]).toHaveTextContent('0.6271 [0.5787–0.6731]');
    expect(rows[0]).toHaveTextContent('259 / 413');
    expect(rows[1]).toHaveTextContent('only deployed 34, only this 9; p = 0.0002');
    expect(rows[4]).toHaveTextContent('0.4165');
    expect(rows[4]).toHaveTextContent('not tested in the reports');
    expect(within(board).getByTestId('leaderboard-chart-deployed')).toHaveClass('hi');
    expect(screen.getByTestId('bench-stop')).toHaveTextContent('49.9%');
    expect(screen.getByTestId('bench-stop')).toHaveTextContent('90.8%');
    expect(screen.getByTestId('bench-stop')).toHaveTextContent('(187 of 206)');
    expect(screen.getByTestId('reliability-chart').querySelectorAll('rect.bar')).toHaveLength(10);
    expect(screen.getByTestId('bench-gaps')).toHaveTextContent('0.1961');
    expect(screen.getByTestId('bench-ocr')).toHaveTextContent('0.857');
    expect(screen.getByTestId('bench-decider')).toHaveTextContent('p = 0.69');
    expect(screen.getByTestId('bench-method')).toHaveTextContent('Built with Strands Agents.');
    for (const a of within(screen.getByTestId('bench-reports')).getAllByRole('link'))
      expect(a.getAttribute('href')).toMatch(/^https:\/\/github\.com\/Vivek0712\/ezhuthu\/blob\/main\/(eval\/reports|benchmark)\//);

    // Hard subset toggle.
    await user.click(screen.getByTestId('subset-hard'));
    expect(within(screen.getByTestId('leaderboard-table')).getAllByRole('row')[1]).toHaveTextContent('0.5741 [0.5205–0.6278]');

    // Runner: gated, not the whole page.
    const runner = screen.getByTestId('bench-runner');
    expect(within(runner).getByTestId('runner-gate')).toHaveTextContent('Sign in to run it yourself.');
    expect(screen.queryByTestId('run-benchmark')).toBeNull();
    expect(screen.queryByTestId('jsonl-file')).toBeNull();
    await user.click(within(runner).getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByTestId('run-benchmark')).toBeInTheDocument();
    expect(screen.getByTestId('jsonl-file')).toBeInTheDocument();
  });

  it('renders in Tamil too', () => {
    renderApp(<AppRoutes />, { route: '/benchmark', lang: 'ta' });
    expect(screen.getByRole('heading', { level: 1, name: 'அளவுகோல் முடிவுகள்' })).toBeInTheDocument();
    expect(screen.getByTestId('leaderboard-table')).toHaveTextContent('0.6271');
  });

  it('follows the copy rules: never "correct", "experimental" or Aivar; numbers only from summary.json', () => {
    for (const v of [...Object.values(enBench), ...Object.values(taBench)]) {
      expect(v).not.toMatch(/\bcorrect|experimental|aivar/i);
      expect(v.replace(/\{\w+\}|PR #31|v19|4\.6|5-gram|2B|95%|70%|CC BY-SA 4\.0|\b0\.05\b|\b[0-9]\b|stats\.json/g, '')).not.toMatch(/\d/);
    }
    expect(SUMMARY.leaderboard.full.rows[0]!.id).toBe('deployed');
  });
});
