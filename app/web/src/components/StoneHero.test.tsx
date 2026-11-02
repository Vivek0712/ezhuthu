import { screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { Route, Routes, useLocation } from 'react-router-dom';
import { AppRoutes } from '../App';
import heroRaw from '../hero/hero-reading.json';
import heroView from '../hero/hero-view.json';
import glyphs from '../hero/runs/glyphs.json';
import interp from '../hero/runs/interpret.json';
import restore from '../hero/runs/restore.json';
import { BADGE_EDGE_X, BADGE_EDGE_Y, BADGE_HALF_H, BADGE_HALF_W, HERO } from '../hero/heroData';
import { buildTimeline } from '../hero/timeline';
import { en, ta } from '../i18n/strings';
import { enHero, taHero } from '../i18n/strings-hero';
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
    // What happened to the uncertain letter, in plain words, with the real numbers (the deployed Restorer's calibrated
    // confidence and threshold).
    expect(hero).toHaveTextContent('Line 3: one letter is too worn to be sure (45%). The best fill scored 8%, under the 49% needed, so rather than guess, Ezhuthu marks it ? for an expert.');
    expect(hero).toHaveTextContent('46 carved letters named in modern Tamil');
    expect(hero).toHaveTextContent('the Reader’s mean confidence 65%');
    expect(hero).toHaveTextContent('1 left open');
    expect(hero).toHaveTextContent('Letters under 50% are flagged as uncertain.');
    // WORDS: the letters of each row are grouped into the Interpreter's words, each underlined in its tint.
    const words = interp.response.words;
    expect(hero.querySelectorAll('.sh-wline')).toHaveLength(words.reduce((n, w) => n + new Set(w.letters.map(([r]) => r)).size, 0));
    words.forEach((w, k) => {
      const letters = Array.from(hero.querySelectorAll(`.sh-word[data-w="${k}"] [data-anim="land"]`));
      expect(letters.map((l) => [Number(l.closest<HTMLElement>('[data-line]')!.dataset.line), Number((l as HTMLElement).dataset.k)])).toEqual(w.letters);
    });
    expect(hero).toHaveTextContent(`${words.length} words, ${words.filter((w) => (w.confidence ?? 0) >= 0.5).length} at 50% or more`);
    // PHRASE and MEANING, in today's Tamil and in English, as the Interpreter gave them.
    const meaning = screen.getByTestId('hero-meaning');
    expect(cleanText(meaning.querySelector('.sh-phrase')!)).toBe(interp.response.phrase_tamil);
    expect(meaning.querySelector('.sh-phrase-iso')).toHaveTextContent(interp.response.phrase_iso);
    expect(meaning.querySelector('.sh-mean-en')).toHaveTextContent(interp.response.meaning_en);
    expect(meaning.querySelector('.sh-mean-ta')).toHaveTextContent(interp.response.meaning_ta);
    // The meaning's chip says what its % measures (the legend above is about letters).
    expect(meaning.querySelector('.sh-mc')).toHaveTextContent(`confidence ${Math.round(interp.response.confidence * 100)}%`);
    // English first in English.
    expect(Array.from(meaning.querySelectorAll('[data-anim^="mean-"]:not([data-anim="mean-head"])')).map((e) => e.getAttribute('lang'))).toEqual(['en', 'ta']);
    // The panel heading covers every stage it stays up for.
    expect(hero.querySelector('.sh-out-head')).toHaveTextContent('Modern Tamil: letters, words, meaning');
    // Every badge sits inside the photo, the last carved line included.
    hero.querySelectorAll<HTMLElement>('.sh-badge').forEach((b) => {
      expect(parseFloat(b.style.top)).toBeLessThanOrEqual(100 * (1 - ((BADGE_HALF_H + BADGE_EDGE_Y) * HERO.photo.width) / HERO.photo.height) + 1e-6);
      expect(parseFloat(b.style.left)).toBeGreaterThanOrEqual(100 * (BADGE_HALF_W + BADGE_EDGE_X) - 1e-6);
      expect(parseFloat(b.style.left)).toBeLessThanOrEqual(100 * (1 - BADGE_HALF_W - BADGE_EDGE_X) + 1e-6);
    });
    expect(hero.querySelector('[data-node="interpreter"]')).toHaveTextContent(`Interpreter`);
    // No hedging labels, no claims of correctness or of anything being queued.
    expect(hero.textContent).not.toMatch(/experimental|not checked|edition|goes to expert review|\bcorrect\b|deciph/i);
    // Credits: photo author, licence, source, and the reading's maker.
    expect(screen.getByTestId('hero-credit')).toHaveAttribute('href', expect.stringContaining('commons.wikimedia.org'));
    expect(within(hero).getByRole('link', { name: 'CC BY 2.0' })).toHaveAttribute('href', 'https://creativecommons.org/licenses/by/2.0/');
    expect(hero).toHaveTextContent('Richard Mortel');
    expect(hero).toHaveTextContent('Reading by Ezhuthu, built with Strands Agents');
    expect(hero).toHaveTextContent('Meaning by Ezhuthu');
    // The artwork is hidden from assistive tech; the reading is not.
    expect(hero.querySelector('.sh-photo')).toHaveAttribute('aria-hidden', 'true');
    expect(hero.querySelector('.sh-pipe')).toHaveAttribute('aria-hidden', 'true');
    expect(hero.querySelector('.sh-out')?.closest('[aria-hidden="true"]')).toBeNull();
  });

  it('offers one primary call to action, then practice, how it works and scholars sections', () => {
    renderApp(<AppRoutes />, { route: '/' });
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Learn to read old Tamil inscriptions.');
    // A short subline a non-expert understands, then the calls to action.
    expect(screen.getByTestId('hero-head').querySelector('.hh-sub')).toHaveTextContent(/^Practise on real inscriptions/);
    expect(screen.getByTestId('hero-head').textContent).not.toMatch(/abstain|backlog|review queue|experimental|\bcorrect\b|Aivar/i);
    expect(screen.getByTestId('hero-actions').querySelectorAll('.btn-primary')).toHaveLength(1);
    expect(screen.getByTestId('cta-practice')).toHaveAttribute('href', '#try');
    expect(screen.getByTestId('cta-upload')).toHaveAttribute('href', '/restore');
    expect(screen.getByTestId('cta-how')).toHaveAttribute('href', '#how');
    // The headline and calls to action come before the stone in the page (phones show them first).
    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1.compareDocumentPosition(screen.getByTestId('stone-hero')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // Sections in order: hero, practice, how it works, scholars.
    const order = ['stone-hero', 'home-features', 'home-practice', 'home-how', 'scholars'].map((id) => screen.getByTestId(id));
    for (let i = 1; i < order.length; i++) expect(order[i - 1]!.compareDocumentPosition(order[i]!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByTestId('mini-drill')).toBeInTheDocument();
    // The long sample gallery is not on home (user feedback); one link leads to it on Restore.
    expect(screen.queryByTestId('sample-gallery')).toBeNull();
    expect(screen.getByTestId('home-samples-link')).toHaveAttribute('href', '/restore#samples');
    for (const f of ['practice', 'restore', 'read', 'how']) expect(screen.getByTestId(`feature-${f}`)).toBeInTheDocument();
    const scholars = screen.getByTestId('scholars');
    expect(within(scholars).getByRole('link', { name: 'Expert review →' })).toHaveAttribute('href', '/review');
    expect(within(scholars).getByTestId('scholars-benchmark')).toHaveAttribute('href', '/benchmark');
  });

  it('is in Tamil when the app is', () => {
    renderApp(<AppRoutes />, { route: '/', lang: 'ta' });
    const hero = screen.getByTestId('stone-hero');
    expect(hero).toHaveTextContent('வாசிப்பாளர்');
    expect(hero).toHaveTextContent('சோழர் காலத் தமிழ்');
    expect(hero).toHaveTextContent('Strands Agents');
    expect(hero).toHaveTextContent('விளக்குநர்');
    expect(hero).toHaveTextContent('பொருள்: எழுத்து');
    // In Tamil, the Tamil meaning comes first; the words verdict keeps its two numbers apart.
    const meaning = screen.getByTestId('hero-meaning');
    expect(Array.from(meaning.querySelectorAll('[data-anim^="mean-"]:not([data-anim="mean-head"])')).map((e) => e.getAttribute('lang'))).toEqual(['ta', 'en']);
    expect(meaning.querySelector('.sh-mc')).toHaveTextContent('நம்பகம்');
    expect(hero).toHaveTextContent('சொற்களின் நம்பகம் 50% அல்லது அதற்கு மேல்');
  });
});

