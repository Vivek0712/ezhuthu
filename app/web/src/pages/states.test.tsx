import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import type { PracticeItem } from '../api/client';
import { GlyphTile } from '../components/GlyphTile';
import { I18nProvider } from '../i18n/I18nProvider';
import { VATTELUTTU } from '../lib/vatteluttu';
import { server } from '../mocks/server';
import { renderApp } from '../test/render';

async function startLesson(level = 'L5') {
  const user = userEvent.setup();
  renderApp(<AppRoutes />, { route: '/learn' });
  await user.click(screen.getByTestId(`level-${level}`));
  await user.click(screen.getByTestId('start-lesson'));
  await screen.findByTestId('glyph-tile');
  return user;
}
async function answer(user: ReturnType<typeof userEvent.setup>, text: string) {
  await user.type(screen.getByTestId('answer-input'), text);
  await user.click(screen.getByTestId('check-answer'));
  return screen.findByTestId('feedback');
}

describe('tutor: decider confidence', () => {
  it('shows the decider confidence when the decider decided', async () => {
    const user = await startLesson();
    const fb = await answer(user, 'ம');
    expect(within(fb).getByTestId('decision')).toHaveTextContent('Confidence 68%');
    expect(within(fb).queryByTestId('decided-by-rules')).toBeNull();
  });

  it('says "decided by rules", never "confidence 0%", when decider_confidence is null', async () => {
    const user = await startLesson();
    await answer(user, 'ம'); // hint (decider)
    await answer(user, 'ம'); // repeat (decider)
    await answer(user, 'ம'); // the attempt limit: rules advance, decider_confidence null
    const fb = await waitFor(() => {
      const el = screen.getByTestId('feedback');
      expect(el).toHaveTextContent('decided by rules');
      return el;
    });
    expect(fb).not.toHaveTextContent(/0%/);
    expect(fb).not.toHaveTextContent(/Confidence/);
    expect(within(fb).getByTestId('decision')).toHaveTextContent('Tutor decision: move on · decided by rules');
    expect(screen.getByTestId('next-item')).toBeInTheDocument();
  });

  it('says it in Tamil too', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn', lang: 'ta' });
    await user.click(screen.getByTestId('level-L5'));
    await user.click(screen.getByTestId('start-lesson'));
    await screen.findByTestId('glyph-tile');
    for (let i = 0; i < 3; i++) await answer(user, 'ம');
    await waitFor(() => expect(screen.getByTestId('decided-by-rules')).toHaveTextContent('விதிகளின்படி முடிவு'));
  });
});

describe('tutor: async lesson explanation (context_update)', () => {
  it('shows the template explanation with a pending note, then the tutor team explanation after the next answer', async () => {
    const user = await startLesson();
    expect(screen.getByTestId('explanation')).toHaveTextContent('This lesson comes from a real inscription (c. 2nd c. BCE).');
    expect(screen.getByTestId('explanation-pending')).toBeInTheDocument();
    expect(screen.queryByTestId('explanation-updated')).toBeNull();

    await answer(user, 'ம');
    await waitFor(() => expect(screen.getByTestId('explanation')).toHaveTextContent('Stone beds were cut for Jain monks in the Mangulam caves.'));
    expect(screen.queryByTestId('explanation-pending')).toBeNull();
    expect(screen.getByTestId('explanation-updated')).toHaveTextContent('Explanation from the tutor team');
    // The lesson's facts stay; only the explanation changed.
    expect(screen.getByTestId('lesson-context')).toHaveTextContent('Neṭuñceḻiyaṉ');

    // Delivered once: the next answer has no context_update and the explanation stays.
    await answer(user, 'க');
    expect(screen.getByTestId('explanation')).toHaveTextContent('Mangulam caves');
  });

  it('keeps the template explanation when no update ever arrives (best effort)', async () => {
    server.use(
      http.post('/api/answer', () =>
        HttpResponse.json({ correct: false, feedback_ta: 'இன்னும் இல்லை.', feedback_en: 'Not yet.', next_action: 'repeat', decider_confidence: 0.6 }),
      ),
    );
    const user = await startLesson();
    await answer(user, 'ம');
    expect(screen.getByTestId('explanation')).toHaveTextContent('This lesson comes from a real inscription');
    expect(screen.getByTestId('explanation-pending')).toBeInTheDocument();
  });

  it('credits the DHARMA edition and its licence on the lesson', async () => {
    await startLesson();
    const src = screen.getByTestId('lesson-source');
    expect(src).toHaveTextContent('Neṭuñceḻiyaṉ (Pandya) · Pandya · c. 2nd c. BCE');
    expect(within(src).getByRole('link', { name: /DHARMA edition/ })).toHaveAttribute('href', 'https://dharmalekha.info/');
    expect(within(src).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by-sa/4.0/');
  });

  it('makes no DHARMA claim for the learner’s own text', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn' });
    await user.type(screen.getByRole('textbox'), 'kal');
    await user.click(screen.getByTestId('start-lesson'));
    await screen.findByTestId('glyph-tile');
    expect(screen.getByTestId('lesson-source')).not.toHaveTextContent(/DHARMA|CC BY/);
  });
});

