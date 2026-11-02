import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { Route, Routes, useLocation } from 'react-router-dom';
import { AppRoutes } from '../App';
import heroRaw from '../hero/hero-reading.json';
import read from '../hero/runs/read.json';
import restore from '../hero/runs/restore.json';
import { HERO } from '../hero/heroData';
import { en, ta } from '../i18n/strings';
import { renderApp } from '../test/render';

describe('stone hero (home)', () => {
  it('renders the composed final frame when it cannot animate (jsdom has no element.animate)', () => {
    renderApp(<AppRoutes />, { route: '/' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveAttribute('data-motion', 'static');
    expect(screen.queryByTestId('stone-toggle')).toBeNull();
    // The reading is real text, in Tamil, one paragraph per line, from the actual Reader run.
    const ta = hero.querySelectorAll('p[lang="ta"]');
    expect(ta).toHaveLength(read.lines.length);
    read.lines.forEach((l, i) => expect(ta[i]!.textContent!.replace(/\s+/g, ' ')).toContain(l.text_tamil.split(' ')[0]!));
    // Each gap the restorer abstained on is a "?" tile with an accessible name.
    expect(hero.querySelectorAll('.sh-gap')).toHaveLength(restore.response.gaps.length);
    expect(within(hero).getAllByText('gap').length).toBeGreaterThanOrEqual(restore.response.gaps.length);
    // Honest labels: experimental, no edition, sent to expert review.
    expect(hero).toHaveTextContent('Experimental reading, not checked against an edition');
    expect(hero).toHaveTextContent('Under 0.5, so this reading goes to expert review.');
    expect(hero).toHaveTextContent('no error rate and no translation');
    expect(hero.textContent).not.toMatch(/\bcorrect\b|deciph/i);
    // Photo credit with author, licence link and source.
    expect(screen.getByTestId('hero-credit')).toHaveAttribute('href', expect.stringContaining('commons.wikimedia.org'));
    expect(within(hero).getByRole('link', { name: 'CC BY 2.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/2.0/');
    expect(hero).toHaveTextContent('Richard Mortel');
    // The artwork is hidden from assistive tech; the reading is not.
    expect(hero.querySelector('.sh-photo')).toHaveAttribute('aria-hidden', 'true');
    expect(hero.querySelector('.sh-pipe')).toHaveAttribute('aria-hidden', 'true');
    expect(hero.querySelector('.sh-out')?.closest('[aria-hidden="true"]')).toBeNull();
  });

  it('keeps the era-evolution strip and offers the three calls to action', () => {
    renderApp(<AppRoutes />, { route: '/' });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Learn to read the stone. Help read the backlog.');
    expect(screen.getByTestId('evolution-hero')).toBeInTheDocument();
    expect(screen.getByTestId('cta-upload')).toHaveAttribute('href', '/restore');
    expect(screen.getByTestId('cta-samples')).toHaveAttribute('href', '#samples');
    expect(screen.getByTestId('cta-scholars')).toHaveAttribute('href', '#scholars');
    const scholars = screen.getByTestId('scholars');
    expect(within(scholars).getByRole('link', { name: 'Expert review' })).toHaveAttribute('href', '/review');
    expect(within(scholars).getByRole('link', { name: 'Benchmark' })).toHaveAttribute('href', '/benchmark');
  });

  it('is in Tamil when the app is', () => {
    renderApp(<AppRoutes />, { route: '/', lang: 'ta' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveTextContent('வாசிப்பாளர்');
    expect(hero).toHaveTextContent('வல்லுநர் மதிப்பாய்வுக்குச் செல்கிறது');
  });
});

describe('hero data (src/hero/hero-reading.json) is the real run, not hand-written', () => {
  it('matches the Reader and Restorer responses it was built from', () => {
    expect(HERO.lines.map((l) => l.iso)).toEqual(read.lines.map((l) => l.text));
    expect(HERO.lines.map((l) => l.ta)).toEqual(read.lines.map((l) => l.text_tamil));
    expect(HERO.confidence).toBe(read.confidence);
    expect(HERO.gaps).toBe(restore.response.gaps.length);
    expect(HERO.fills).toBe(restore.response.gaps.filter((g) => g.decision !== 'abstain').length);
    const gapsInReading = read.lines.reduce((n, l) => n + l.gaps, 0);
    expect(HERO.gaps).toBe(gapsInReading);
  });
  it('has one row of letter boxes per reading line, all inside the photo', () => {
    expect(HERO.boxes).toHaveLength(read.lines.length);
    for (const row of HERO.boxes)
      for (const [x0, y0, x1, y1] of row) {
        expect(x0).toBeGreaterThanOrEqual(0);
        expect(y0).toBeGreaterThanOrEqual(0);
        expect(x1).toBeLessThanOrEqual(HERO.photo.width);
        expect(y1).toBeLessThanOrEqual(HERO.photo.height);
        expect(x1).toBeGreaterThan(x0);
        expect(y1).toBeGreaterThan(y0);
      }
  });
  it('records the photo licence and states that there is no edition to score against', () => {
    expect(heroRaw.photo.licence).toBe('CC BY 2.0');
    expect(heroRaw.photo.author).toBe('Richard Mortel');
    expect(heroRaw.edition).toBeNull();
    expect(heroRaw.cer).toBeNull();
    expect(heroRaw.live_calls.reader + heroRaw.live_calls.restorer).toBeLessThanOrEqual(20);
  });
});

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

describe('renamed routes keep old links working', () => {
  it('/learn redirects to /practice with its query string', async () => {
    renderApp(
      <>
        <AppRoutes />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </>,
      { route: '/learn?level=L2' },
    );
    expect(await screen.findByTestId('where')).toHaveTextContent('/practice?level=L2');
    expect(screen.getByRole('heading', { level: 1, name: 'Practice' })).toBeInTheDocument();
  });
  it('/test redirects to /benchmark', async () => {
    renderApp(
      <>
        <AppRoutes />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </>,
      { route: '/test' },
    );
    expect(await screen.findByTestId('where')).toHaveTextContent('/benchmark');
  });
});

describe('positioning C copy', () => {
  const all = [...Object.values(en), ...Object.values(ta)].join('\n');
  it('uses the precise Federal wording, never the old "70,000" backlog', () => {
    expect(all).not.toMatch(/70,000|70000/);
    expect(en['about.why2']).toMatch(/about 23 epigraphists.*1 lakh.*1886.*30,000 to 35,000.*The Federal, 3 Aug 2021/);
  });
  it('never makes the claims the positioning brief rules out', () => {
    expect(all).not.toMatch(/Strands AI|AWS AI\b|deciphers|replaces? epigraphists|clears? the backlog|validated by/i);
    expect(all).not.toMatch(/\b(?:are|is) correct\b/i);
  });
  it('About lists who it is for and what it cannot do yet', () => {
    renderApp(<AppRoutes />, { route: '/about' });
    expect(screen.getByTestId('who-for')).toHaveTextContent('New epigraphists');
    const limits = screen.getByTestId('limits');
    expect(limits).toHaveTextContent('cannot read Tamil-Brahmi from photos');
    expect(limits).toHaveTextContent('No scholar has validated it yet');
    expect(limits).toHaveTextContent('match expert restorations');
  });
});
