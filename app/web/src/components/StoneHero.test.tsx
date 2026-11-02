import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { Route, Routes, useLocation } from 'react-router-dom';
import { AppRoutes } from '../App';
import heroRaw from '../hero/hero-reading.json';
import heroView from '../hero/hero-view.json';
import glyphs from '../hero/runs/glyphs.json';
import restore from '../hero/runs/restore.json';
import { HERO } from '../hero/heroData';
import { buildTimeline } from '../hero/timeline';
import { en, ta } from '../i18n/strings';
import { renderApp } from '../test/render';

const cleanText = (el: Element) => (el.textContent ?? '').replace(/\s+/g, ' ').trim();

describe('stone hero (home)', () => {
  it('renders the composed static frame when it cannot animate (jsdom has no element.animate)', () => {
    renderApp(<AppRoutes />, { route: '/' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveAttribute('data-motion', 'static');
    expect(screen.queryByTestId('stone-toggle')).toBeNull();
    // The reading is real text, in Tamil, one paragraph per row: the letters the Reader matched box by box, run
    // together as on the stone, with the letter the Decider left open as a "?" tile.
    const paras = hero.querySelectorAll('.sh-ta[lang="ta"]');
    expect(paras).toHaveLength(glyphs.rows.length);
    glyphs.rows.forEach((row, r) => {
      const expected = row.glyphs.map((g) => (g.confidence !== null && g.confidence >= 0.5 && g.ta ? g.ta : 'gap')).join('');
      expect(cleanText(paras[r]!).replace(/\?/g, '')).toBe(expected);
    });
    expect(hero.querySelectorAll('.sh-ta .sh-gap')).toHaveLength(restore.response.gaps.length);
    // Every box has a badge; the static frame shows two match cards.
    expect(hero.querySelectorAll('.sh-badge')).toHaveLength(glyphs.rows.reduce((n, r) => n + r.n_boxes, 0));
    expect(hero.querySelectorAll('.sh-card[data-static]')).toHaveLength(2);
    expect(hero.querySelector('.sh-card[data-card="0"]')).toHaveTextContent('கி');
    expect(hero.querySelector('.sh-card[data-card="0"]')).toHaveTextContent('80%');
    expect(hero.querySelector('.sh-card[data-card="0"]')).toHaveTextContent('Chola-era Tamil');
    // Row confidence chips sit in their own column, one per row.
    expect(Array.from(hero.querySelectorAll('.sh-lc')).map(cleanText)).toEqual(heroRaw.glyphs.rows.map((r) => `${Math.round(r.mean_confidence * 100)}%`));
    // Letters are indexed within their own row (the timeline schedules per row).
    hero.querySelectorAll('.sh-line').forEach((line) => {
      const ks = Array.from(line.querySelectorAll<HTMLElement>('[data-anim="land"]')).map((e) => Number(e.dataset.k));
      expect(ks).toEqual(ks.map((_, i) => i));
    });
    // What happened to the uncertain letter, in plain words, with the real numbers.
    expect(hero).toHaveTextContent('Line 3: the Reader named this letter ண்ணி at 45%, under 50%. The Restorer’s best fill, குப் at 37%, was under 50% too, so the Strands Decider left it open.');
    expect(hero).toHaveTextContent('46 letters matched to modern Tamil');
    expect(hero).toHaveTextContent('mean confidence 65%');
    expect(hero).toHaveTextContent('1 left open');
    expect(hero).toHaveTextContent('Letters under 50% are flagged as uncertain.');
    // No hedging labels, no claims of correctness or of anything being queued.
    expect(hero.textContent).not.toMatch(/experimental|not checked|edition|goes to expert review|\bcorrect\b|deciph/i);
    // Credits: photo author, licence, source, and the reading's maker.
    expect(screen.getByTestId('hero-credit')).toHaveAttribute('href', expect.stringContaining('commons.wikimedia.org'));
    expect(within(hero).getByRole('link', { name: 'CC BY 2.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/2.0/');
    expect(hero).toHaveTextContent('Richard Mortel');
    expect(hero).toHaveTextContent('Reading by Ezhuthu, built with Strands Agents');
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
    // The headline and calls to action come before the stone in the page (phones show them first).
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.compareDocumentPosition(screen.getByTestId('stone-hero')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    const scholars = screen.getByTestId('scholars');
    expect(within(scholars).getByRole('link', { name: 'Expert review' })).toHaveAttribute('href', '/review');
    expect(within(scholars).getByRole('link', { name: 'Benchmark' })).toHaveAttribute('href', '/benchmark');
  });

  it('is in Tamil when the app is', () => {
    renderApp(<AppRoutes />, { route: '/', lang: 'ta' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveTextContent('வாசிப்பாளர்');
    expect(hero).toHaveTextContent('சோழர் காலத் தமிழ்');
    expect(hero).toHaveTextContent('Strands Agents');
  });
});

describe('stone hero animation: one track per element, and the loop has no seam', () => {
  type Rec = { el: Element; kf: Keyframe[]; opts: KeyframeAnimationOptions };
  let recs: Rec[] = [];
  const proto = Element.prototype as unknown as { animate?: unknown };
  const original = proto.animate;
  const matchMedia = window.matchMedia;

  beforeEach(() => {
    recs = [];
    proto.animate = function (this: Element, kf: Keyframe[], opts: KeyframeAnimationOptions) {
      recs.push({ el: this, kf, opts });
      return { cancel() {}, pause() {}, play() {}, playState: 'running', onfinish: null } as unknown as Animation;
    };
    window.matchMedia = ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
  });
  afterEach(() => {
    proto.animate = original;
    window.matchMedia = matchMedia;
  });

  async function startCycle() {
    renderApp(<AppRoutes />, { route: '/' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveAttribute('data-motion', 'animated');
    hero.querySelector('.sh-kb > picture img')!.dispatchEvent(new Event('load'));
    await waitFor(() => expect(hero).toHaveAttribute('data-phase', 'running'));
    return hero;
  }

  it('animates every hero element over exactly one cycle, ending where the next cycle begins', async () => {
    const hero = await startCycle();
    const tl = buildTimeline(HERO.rows.map((r) => r.glyphs.length), HERO.featured, HERO.gaps.length);
    const inHero = recs.filter((r) => hero.contains(r.el) && r.kf.length > 0);
    expect(inHero.length).toBeGreaterThan(150);
    const perEl = new Map<Element, number>();
    for (const r of inHero) {
      expect(r.opts.duration).toBe(tl.cycle);
      expect(r.opts.delay ?? 0).toBe(0);
      expect(r.kf[0]!.offset).toBe(0);
      expect(r.kf[r.kf.length - 1]!.offset).toBe(1);
      perEl.set(r.el, (perEl.get(r.el) ?? 0) + 1);
      if (r.el.classList.contains('sh-kb')) continue;
      // Everything except the photo starts hidden and is hidden again at the end: nothing blinks at the seam.
      const first = r.kf[0]!;
      const last = r.kf[r.kf.length - 1]!;
      if ('opacity' in first) expect(last.opacity).toBe(first.opacity);
      if ('strokeDashoffset' in first) {
        expect(first.strokeDashoffset).toBe(100);
        expect(last.strokeDashoffset).toBe(100);
      }
    }
    // One animation per element: no two animations composite over each other.
    for (const n of perEl.values()) expect(n).toBe(1);
    // Boxes fade out from their resting opacity, not from full (no flash of all boxes before the fade).
    const box = inHero.find((r) => r.el.classList.contains('sh-box'))!;
    const fade = box.kf.filter((k) => (k.offset as number) >= tl.fadeOut / tl.cycle);
    expect(fade[0]!.opacity).toBeLessThan(1);
    // The photo fades in on the first cycle only and is fully shown at the end of it.
    const kb = inHero.find((r) => r.el.classList.contains('sh-kb'))!;
    expect(kb.kf[0]!.opacity).toBe(0);
    expect(kb.kf[kb.kf.length - 1]!.opacity).toBe(1);
  });

  it('reads letters out in order: every letter of row r lands before row r+1 starts landing', async () => {
    const hero = await startCycle();
    const tl = buildTimeline(HERO.rows.map((r) => r.glyphs.length), HERO.featured, HERO.gaps.length);
    const landed = (el: Element) => {
      const kf = recs.find((r) => r.el === el)!.kf;
      // The first keyframe where the letter is at rest in place.
      return kf.find((k) => k.transform === 'none' && k.opacity === 1)!.offset as number;
    };
    const rows = Array.from(hero.querySelectorAll('.sh-line')).map((l) => Array.from(l.querySelectorAll('[data-anim="land"]')).map(landed));
    rows.forEach((row, r) => {
      for (let i = 1; i < row.length; i++) expect(row[i]).toBeGreaterThan(row[i - 1]!);
      if (r > 0) expect(row[row.length - 1]).toBeGreaterThan(rows[r - 1]![rows[r - 1]!.length - 1]!);
      expect(row[0]! * tl.cycle).toBeGreaterThan(tl.gap.end);
    });
  });
});

describe('stone hero under reduced motion', () => {
  const matchMedia = window.matchMedia;
  afterEach(() => {
    window.matchMedia = matchMedia;
  });
  it('shows the static frame even where element.animate exists', () => {
    const proto = Element.prototype as unknown as { animate?: unknown };
    const original = proto.animate;
    proto.animate = () => ({ cancel() {} });
    window.matchMedia = ((q: string) => ({ matches: q.includes('reduce'), media: q, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
    try {
      renderApp(<AppRoutes />, { route: '/' });
      const hero = screen.getByTestId('stone-hero');
      expect(hero).toHaveAttribute('data-motion', 'static');
      expect(hero.querySelectorAll('.sh-card[data-static]')).toHaveLength(2);
      expect(hero.querySelectorAll('.sh-ta[lang="ta"]')).toHaveLength(HERO.rows.length);
      expect(screen.queryByTestId('stone-replay')).toBeNull();
    } finally {
      proto.animate = original;
    }
  });
});

describe('hero data (src/hero/hero-view.json) is the real run, not hand-written', () => {
  it('matches the letter-by-letter Reader run and the Restorer run it was built from', () => {
    expect(HERO.rows.map((r) => r.glyphs.map((g) => [g.ta, g.c]))).toEqual(glyphs.rows.map((r) => r.glyphs.map((g) => [g.ta ?? '', g.confidence])));
    expect(HERO.letters).toBe(glyphs.rows.reduce((n, r) => n + r.n_boxes, 0));
    expect(HERO.gaps).toHaveLength(restore.response.gaps.length);
    expect(HERO.gaps.map((x) => x.g.gap!.decision)).toEqual(restore.response.gaps.map((g) => g.decision));
    expect(HERO.gaps.map((x) => x.g.gap!.best!.c)).toEqual(restore.response.gaps.map((g) => g.candidates[0]!.confidence));
    expect(HERO.fills).toBe(restore.response.gaps.filter((g) => g.decision !== 'abstain').length);
    // Letters under the cut-off are exactly the gaps the Restorer was given.
    const under = glyphs.rows.flatMap((r) => r.glyphs.filter((g) => !g.ta || (g.confidence ?? 0) < 0.5));
    expect(under).toHaveLength(restore.response.gaps.length);
    expect(HERO.mean).toBe(heroRaw.glyphs.mean_confidence);
  });
  it('ships a trimmed view that agrees with the full record', () => {
    expect(heroView.boxes).toEqual(heroRaw.boxes);
    expect(heroView.rows.map((r) => r.c)).toEqual(heroRaw.glyphs.rows.map((r) => r.mean_confidence));
    expect(JSON.stringify(heroView).length).toBeLessThan(JSON.stringify(heroRaw).length * 0.3);
    expect(JSON.stringify(heroView)).not.toMatch(/note|candidates|model/);
  });
  it('has one box per matched letter, all inside the photo', () => {
    expect(HERO.boxes.map((r) => r.length)).toEqual(HERO.rows.map((r) => r.glyphs.length));
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
  it('records the photo licence, and no edition or match rate (none could be found)', () => {
    expect(heroRaw.photo.licence).toBe('CC BY 2.0');
    expect(heroRaw.photo.author).toBe('Richard Mortel');
    expect(heroRaw.edition).toBeNull();
    expect(heroRaw.match_rate).toBeNull();
    const calls = heroRaw.live_calls;
    expect(calls.reader + calls.glyphs + calls.restorer).toBeLessThanOrEqual(60);
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
