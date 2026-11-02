import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { server } from '../mocks/server';
import { LearnPage } from '../pages/LearnPage';
import { HomePage } from '../pages/HomePage';
import { RestorePage } from '../pages/RestorePage';
import { SAMPLE_IMAGES, learnHref, restoreHref } from '../samples';
import { SAMPLES } from '../samples/data';
import { renderApp } from '../test/render';
import { EvolutionHero } from './EvolutionHero';
import { excerptAroundGap, SampleGallery } from './SampleGallery';
import { TrySampleImage } from './TrySampleImage';

function mockReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((q: string) => ({
      matches: reduce && q.includes('prefers-reduced-motion: reduce'),
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}
afterEach(() => vi.unstubAllGlobals());

describe('SampleGallery', () => {
  it('shows every sample with title, edition, why line, credit and real gaps', async () => {
    renderApp(<SampleGallery />, { lang: 'en' });
    const cards = await screen.findAllByRole('article');
    expect(cards).toHaveLength(SAMPLES.length);
    const s = SAMPLES[0]!;
    const card = screen.getByTestId(`sample-${s.id}`);
    expect(within(card).getByText(s.title_en)).toBeInTheDocument();
    expect(within(card).getByText(s.title_ta)).toBeInTheDocument();
    expect(within(card).getByText(s.why_en)).toBeInTheDocument();
    expect(within(card).getByText(`Edition: ${s.edition_title}`)).toBeInTheDocument();
    expect(card.querySelectorAll('mark.lacuna')).toHaveLength(s.gaps);
    expect(within(card).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute('href', s.licence_url);
    expect(within(card).getByRole('link', { name: /DHARMA/ })).toHaveAttribute('href', s.dharma_url);
    expect(within(card).getByRole('link', { name: 'Restore this' })).toHaveAttribute('href', restoreHref(s));
    expect(within(card).getByRole('link', { name: 'Practise with this' })).toHaveAttribute('href', learnHref(s));
  });

  it('filters by period and says how many are shown', async () => {
    renderApp(<SampleGallery />, { lang: 'en' });
    await screen.findAllByRole('article');
    await userEvent.click(screen.getByTestId('era-pallava'));
    const pallava = SAMPLES.filter((s) => s.era === 'pallava');
    expect(screen.getAllByRole('article')).toHaveLength(pallava.length);
    expect(screen.getByTestId('era-pallava')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(`${pallava.length} samples shown`)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId('era-all'));
    expect(screen.getAllByRole('article')).toHaveLength(SAMPLES.length);
  });

  it('shows the Tamil text and Tamil copy in Tamil', async () => {
    renderApp(<SampleGallery />, { lang: 'ta' });
    const s = SAMPLES[0]!;
    const card = await screen.findByTestId(`sample-${s.id}`);
    expect(within(card).getByText(s.why_ta)).toBeInTheDocument();
    expect(within(card).getByText(s.place_ta)).toBeInTheDocument();
    expect(card.querySelector('.sample-text')?.textContent).toBe(s.text_tamil);
  });
});

describe('HomePage hero', () => {
  it('primary CTA is the upload flow that /restore now opens on (photo tab, samples, typing one tab away)', async () => {
    renderApp(<HomePage />, { lang: 'en' });
    const cta = screen.getByTestId('cta-upload');
    expect(cta).toHaveAttribute('href', '/restore');
    expect(cta).toHaveTextContent('Upload a photo');
    expect(screen.queryByTestId('cta-restore')).toBeNull();
    expect(screen.getByTestId('cta-samples')).toHaveAttribute('href', '#samples');
    await screen.findAllByRole('article');
  });
});

describe('SampleGallery counts', () => {
  it('says "1 gap" and "2 gaps" (and the Tamil singular) by count', () => {
    const one = { ...SAMPLES[0]!, id: 'one', gaps: 1 };
    const two = { ...SAMPLES[1]!, id: 'two', gaps: 2 };
    const { unmount } = renderApp(<SampleGallery samples={[one, two]} />, { lang: 'en' });
    expect(within(screen.getByTestId('sample-one')).getByText('1 gap')).toBeInTheDocument();
    expect(within(screen.getByTestId('sample-two')).getByText('2 gaps')).toBeInTheDocument();
    unmount();
    renderApp(<SampleGallery samples={[one, two]} />, { lang: 'ta' });
    expect(within(screen.getByTestId('sample-one')).getByText('1 இடைவெளி')).toBeInTheDocument();
    expect(within(screen.getByTestId('sample-two')).getByText('2 இடைவெளிகள்')).toBeInTheDocument();
  });

  it('shows placeholders, marked busy, until the samples arrive', async () => {
    renderApp(<SampleGallery />, { lang: 'en' });
    const grid = screen.getAllByTestId('sample-grid')[0]!;
    if (grid.getAttribute('aria-busy') === 'true') expect(grid.querySelectorAll('.sample-card-skeleton')).toHaveLength(3);
    await screen.findAllByRole('article');
    expect(screen.getAllByTestId('sample-grid').every((g) => g.getAttribute('aria-busy') !== 'true')).toBe(true);
    expect(document.querySelectorAll('.sample-card-skeleton')).toHaveLength(0);
  });

  it('splits the gallery into masked passages (with their live counts) and unsolved ones', async () => {
    renderApp(<SampleGallery />, { lang: 'en' });
    await screen.findAllByRole('article');
    const masked = SAMPLES.filter((s) => s.group === 'masked');
    const unsolved = SAMPLES.filter((s) => s.group === 'unsolved');
    const mg = screen.getByTestId('sample-group-masked');
    const ug = screen.getByTestId('sample-group-unsolved');
    expect(within(mg).getAllByRole('article')).toHaveLength(masked.length);
    expect(within(ug).getAllByRole('article')).toHaveLength(unsolved.length);
    expect(within(mg).getByRole('heading', { name: 'Hidden on purpose: compare with the editors' })).toBeInTheDocument();
    expect(within(ug).getByRole('heading', { name: 'Unsolved: even the editors left this blank' })).toBeInTheDocument();
    const gaps = masked.flatMap((s) => s.recorded!.gaps);
    const filled = gaps.filter((g) => g.decision === 'fill').length;
    const matched = gaps.filter((g) => g.outcome === 'match').length;
    expect(screen.getByTestId('masked-stats')).toHaveTextContent(
      `${filled}/${gaps.length} filled · ${matched}/${filled} fills match the editors’ restoration · ${gaps.length - filled} left open for an expert`,
    );
    expect(within(mg).getAllByText('Edition reading known')).toHaveLength(masked.length);
    expect(within(ug).getAllByText('Unsolved')).toHaveLength(unsolved.length);
  });
});

describe('excerptAroundGap', () => {
  it('keeps short passages whole and always shows the first gap of long ones', () => {
    expect(excerptAroundGap('ab [?2] cd')).toBe('ab [?2] cd');
    for (const s of SAMPLES)
      for (const text of [s.text_iso, s.text_tamil]) {
        const ex = excerptAroundGap(text);
        expect(ex.length).toBeLessThanOrEqual(236);
        expect(ex).toContain('[?');
        if (text.length > 230) expect(ex).toMatch(/…/);
      }
  });
});

describe('EvolutionHero', () => {
  it('animates five stages with a pause control and decorative artwork', async () => {
    mockReducedMotion(false);
    renderApp(<EvolutionHero />, { lang: 'en' });
    const hero = screen.getByTestId('evolution-hero');
    expect(hero).toHaveAttribute('data-motion', 'animated');
    expect(hero.querySelectorAll('.evo-frame')).toHaveLength(5);
    expect(hero.querySelector('.evo-stage')).toHaveAttribute('aria-hidden', 'true');
    expect(hero.querySelector('[aria-live]')).toBeNull();
    expect(screen.getByText(/One letter, ka/)).toBeInTheDocument();
    const toggle = screen.getByTestId('evo-toggle');
    expect(toggle).toHaveTextContent('Pause animation');
    await userEvent.click(toggle);
    expect(hero).toHaveAttribute('data-paused', 'true');
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
    expect(toggle).toHaveTextContent('Play animation');
  });

  it('renders a static frame under prefers-reduced-motion', () => {
    mockReducedMotion(true);
    renderApp(<EvolutionHero />, { lang: 'en' });
    const hero = screen.getByTestId('evolution-hero');
    expect(hero).toHaveAttribute('data-motion', 'static');
    expect(hero.querySelectorAll('.evo-frame, .evo-trace, .evo-word-trace, .evo-progress')).toHaveLength(0);
    expect(screen.queryByTestId('evo-toggle')).toBeNull();
    // All five stages are visible at once, labelled.
    const labels = [...hero.querySelectorAll('.evo-pip-label')].map((n) => n.textContent);
    expect(labels).toEqual(['Tamil-Brahmi', 'Vatteluttu', 'Pallava (Grantha form)', 'Chola', 'Today']);
  });

  it('carries the Grantha-form disclaimer on the Pallava label in Tamil too', () => {
    mockReducedMotion(true);
    renderApp(<EvolutionHero />, { lang: 'ta' });
    const labels = [...screen.getByTestId('evolution-hero').querySelectorAll('.evo-pip-label')].map((n) => n.textContent);
    expect(labels[2]).toBe('பல்லவர் (கிரந்த வடிவம்)');
  });
});

describe('TrySampleImage', () => {
  it('hands the chosen picture to the upload flow as a JPEG File with its metadata', async () => {
    server.use(http.get('*/samples/:file', () => new HttpResponse(new Uint8Array([0xff, 0xd8, 0xff, 0xe0]), { headers: { 'Content-Type': 'image/jpeg' } })));
    const onPick = vi.fn();
    renderApp(<TrySampleImage onPick={onPick} />, { lang: 'en' });
    expect(screen.getAllByRole('button')).toHaveLength(SAMPLE_IMAGES.length);
    const im = SAMPLE_IMAGES[0]!;
    await userEvent.click(screen.getByTestId(`sample-image-${im.id}`));
    await waitFor(() => expect(onPick).toHaveBeenCalledTimes(1));
    const [file, meta] = onPick.mock.calls[0] as [File, typeof im];
    expect(file).toBeInstanceOf(File);
    expect(file.type).toBe('image/jpeg');
    expect(file.name).toBe(`${im.id}.jpg`);
    expect(file.size).toBe(4);
    expect(meta.expected_text).toBe(im.expected_text);
  });

  it('reports a picture that cannot be loaded', async () => {
    server.use(http.get('*/samples/:file', () => new HttpResponse(null, { status: 404 })));
    const onPick = vi.fn();
    renderApp(<TrySampleImage onPick={onPick} />, { lang: 'en' });
    await userEvent.click(screen.getByTestId(`sample-image-${SAMPLE_IMAGES[1]!.id}`));
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be loaded');
    expect(onPick).not.toHaveBeenCalled();
  });
});

describe('sample links', () => {
  it('/restore?sample= starts the form with that passage and credits it', async () => {
    const s = SAMPLES[2]!;
    renderApp(<RestorePage />, { lang: 'en', route: restoreHref(s) });
    await waitFor(() => expect(screen.getByTestId('restore-input')).toHaveValue(s.text_iso));
    expect(screen.getByTestId('gap-count')).toHaveTextContent(`${s.gaps} ${s.gaps === 1 ? 'gap found' : 'gaps found'}`);
    expect(screen.getByTestId('restore-sample-source')).toHaveTextContent(s.title_en);
  });

  it('/restore?sample= uses the Tamil text for Tamil readers', async () => {
    const s = SAMPLES[2]!;
    renderApp(<RestorePage />, { lang: 'ta', route: restoreHref(s) });
    await waitFor(() => expect(screen.getByTestId('restore-input')).toHaveValue(s.text_tamil));
  });

  it('/restore?sample= does not overwrite what the reader has typed once it is filled', async () => {
    const s = SAMPLES[2]!;
    renderApp(<RestorePage />, { lang: 'en', route: restoreHref(s) });
    const input = screen.getByTestId('restore-input');
    await waitFor(() => expect(input).toHaveValue(s.text_iso));
    await userEvent.clear(input);
    await userEvent.type(input, 'ka [[?2] ma'); // '[[' types a literal '['
    expect(input).toHaveValue('ka [?2] ma');
    expect(screen.getByTestId('gap-count')).toHaveTextContent('1 gap found');
    expect(screen.queryByTestId('restore-sample-source')).toBeNull();
  });

  it('a masked sample shows the edition reading after the result, with the recorded match state', async () => {
    for (const outcome of ['match', 'open'] as const) {
      const s = SAMPLES.find((x) => x.group === 'masked' && x.recorded!.gaps[0]!.outcome === outcome)!;
      const { unmount } = renderApp(<RestorePage />, { lang: 'en', route: restoreHref(s) });
      await waitFor(() => expect(screen.getByTestId('restore-input')).toHaveValue(s.text_iso));
      await userEvent.click(screen.getByTestId('restore-submit'));
      const reveal = await screen.findByTestId('edition-reveal');
      expect(reveal).toHaveAttribute('data-state', outcome);
      expect(within(reveal).getByTestId('reveal-edition')).toHaveTextContent(s.edition_reading!.text_iso);
      expect(within(reveal).getByTestId('reveal-edition')).toHaveTextContent(s.edition_reading!.text_tamil);
      expect(within(reveal).getByTestId('reveal-state')).toHaveTextContent(
        outcome === 'match' ? 'The system’s fill matches the editors’ restoration.' : 'The system left this gap open and asked for an expert.',
      );
      expect(within(reveal).getByRole('link', { name: /DHARMA/ })).toHaveAttribute('href', s.dharma_url);
      expect(within(reveal).getByRole('link', { name: 'CC BY-SA 4.0' })).toHaveAttribute('href', s.licence_url);
      expect(reveal.textContent).not.toMatch(/\bcorrect\b|experimental/i);
      // The editors did restore a masked gap, so an abstain asks an expert rather than claiming "experts are unsure".
      if (outcome === 'open') {
        expect(screen.getByTestId('abstain')).toHaveTextContent('Needs an expert');
        expect(screen.getByTestId('abstain')).not.toHaveTextContent('Experts are unsure');
      }
      unmount();
    }
  });

  it('a masked sample in Tamil shows the reveal in Tamil', async () => {
    const s = SAMPLES.find((x) => x.group === 'masked' && x.recorded!.gaps[0]!.outcome === 'match')!;
    renderApp(<RestorePage />, { lang: 'ta', route: restoreHref(s) });
    await waitFor(() => expect(screen.getByTestId('restore-input')).toHaveValue(s.text_tamil));
    await userEvent.click(screen.getByTestId('restore-submit'));
    const reveal = await screen.findByTestId('edition-reveal');
    expect(reveal).toHaveAttribute('data-state', 'match');
    expect(within(reveal).getByTestId('reveal-state')).toHaveTextContent('அமைப்பின் நிரப்பு பதிப்பாசிரியர்களின் மீட்டமைப்புடன் பொருந்துகிறது.');
  });

  it('an unsolved sample says there is no edition reading to compare with; an edited passage gets no reveal', async () => {
    const s = SAMPLES.find((x) => x.group === 'unsolved')!;
    renderApp(<RestorePage />, { lang: 'en', route: restoreHref(s) });
    const input = screen.getByTestId('restore-input');
    await waitFor(() => expect(input).toHaveValue(s.text_iso));
    await userEvent.click(screen.getByTestId('restore-submit'));
    const reveal = await screen.findByTestId('edition-reveal');
    expect(reveal).toHaveAttribute('data-state', 'unsolved');
    expect(reveal).toHaveTextContent('Unsolved: even the editors left this blank');
    await userEvent.type(input, ' ka');
    await userEvent.click(screen.getByTestId('restore-submit'));
    await waitFor(() => expect(screen.queryByTestId('edition-reveal')).toBeNull());
  });

  it('"Practise with this" starts a lesson on that inscription at the suggested level', async () => {
    const s = SAMPLES.find((x) => x.learn_level === 'L3')!;
    renderApp(<LearnPage />, { lang: 'en', route: learnHref(s) });
    expect(await screen.findByRole('heading', { level: 1, name: s.edition_title })).toBeInTheDocument();
    expect(screen.getByTestId('lesson-source')).toHaveTextContent('CC BY-SA 4.0');
  });
});