describe('review queue: 409 on a second review', () => {
  async function signIn() {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/review' });
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    await screen.findByTestId('queue-q-0004');
    return user;
  }

  it('treats an item another reviewer already reviewed as gone, not as an error', async () => {
    const user = await signIn();
    await user.click(screen.getByTestId('approve-q-0004'));
    expect(await screen.findByTestId('review-notice')).toHaveTextContent('Another reviewer already reviewed this item');
    expect(screen.queryByTestId('queue-q-0004')).toBeNull();
    expect(screen.getByTestId('reviewed')).toHaveTextContent('q-0004: already reviewed elsewhere');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('still shows other failures as errors', async () => {
    server.use(http.post('/api/queue/:id', () => HttpResponse.json({ error: { code: 'forbidden', message: 'experts group required' } }, { status: 403 })));
    const user = await signIn();
    await user.click(screen.getByTestId('approve-q-0002'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('experts group required');
    expect(alert).toHaveTextContent('forbidden · HTTP 403');
    expect(screen.getByTestId('queue-q-0002')).toBeInTheDocument();
  });

  it('shows the empty state when nothing is waiting', async () => {
    server.use(http.get('/api/queue', () => HttpResponse.json({ items: [] })));
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/review' });
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByTestId('review-empty')).toHaveTextContent('The queue is empty.');
  });
});

describe('error and loading states', () => {
  it('shows a friendly server error with a reference and no server internals', async () => {
    server.use(
      http.post('/api/restore', () =>
        HttpResponse.json({ error: { code: 'agent_error', message: 'KeyError: Traceback (most recent call last)' } }, { status: 500 }),
      ),
    );
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    await user.click(screen.getByTestId('use-sample'));
    await user.click(screen.getByTestId('restore-submit'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Ezhuthu could not finish this request');
    expect(alert).toHaveTextContent('agent_error · HTTP 500');
    expect(alert).not.toHaveTextContent(/Traceback|KeyError/);
  });

  it('says it could not reach Ezhuthu when the network fails', async () => {
    server.use(http.post('/api/lesson', () => HttpResponse.error()));
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/learn' });
    await user.click(screen.getByTestId('start-lesson'));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Could not reach Ezhuthu');
    expect(within(alert).getByRole('button', { name: 'Try again' })).toBeInTheDocument();
  });

  it('shows skeleton lines, not a spinner, while the queue loads', async () => {
    let release!: () => void;
    server.use(http.get('/api/queue', () => new Promise<Response>((r) => (release = () => r(HttpResponse.json({ items: [] }))))));
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/review' });
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByTestId('skeleton')).toBeInTheDocument();
    expect(document.querySelector('.spinner')).toBeNull();
    release();
    await screen.findByTestId('review-empty');
  });
});

describe('Vatteluttu glyphs from the design system', () => {
  const base: PracticeItem = { item_id: 'x', type: 'letter', prompt_ta: 'இந்த எழுத்து என்ன?', prompt_en: 'Which letter is this?', script_level: 'L4', answer_hidden: true };

  it('draws a vatteluttu:<iso> reference inline from design/glyphs/vatteluttu.json, in the text colour', () => {
    render(
      <I18nProvider initial="en">
        <GlyphTile item={{ ...base, glyph_svg: 'vatteluttu:ka' }} label="Which letter is this?" />
      </I18nProvider>,
    );
    const svg = screen.getByTestId('glyph-ref');
    expect(svg.querySelector('path')?.getAttribute('d')).toBe(VATTELUTTU.ka!.d);
    expect(svg.querySelector('g')?.getAttribute('stroke')).toBe('currentColor');
    expect(svg.getAttribute('aria-label')).toBe('L4 · Vatteluttu: Which letter is this?'); // era and prompt, never the answer
    expect(screen.getByTestId('glyph-tile').querySelector('img')).toBeNull();
  });

  it('uses the design drawings for ka, ta, pa and ma and keeps the app’s ṉa', () => {
    expect(VATTELUTTU.ka!.d).toBe('M50 13V87M17 47C25 38 39 39 50 50C61 61 75 62 83 53');
    expect(Object.keys(VATTELUTTU)).toEqual(expect.arrayContaining(['a', 'ka', 'ma', 'e', 'ḻa', 'ta', 'pa', 'ṉa']));
    expect(VATTELUTTU.na).toBe(VATTELUTTU['ṉa']);
  });

  it('still renders server SVG markup as an image (no inline markup)', () => {
    render(
      <I18nProvider initial="en">
        <GlyphTile item={{ ...base, glyph_svg: '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>' }} label="q" />
      </I18nProvider>,
    );
    expect(screen.getByTestId('glyph-tile').querySelector('img')?.getAttribute('src')).toMatch(/^data:image\/svg\+xml/);
    expect(screen.getByTestId('glyph-tile').querySelector('script')).toBeNull();
  });
});

describe('layout', () => {
  it('shows the brand lockup and Tamil wordmark, and hides Review from people who are not experts', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/' });
    const brand = screen.getByTestId('brand');
    expect(brand).toHaveAccessibleName('எழுத்து · Ezhuthu, home');
    const srcs = [...brand.querySelectorAll('img')].map((i) => i.getAttribute('src'));
    expect(srcs.join(' ')).toMatch(/lockup-horizontal-color\.svg/);
    expect(srcs.join(' ')).toMatch(/lockup-horizontal-reversed\.svg/);
    expect(srcs.join(' ')).toMatch(/wordmark-ta-color\.svg/);
    const tabs = screen.getByTestId('tabbar');
    expect(within(tabs).queryByRole('link', { name: 'Review' })).toBeNull();
    expect(within(screen.getByRole('navigation', { name: 'primary' })).queryByRole('link', { name: 'Review' })).toBeNull();
    await user.click(screen.getByTestId('menu-toggle'));
    await user.click(within(screen.getByRole('navigation', { name: 'mobile' })).getByRole('button', { name: 'Sign in' }));
    expect(within(screen.getByTestId('tabbar')).getByRole('link', { name: 'Review' })).toBeInTheDocument();
  });

  it('credits DHARMA under CC BY-SA 4.0 in the footer and on every data page', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/restore' });
    const footer = screen.getByTestId('footer-credit');
    expect(footer).toHaveTextContent('Inscription texts: DHARMA, CC BY-SA 4.0');
    expect(within(footer).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by-sa/4.0/');
    await user.click(screen.getByTestId('use-sample'));
    await user.click(screen.getByTestId('restore-submit'));
    expect(await screen.findByTestId('restore-credit')).toHaveTextContent('DHARMA, CC BY-SA 4.0');
    expect(document.body.textContent).not.toMatch(/CC BY 4\.0/);
  });

  it('credits the benchmark licence on the Test page', async () => {
    const user = userEvent.setup();
    renderApp(<AppRoutes />, { route: '/test' });
    await user.click(within(screen.getByTestId('auth-gate')).getByRole('button', { name: 'Sign in' }));
    expect(await screen.findByTestId('benchmark-credit')).toHaveTextContent('shared under the same licence, CC BY-SA 4.0');
  });
});