describe('stone hero accuracy: every number shown comes from the recorded runs', () => {
  it('shows the letter count, mean, cut-off, gap fill, calibrated threshold, open count and word counts from hero-reading.json', () => {
    renderApp(<AppRoutes />, { route: '/' });
    const hero = screen.getByTestId('stone-hero');
    const pct = (c: number) => `${Math.round(c * 100)}%`;
    const g = heroRaw.glyphs;
    const gaps = heroRaw.restore.gaps;
    const cut = pct(g.gap_below);
    expect(hero).toHaveTextContent(`${g.letters} carved letters named in modern Tamil`);
    expect(hero).toHaveTextContent(`the Reader’s mean confidence ${pct(g.mean_confidence)}`);
    expect(hero.querySelector('[data-node="reader"] .sh-node-out')).toHaveTextContent(`${g.letters} letters · ${pct(g.mean_confidence)}`);
    const open = gaps.filter((x) => x.decision === 'abstain').length;
    expect(hero).toHaveTextContent(`${open} left open`);
    expect(hero).toHaveTextContent(`Letters under ${cut} are flagged as uncertain.`);
    const words = heroRaw.interpret.words;
    expect(hero).toHaveTextContent(`${words.length} words, ${words.filter((w) => (w.confidence ?? 0) >= g.gap_below).length} at ${cut} or more`);
    // The gap: the Reader's own confidence, the Restorer's best fill with its calibrated confidence, and the
    // calibrated threshold it was held to (not a hard-coded 50%).
    const gap = gaps[0]!;
    const reader = g.rows[gap.row]!.glyphs[gap.box]!.confidence!;
    expect(gap.strategy).toBe('prerank');
    expect(gap.best.confidence_source).not.toMatch(/decider/);
    expect(hero.querySelector('[data-node="restorer"] .sh-node-out')).toHaveTextContent(`${gap.best.ta} ${pct(gap.best.confidence)}`);
    expect(hero.querySelector('.sh-card[data-gap]')).toHaveTextContent(`Reader ${pct(reader)} < ${cut}`);
    expect(hero.querySelector('.sh-card[data-gap]')).toHaveTextContent(`best fill ${gap.best.ta} ${pct(gap.best.confidence)} < ${pct(gap.abstain_below)} · left open`);
    expect(hero.querySelector('.sh-gapnote')).toHaveTextContent(`(${pct(reader)})`);
    expect(hero.querySelector('.sh-gapnote')).toHaveTextContent(`scored ${pct(gap.best.confidence)}, under the ${pct(gap.abstain_below)} needed`);
    // The view the page ships is the same record.
    expect(HERO.letters).toBe(g.letters);
    expect(HERO.mean).toBe(g.mean_confidence);
    expect(HERO.letterCut).toBe(g.gap_below);
    expect(HERO.gaps[0]!.g.gap).toEqual({ decision: gap.decision, below: gap.abstain_below, best: { ta: gap.best.ta, c: gap.best.confidence } });
    // Restoration is not credited to the Strands Decider (the deployed restorer makes no decider call); the letter
    // % is labelled as the Reader's own; the boxes as hand-marked; nothing says the reading is verified.
    expect(hero.querySelector('.sh-pipe')!.textContent).not.toMatch(/Strands Decider/);
    expect(hero.querySelector('.sh-gapnote')!.textContent).not.toMatch(/Decider/);
    expect(hero).toHaveTextContent('%: the Reader’s own confidence, not a measured accuracy');
    expect(hero).toHaveTextContent('Letter boxes marked by hand; the Reader names each letter.');
    expect(hero.textContent).not.toMatch(/verified|validated|accuracy of \d|match rate/i);
  });
});

describe('stone hero animation: one track per element, and the loop has no seam', () => {
  type Rec = { el: Element; kf: Keyframe[]; opts: KeyframeAnimationOptions; anim: Animation };
  let recs: Rec[] = [];
  const proto = Element.prototype as unknown as { animate?: unknown };
  const original = proto.animate;
  const matchMedia = window.matchMedia;

  beforeEach(() => {
    recs = [];
    proto.animate = function (this: Element, kf: Keyframe[], opts: KeyframeAnimationOptions) {
      const anim = { cancel() {}, pause() {}, play() {}, playState: 'running', onfinish: null, currentTime: 0 } as unknown as Animation;
      recs.push({ el: this, kf, opts, anim });
      return anim;
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

  const timeline = () => buildTimeline(HERO.rows.map((r) => r.glyphs.length), HERO.featured, HERO.gaps.length, 2, HERO.words.length, HERO.phraseTokens.length);
  /** The reading pane and the meaning pane (with what is in it) carry over the seam: the meaning stays on screen and
   * crossfades out as the next cycle's scan begins. */
  const carried = (el: Element) => el.classList.contains('sh-read') || !!el.closest('.sh-mean');

  it('animates every hero element over exactly one cycle, ending where the next cycle begins', async () => {
    const hero = await startCycle();
    const tl = timeline();
    const inHero = recs.filter((r) => hero.contains(r.el) && r.kf.length > 0);
    expect(inHero.length).toBeGreaterThan(150);
    const perEl = new Map<Element, number>();
    for (const r of inHero) {
      expect(r.opts.duration).toBe(tl.cycle);
      expect(r.opts.delay ?? 0).toBe(0);
      expect(r.kf[0]!.offset).toBe(0);
      expect(r.kf[r.kf.length - 1]!.offset).toBe(1);
      perEl.set(r.el, (perEl.get(r.el) ?? 0) + 1);
      if (r.el.classList.contains('sh-kb') || carried(r.el)) continue;
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
    // The finished frame is the stone with the phrase and meaning: the meaning pane is on screen at the end.
    const mean = inHero.find((r) => r.el.classList.contains('sh-mean'))!;
    expect(mean.kf[0]!.opacity).toBe(0);
    expect(mean.kf[mean.kf.length - 1]!.opacity).toBe(1);
    // The beats come in the order the story is told, and the loop is 22 to 26 s with a 3 s hold.
    expect(tl.words.start).toBeGreaterThan(Math.max(...tl.rows.map((r) => r.landed)) - 400);
    expect(tl.phrase.start).toBeGreaterThan(tl.words.end - 1);
    expect(tl.meaning.first).toBeGreaterThan(tl.phrase.end);
    expect(tl.cycle).toBeGreaterThanOrEqual(22_000);
    expect(tl.cycle).toBeLessThanOrEqual(26_000);
  });

  it('crossfades the meaning into the next cycle instead of emptying the reading', async () => {
    const hero = await startCycle();
    const first = recs.filter((r) => hero.contains(r.el) && r.kf.length > 0);
    const clock = recs.find((r) => r.el.classList.contains('sh-stage') && r.kf.length === 0)!;
    recs = [];
    (clock.anim as unknown as { currentTime: number }).currentTime = clock.opts.duration as number;
    (clock.anim.onfinish as unknown as () => void)();
    const second = recs.filter((r) => hero.contains(r.el) && r.kf.length > 0);
    expect(second.length).toBe(first.length);
    const end = new Map(first.map((r) => [r.el, r.kf[r.kf.length - 1]!]));
    for (const r of second) {
      const prev = end.get(r.el)!;
      // Every element starts the next cycle exactly as it ended this one (the photo keeps its place too).
      if ('opacity' in r.kf[0]!) expect(r.kf[0]!.opacity, r.el.className).toBe(prev.opacity);
    }
    // The meaning is on screen when the next cycle starts and gone, with the reading pane back, during the scan.
    const at = (el: Element, t: number) => {
      const kf = second.find((r) => r.el === el)!.kf;
      const off = t / (clock.opts.duration as number);
      return kf.filter((k) => (k.offset as number) <= off).pop()!.opacity;
    };
    const mean = hero.querySelector('.sh-mean')!;
    const read = hero.querySelector('.sh-read')!;
    expect(at(mean, 0)).toBe(1);
    expect(at(mean, 1600)).toBe(0);
    expect(at(read, 0)).toBe(0);
    expect(at(read, 1600)).toBe(1);
  });

  it('reads letters out in order: every letter of row r lands before row r+1 starts landing', async () => {
    const hero = await startCycle();
    const tl = timeline();
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
    // Then the words open up: letters are closed up (shifted left) until the WORDS beat, then sit in their word.
    const words = Array.from(hero.querySelectorAll('.sh-word'));
    for (const w of words) {
      const kf = recs.find((r) => r.el === w)!.kf;
      const opened = kf.find((k) => k.transform === 'none')!.offset as number;
      expect(opened * tl.cycle).toBeCloseTo(tl.words.slid, 0);
    }
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
  it('shows the Interpreter run it was built from: words with their letters, phrase, meaning', () => {
    expect(HERO.words.map((w) => [w.ta, w.c, w.at])).toEqual(interp.response.words.map((w) => [w.tamil, w.confidence, w.letters]));
    expect(HERO.phrase).toEqual({ ta: interp.response.phrase_tamil, iso: interp.response.phrase_iso });
    expect(HERO.meaning).toEqual({ en: interp.response.meaning_en, ta: interp.response.meaning_ta });
    expect(interp.input).toEqual(glyphs.rows.map((r) => r.glyphs.map((g) => (g.confidence !== null && g.confidence >= 0.5 && g.ta ? g.ta : '?'))));
    // Every letter belongs to at most one word, and words keep reading order.
    const seen = HERO.words.flatMap((w) => w.at.map(([r, i]) => readingIndexOf(r, i)));
    expect(seen).toEqual([...seen].sort((a, b) => a - b));
    expect(new Set(seen).size).toBe(seen.length);
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
    expect(heroRaw.interpret.model).toBe(interp.response.model);
    expect(heroRaw.photo.licence).toBe('CC BY 2.0');
    expect(heroRaw.photo.author).toBe('Richard Mortel');
    expect(heroRaw.edition).toBeNull();
    expect(heroRaw.match_rate).toBeNull();
    const calls = heroRaw.live_calls;
    expect(calls.reader + calls.glyphs + calls.restorer + calls.interpreter + calls.photo_search).toBeLessThanOrEqual(60);
  });
});

function readingIndexOf(r: number, i: number): number {
  return HERO.rows.slice(0, r).reduce((n, row) => n + row.glyphs.length, 0) + i;
}

function Where() {
  const loc = useLocation();
  return <p data-testid="where">{loc.pathname + loc.search}</p>;
}

describe('renamed routes keep old links working', () => {
  it('/learn redirects to /practice with its query string (a tutor-lesson link lands on the guided lesson)', async () => {
    renderApp(
      <>
        <AppRoutes />
        <Routes>
          <Route path="*" element={<Where />} />
        </Routes>
      </>,
      { route: '/learn?level=L2' },
    );
    expect(await screen.findByTestId('where')).toHaveTextContent('/practice/guided?level=L2');
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
  const all = [...Object.values(en), ...Object.values(ta), ...Object.values(enHero), ...Object.values(taHero)].join('\n');
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
