import { useCallback, useEffect, useRef, useState, type CSSProperties, type RefObject } from 'react';
import { badgeAnchor, confClass, HERO, heroSrcSet, pctLabel, wordRuns, type Box, type HeroGlyph } from '../hero/heroData';
import {
  BADGE_MS,
  BEATS,
  buildTimeline,
  CARRY_OUT,
  CHIP_MS,
  FADE_MS,
  FLY_MS,
  HIDDEN,
  KB_END,
  kbAt,
  kbTransform,
  MEANING_MS,
  PANE_MS,
  readingIndex,
  SHOWN,
  TOKEN_MS,
  trackKeyframes,
  VERDICT_MS,
  VERDICT_STAGGER,
  WORD_LINE_MS,
  type Props,
  type Stop,
} from '../hero/timeline';
import { useI18n } from '../i18n/I18nProvider';
import { usePrefersReducedMotion } from '../lib/motion';
import '../styles/stone-hero.css';

/**
 * The home hero: a real photograph of a Chola-period inscription (Brihadisvara temple, Thanjavur; Richard Mortel,
 * CC BY 2.0), read letter by letter by Ezhuthu's Reader, with the Restorer and the Strands Decider on the letter it
 * could not name with confidence, and the Interpreter turning the letters into words, a phrase in today's Tamil and
 * its meaning. Every letter, word, percentage and decision shown comes from src/hero/hero-view.json
 * (scripts/hero_read.py + scripts/hero_build.py): nothing is invented for the animation.
 *
 * Storyboard (src/hero/timeline.ts derives every beat from the reading): (a) the stone (fades in on the first cycle
 * only; later cycles keep it and reverse its slow drift, so the loop has no cut) and a raking light; (b) a scan beam
 * lights the carved letters row by row; (c) MATCH: the first letters one at a time in a card (the carved glyph,
 * zoomed -> the modern Tamil letter, a ring filling to the Reader's confidence), speeding up into a cascade of small
 * badges (letter + %) over every box; (d) the letter under the cut-off: the Restorer proposes, the Strands Decider
 * fills or abstains, and its badge turns to "?"; (e) the letters fly from the stone past the pipeline and assemble
 * into the reading, row by row, run together as on the stone; (f) WORDS: they slide apart into the Interpreter's
 * words, each underlined in its confidence tint; (g) PHRASE: the letter rows give way to the words arranged in today's
 * Tamil; (h) MEANING in English, then in Tamil; the verdict; a hold. Then everything but the photo and the meaning
 * fades, and the meaning crossfades into the next cycle's empty reading as its scan begins.
 *
 * Motion is the Web Animations API, one animation per element over the whole cycle (so nothing composites over a
 * stale fill and the loop seam is explicit), on transform and opacity (plus the ring's stroke). Positions are
 * measured once per cycle, before any animation starts. The cycle runs while the hero is on screen, pauses off screen
 * or in a hidden tab, and has Pause and Replay buttons. Under prefers-reduced-motion, or without element.animate, it
 * renders a composed static frame: the photo with every letter marked and badged, two match cards, the reading in
 * words, the phrase and the meaning. The artwork is aria-hidden; the reading is real, selectable text.
 */

const LETTERS = HERO.rows.map((r) => r.glyphs.length);
const TL = buildTimeline(LETTERS, HERO.featured, HERO.gaps.length, 2, HERO.words.length, HERO.phraseTokens.length);
/** Boxes rest at this opacity once their letter has left; the fade-out starts from it. */
const BOX_REST = 0.55;
/** The photo's rendered width: the stone column at >= 980 px (~63% of the stage, capped by the page), else the
 * stage width. Checked against the laid-out width in e2e/stone-hero.spec.ts. */
const PHOTO_SIZES = '(min-width: 1180px) 660px, (min-width: 980px) calc(64vw - 72px), calc(100vw - 40px)';
const EASE = 'cubic-bezier(.2,0,0,1)';

type Phase = 'idle' | 'running' | 'paused';

function canAnimate(): boolean {
  return typeof Element !== 'undefined' && typeof Element.prototype.animate === 'function';
}

const pct = (v: number, of: number) => `${((v / of) * 100).toFixed(3)}%`;
const fill = (s: string, vars: Record<string, string | number>) => s.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ''));

/** Reading-order list of letters with their row, index and box. */
const FLAT = HERO.rows.flatMap((row, r) => row.glyphs.map((g, i) => ({ r, i, g, box: HERO.boxes[r]![i]! as Box, idx: readingIndex(LETTERS, r, i) })));
const GAP0 = HERO.gaps[0];
/** Static frame: the first featured card, and the card of the first gap (or the second featured letter). */
const STATIC_CARDS = new Set([0, GAP0 ? readingIndex(LETTERS, GAP0.r, GAP0.i) : 1]);
/** Words the Interpreter is at least as sure of as the letter cut-off. */
const WORDS_SURE = HERO.words.filter((w) => (w.c ?? 0) >= HERO.abstainBelow).length;

function Photo({ cls }: { cls?: string }) {
  return (
    <picture>
      <source type="image/avif" srcSet={heroSrcSet('avif')} sizes={PHOTO_SIZES} />
      <source type="image/webp" srcSet={heroSrcSet('webp')} sizes={PHOTO_SIZES} />
      <img
        className={cls}
        src="/hero/thanjavur-800.jpg"
        srcSet={heroSrcSet('jpg')}
        sizes={PHOTO_SIZES}
        width={HERO.photo.width}
        height={HERO.photo.height}
        alt=""
        decoding="async"
        fetchPriority={cls ? 'low' : 'high'}
      />
    </picture>
  );
}

/** The carved glyph, zoomed: the photo inside a square window centred on the box. Same srcset and sizes as the main
 * photo, so the browser reuses the file it already picked. */
function Crop({ box }: { box: Box }) {
  const { width: W, height: H } = HERO.photo;
  const [x0, y0, x1, y1] = box;
  const side = Math.max(x1 - x0, y1 - y0) * 1.12;
  const cx = (x0 + x1) / 2;
  const cy = (y0 + y1) / 2;
  const style: CSSProperties = {
    width: `${(W / side) * 100}%`,
    left: `${(-(cx - side / 2) / side) * 100}%`,
    top: `${(-(cy - side / 2) / side) * 100}%`,
    height: 'auto',
    aspectRatio: `${W} / ${H}`,
  };
  return (
    <span className="sh-crop">
      <span className="sh-crop-in" style={style}>
        <Photo cls="sh-crop-img" />
      </span>
    </span>
  );
}

function Ring({ c }: { c: number | null }) {
  const off = 100 * (1 - (c ?? 0));
  return (
    <span className={`sh-ring ${confClass(c)}`}>
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle className="sh-ring-bg" cx="18" cy="18" r="15.915" />
        <circle className="sh-ring-fg" cx="18" cy="18" r="15.915" pathLength={100} strokeDasharray="100" style={{ strokeDashoffset: off }} />
      </svg>
      <b>{pctLabel(c)}</b>
    </span>
  );
}

/** A match card beside its box: carved glyph -> modern Tamil letter, the confidence ring, the era. */
function MatchCard({ idx, g, box, place, foot, era, gap }: { idx: number; g: HeroGlyph; box: Box; place: 'below' | 'right'; foot: string; era: string; gap?: boolean }) {
  const { width: W, height: H } = HERO.photo;
  const [x0, y0, x1, y1] = box;
  const style: CSSProperties =
    place === 'below'
      ? { left: pct(Math.max(6, x0 - 10), W), top: pct(y1 + 8, H) }
      : { left: pct(x1 + 10, W), top: pct(Math.max(6, y0 - 10), H) };
  return (
    <span className="sh-card" data-card={idx} data-place={place} data-gap={gap ? '' : undefined} data-static={STATIC_CARDS.has(idx) ? '' : undefined} style={style}>
      <span className="sh-card-row">
        <Crop box={box} />
        <span className="sh-arrow" aria-hidden="true">
          →
        </span>
        <span className={`sh-card-ta ${confClass(g.c)}`} lang="ta">
          {g.ta || '?'}
        </span>
        <Ring c={g.c} />
      </span>
      <span className="sh-card-foot">
        <span>{era}</span>
        <span>{foot}</span>
      </span>
    </span>
  );
}

function Badge({ idx, g, box }: { idx: number; g: HeroGlyph; box: Box }) {
  const { width: W, height: H } = HERO.photo;
  const { x, y } = badgeAnchor(box);
  const open = g.gap && g.gap.decision === 'abstain';
  return (
    <span className={`sh-badge ${confClass(g.c)}${g.gap ? ' sh-badge-gap' : ''}`} data-idx={idx} style={{ left: pct(x, W), top: pct(y, H) }}>
      <span className="sh-badge-a">
        <b lang="ta">{g.ta || '?'}</b>
        <small>{Math.round((g.c ?? 0) * 100)}</small>
      </span>
      {g.gap && (
        <span className="sh-badge-b">
          <b lang="ta">{open ? '?' : g.gap.best?.ta}</b>
        </span>
      )}
    </span>
  );
}

/** One row of the reading: letters grouped into the Interpreter's words. Before the WORDS beat the words are closed
 * up (each letter slot is shifted left by the word gaps before it), so the row reads run-on, as carved. */
function ReadingRow({ r, gapLabel }: { r: number; gapLabel: string }) {
  const row = HERO.rows[r]!;
  return (
    <p className="sh-ta" lang="ta">
      {wordRuns(r).map(([w, a, b]) => {
        const word = w >= 0 ? HERO.words[w] : undefined;
        return (
          <span key={a} className="sh-word" data-w={w} data-row={r}>
            {row.glyphs.slice(a, b + 1).map((g, k) => {
              const i = a + k;
              const openGap = g.gap && g.gap.decision === 'abstain';
              const text = g.gap ? (openGap ? null : g.gap.best?.ta) : g.ta;
              return (
                <span key={i} className="sh-slot">
                  <span className={`sh-dot ${confClass(g.c)}`} data-idx={readingIndex(LETTERS, r, i)} aria-hidden="true" />
                  <span className={`sh-l ${openGap ? 'sh-gap' : confClass(g.gap ? g.gap.best?.c : g.c)}`} data-anim="land" data-k={i}>
                    {openGap ? (
                      <>
                        <span aria-hidden="true">?</span>
                        <span className="visually-hidden">{gapLabel}</span>
                      </>
                    ) : (
                      text
                    )}
                  </span>
                </span>
              );
            })}
            {word && <span className={`sh-wline ${confClass(word.c)}`} data-w={w} aria-hidden="true" />}
          </span>
        );
      })}
    </p>
  );
}

export function StoneHero({ ctaRef }: { ctaRef?: RefObject<HTMLElement | null> }) {
  const { lang, t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const animated = !reduced && canAnimate();
  const rootRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const anims = useRef<Animation[]>([]);
  const clockRef = useRef<Animation | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [userPaused, setUserPaused] = useState(false);
  const visible = useRef(false);
  const tabVisible = useRef(true);
  const userPausedRef = useRef(false);
  /** The photo has decoded (the first frame of the cycle has pixels to show). */
  const ready = useRef(false);
  const cycleN = useRef(0);
  const photoShown = useRef(false);
  const startRef = useRef<(next?: boolean) => void>(() => {});

  const clear = useCallback(() => {
    for (const a of anims.current) a.cancel();
    anims.current = [];
    clockRef.current = null;
  }, []);

  /** Build and start one full cycle. All measuring happens here, before the first animation is created. */
  const start = useCallback(
    (next = false) => {
      const root = rootRef.current;
      const stage = stageRef.current;
      if (!root || !stage) return;
      // The meaning is on screen if the last cycle got as far as the phrase: then this cycle crossfades it out.
      const prevT = Number(clockRef.current?.currentTime ?? 0);
      const carry = next || prevT >= TL.phrase.paneIn;
      clear();
      cycleN.current = next ? cycleN.current + 1 : 0;
      const zoomOut = cycleN.current % 2 === 0;
      const fadeIn = !photoShown.current;
      photoShown.current = true;
      const C = TL.cycle;
      const list: Animation[] = [];
      /** One animation per element over the whole cycle. `reset`: an element inside a card or badge returns to its
       * first state once everything is hidden, so the next cycle starts from the same frame. */
      const track = (el: Element | null | undefined, stops: Stop[], reset = false) => {
        if (!el) return;
        const all: Stop[] = reset && stops.length ? [...stops, [TL.fadeOut + FADE_MS, stops[0]![1]]] : stops;
        list.push(el.animate(trackKeyframes(all, C), { duration: C, fill: 'both', easing: 'linear' }));
      };
      const q = <E extends Element>(sel: string) => Array.from(root.querySelectorAll<E>(sel));
      const one = <E extends Element>(sel: string) => root.querySelector<E>(sel);
      const fadeStops = (from = 1): Stop[] => [
        [TL.fadeOut, { opacity: from, transform: 'none' }, 'ease-in'],
        [TL.fadeOut + FADE_MS, HIDDEN],
      ];
      const rise = (at: number, ms: number, dy = 6): Stop[] => [
        [at, { opacity: 0, transform: `translateY(${dy}px)` }, EASE],
        [at + ms, SHOWN],
        ...fadeStops(),
      ];
      /** Inside the meaning pane, which is carried into the next cycle: shown from `at` to the end of the cycle; in a
       * carried cycle also shown at the start, until the pane has faded out. */
      const kept = (at: number, ms: number, dy = 6): Stop[] => {
        const off: Props = { opacity: 0, transform: `translateY(${dy}px)` };
        return [
          // Carried: on screen at the start; dropped the moment the pane has faded out, so it can rise again.
          ...(carry ? ([[0, SHOWN], [CARRY_OUT[1], SHOWN], [CARRY_OUT[1] + 1, off]] as Stop[]) : []),
          [at, off, EASE],
          [at + ms, SHOWN],
        ];
      };

      // ---- measure (one batch of reads) ----
      const sr = stage.getBoundingClientRect();
      const rel = (r: DOMRect) => ({ x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height });
      const kb = one<HTMLElement>('.sh-kb');
      const kbRect = kb ? rel(kb.getBoundingClientRect()) : null;
      const badges = q<HTMLElement>('.sh-badge');
      const badgeRects = badges.map((b) => rel(b.getBoundingClientRect()));
      const nodeRects = q<HTMLElement>('.sh-node-dot').map((n) => rel(n.getBoundingClientRect()));
      const capEl = one<HTMLElement>('.sh-place');
      const capRect = capEl ? rel(capEl.getBoundingClientRect()) : null;
      const lands = q<HTMLElement>('[data-anim="land"]');
      const landRects = lands.map((n) => rel(n.getBoundingClientRect()));
      // The gap before each word of a row: letters are drawn closed up by the sum of the gaps before their word.
      const shiftOf = new Map<Element, number>();
      q<HTMLElement>('.sh-ta').forEach((rowEl) => {
        let acc = 0;
        Array.from(rowEl.querySelectorAll<HTMLElement>('.sh-word')).forEach((w, k) => {
          if (k > 0) acc += parseFloat(getComputedStyle(w).marginLeft) || 0;
          shiftOf.set(w, acc);
        });
      });

      // ---- (a) the stone: drift, raking light ----
      if (kb) {
        const from = kbTransform(kbAt(0, C, zoomOut));
        const to = kbTransform(kbAt(C, C, zoomOut));
        track(kb, [
          [0, { opacity: fadeIn ? 0 : 1, transform: from }],
          [BEATS.photoIn, { opacity: 1, transform: kbTransform(kbAt(BEATS.photoIn, C, zoomOut)) }],
          [C * KB_END, { opacity: 1, transform: to }],
        ]);
      }
      track(one('.sh-rake'), [
        [BEATS.rake, { opacity: 0, transform: 'translateX(-60%)' }, 'cubic-bezier(.65,0,.35,1)'],
        [BEATS.rake + 600, { opacity: 1, transform: 'translateX(-30%)' }],
        [BEATS.rake + 1700, { opacity: 1, transform: 'translateX(30%)' }],
        [BEATS.rake + 2400, { opacity: 0, transform: 'translateX(60%)' }],
      ]);
      track(one('.sh-beam'), [
        [BEATS.beam, { opacity: 0, transform: 'translateY(-56%)' }],
        [BEATS.beam + 220, { opacity: 1, transform: 'translateY(-45%)' }],
        [BEATS.beam + BEATS.beamMs - 260, { opacity: 1, transform: 'translateY(45%)' }],
        [BEATS.beam + BEATS.beamMs, { opacity: 0, transform: 'translateY(56%)' }],
      ]);

      // ---- (b) boxes light up; they dim to rest once their letter flies off ----
      q<HTMLElement>('.sh-box').forEach((b) => {
        const r = Number(b.dataset.row);
        const i = Number(b.dataset.i);
        const on = TL.boxOn(r, i);
        const fly = TL.flyAt(r, i);
        track(b, [
          [on, { opacity: 0, transform: 'scale(1.18)' }, EASE],
          [on + 380, { opacity: 1, transform: 'none' }],
          [fly, { opacity: 1, transform: 'none' }],
          [fly + 300, { opacity: BOX_REST, transform: 'none' }],
          ...fadeStops(BOX_REST),
        ]);
      });

      // ---- (c) MATCH: featured cards one at a time, then the cascade of badges ----
      const cardStops = (inAt: number, outAt: number, endAt: number): Stop[] => [
        [inAt, { opacity: 0, transform: 'translateY(6px) scale(.86)' }, 'cubic-bezier(.2,.9,.3,1.2)'],
        [inAt + 240, { opacity: 1, transform: 'none' }],
        [outAt, { opacity: 1, transform: 'none' }, 'cubic-bezier(.5,0,.75,0)'],
        [endAt, { opacity: 0, transform: 'translateY(-4px) scale(.55)' }],
      ];
      const ringStops = (c: number | null, from: number, to: number): Stop[] => [
        [from, { strokeDashoffset: 100 }, 'cubic-bezier(.3,0,.2,1)'],
        [to, { strokeDashoffset: 100 * (1 - (c ?? 0)) }],
      ];
      TL.cards.forEach((cd) => {
        const el = one(`.sh-card[data-card="${cd.idx}"]`);
        track(el, cardStops(cd.in, cd.out, cd.end));
        track(el?.querySelector('.sh-ring-fg'), ringStops(FLAT[cd.idx]!.g.c, cd.ringFrom, cd.ringTo), true);
        track(el?.querySelector('.sh-ring b'), [
          [cd.ringFrom, HIDDEN],
          [cd.ringFrom + 200, SHOWN],
        ], true);
      });
      // The gap's card: the Reader's letter under the cut-off -> the Restorer's best fill -> the Decider's call.
      if (GAP0) {
        const gi = readingIndex(LETTERS, GAP0.r, GAP0.i);
        const el = one(`.sh-card[data-card="${gi}"]`);
        const g = TL.gap;
        track(el, cardStops(g.start, g.resolve + 250, g.end - 80));
        track(el?.querySelector('.sh-ring-fg'), ringStops(GAP0.g.c, g.start + 150, g.start + 550), true);
        track(el?.querySelector('.sh-ring b'), [
          [g.start + 150, HIDDEN],
          [g.start + 350, SHOWN],
        ], true);
        el?.querySelectorAll('.sh-card-foot > span').forEach((s, k) =>
          track(s, k === 0 ? [[g.restorerOut, SHOWN], [g.restorerOut + 200, HIDDEN]] : [[g.restorerOut, HIDDEN], [g.restorerOut + 250, SHOWN]], true),
        );
      }
      badges.forEach((b) => {
        const idx = Number(b.dataset.idx);
        const { r, i, g } = FLAT[idx]!;
        const at = TL.badgeAt(idx);
        const fly = TL.flyAt(r, i);
        track(b, [
          [at, { opacity: 0, transform: 'translate(-50%, -30%) scale(.4)' }, 'cubic-bezier(.2,.9,.3,1.3)'],
          [at + BADGE_MS, { opacity: 1, transform: 'translate(-50%, -50%)' }],
          [fly, { opacity: 1, transform: 'translate(-50%, -50%)' }, 'ease-in'],
          [fly + 180, { opacity: 0, transform: 'translate(-50%, -50%) scale(.7)' }],
        ]);
        if (g.gap) {
          const res = TL.gap.resolve;
          track(b.querySelector('.sh-badge-a'), [
            [res, SHOWN],
            [res + 220, { opacity: 0, transform: 'scale(.6)' }],
          ], true);
          track(b.querySelector('.sh-badge-b'), [
            [res + 120, { opacity: 0, transform: 'scale(1.6)' }, 'cubic-bezier(.2,.9,.3,1.2)'],
            [res + 380, SHOWN],
          ], true);
        }
      });

      // ---- (d) the pipeline: Reader through the match; Restorer and Decider on the gap; Interpreter on the words ----
      const glow = (key: string, from: number, to: number) =>
        track(one(`[data-node="${key}"] .sh-node-glow`), [
          [from, { opacity: 0, transform: 'scale(.8)' }, 'ease-out'],
          [from + 250, { opacity: 1, transform: 'none' }],
          [Math.max(from + 260, to - 300), { opacity: 1, transform: 'scale(1.05)' }, 'ease-in'],
          [Math.max(from + 300, to), { opacity: 0, transform: 'scale(1.25)' }],
        ]);
      glow('reader', TL.match - 200, TL.cascadeEnd + 200);
      glow('restorer', TL.gap.restorer, TL.gap.decider + 100);
      glow('decider', TL.gap.decider, TL.rows[TL.rows.length - 1]!.landed - FLY_MS / 2);
      glow('interpreter', TL.words.start - 250, TL.meaning.end);
      track(one('[data-node="reader"] .sh-node-out'), rise(TL.cascadeEnd - 150, 380, 4));
      track(one('[data-node="restorer"] .sh-node-out'), rise(TL.gap.restorerOut, 380, 4));
      track(one('[data-node="decider"] .sh-node-out'), rise(TL.gap.deciderOut, 380, 4));
      track(one('[data-node="interpreter"] .sh-node-out'), rise(TL.phrase.start, 380, 4));
      q<HTMLElement>('.sh-spark').forEach((el) => {
        const seg = Number(el.dataset.seg);
        const a = nodeRects[seg];
        const z = nodeRects[seg + 1];
        if (!a || !z) return;
        const k = Number(el.dataset.k);
        const at = (seg === 0 ? TL.gap.restorer - 350 : seg === 1 ? TL.gap.decider - 330 : TL.words.start - 520) + k * 110;
        track(el, [
          [at, { opacity: 0, transform: 'translate(0px, 0px) scale(.6)' }, 'cubic-bezier(.45,0,.25,1)'],
          [at + 130, { opacity: 1, transform: `translate(${(z.x - a.x) * 0.2}px, ${(z.y - a.y) * 0.2}px) scale(.8)` }],
          [at + 520, { opacity: 1, transform: `translate(${(z.x - a.x) * 0.8}px, ${(z.y - a.y) * 0.8}px) scale(1)` }],
          [at + 650, { opacity: 0, transform: `translate(${z.x - a.x}px, ${z.y - a.y}px) scale(1)` }],
        ]);
      });

      // ---- (e) the letters fly from the stone, past the Decider, into the reading (closed up, as carved) ----
      const dec = nodeRects[2];
      lands.forEach((el, n) => {
        const lr = landRects[n]!;
        const r = Number(el.closest<HTMLElement>('[data-line]')?.dataset.line ?? 0);
        const i = Number(el.dataset.k ?? 0);
        const at = TL.flyAt(r, i);
        const idx = readingIndex(LETTERS, r, i);
        const b0 = badgeRects[idx];
        // Its slot is drawn closed up by `shift` px while the letter flies: aim for the closed-up place.
        const shift = shiftOf.get(el.closest('.sh-word')!) ?? 0;
        const stops: Stop[] = [];
        if (b0 && kbRect && dec) {
          // Where the badge is at take-off: the photo is still drifting (scale about its centre, then translate).
          const { s, tx, ty } = kbAt(at, C, zoomOut);
          const cx = kbRect.x + kbRect.w / 2;
          const cy = kbRect.y + kbRect.h / 2;
          const bx = cx + s * (b0.x + b0.w / 2 - cx + tx * kbRect.w);
          const by = cy + s * (b0.y + b0.h / 2 - cy + ty * kbRect.h);
          const ex = lr.x + lr.w / 2 - shift;
          const ey = lr.y + lr.h / 2;
          // Quadratic Bezier start -> end with its control point at the Decider, so every letter swings past it. When
          // both ends are above the photo caption (wide screens), the control point is lowered no further than keeps
          // the lowest point of the curve above the caption, so no letter crosses it: for a curve from y0 to y2 with
          // control y1 below both, the lowest point is m when y1 = m + sqrt((m - y0)(m - y2)).
          const kx = dec.x + dec.w / 2 + (i % 3 - 1) * 10;
          let ky = dec.y + dec.h / 2 + (r - 1.5) * 8;
          const m = capRect ? capRect.y - lr.h * 0.8 : Infinity;
          if (m > by && m > ey) ky = Math.min(ky, m + Math.sqrt((m - by) * (m - ey)));
          const N = 10;
          for (let k = 0; k <= N; k++) {
            const u = k / N;
            const x = (1 - u) * (1 - u) * bx + 2 * (1 - u) * u * kx + u * u * ex - ex;
            const y = (1 - u) * (1 - u) * by + 2 * (1 - u) * u * ky + u * u * ey - ey;
            const sc = k === N ? 1 : 0.8 + 0.5 * Math.sin(Math.PI * u) * (1 - u) + 0.2 * u;
            stops.push([at + u * FLY_MS, { opacity: k === 0 ? 0 : 1, transform: k === N ? 'none' : `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${sc.toFixed(3)})` }, k === 0 ? 'ease-out' : k === N - 1 ? 'cubic-bezier(.3,0,.2,1.4)' : undefined]);
          }
        } else {
          stops.push([at, { opacity: 0, transform: 'translateY(10px)' }, EASE], [at + FLY_MS, SHOWN]);
        }
        track(el, [...stops, ...fadeStops()]);
      });
      // Each letter's slot in the reading appears as a faint dot as the scan beam finds its box, then lights in its
      // confidence tint when the Reader matches it.
      q<HTMLElement>('.sh-dot').forEach((el) => {
        const idx = Number(el.dataset.idx);
        const { r, i } = FLAT[idx]!;
        const on = TL.boxOn(r, i);
        const at = TL.badgeAt(idx);
        const land = TL.flyAt(r, i) + FLY_MS;
        const faint: Props = { opacity: 0.3, transform: 'scale(.55)' };
        track(el, [
          [on, { opacity: 0, transform: 'scale(.2)' }, EASE],
          [on + 300, faint],
          [at, faint, 'cubic-bezier(.2,.9,.3,1.4)'],
          [at + 260, SHOWN],
          [land - 220, SHOWN],
          [land - 40, { opacity: 0, transform: 'scale(.4)' }],
        ]);
      });
      q<HTMLElement>('[data-anim="chip"]').forEach((el) => {
        const r = Number(el.closest<HTMLElement>('[data-line]')?.dataset.line ?? 0);
        const at = TL.rows[r]!.landed;
        track(el, [[at, { opacity: 0, transform: 'scale(.7)' }, 'cubic-bezier(.2,.9,.3,1.3)'], [at + CHIP_MS, SHOWN], ...fadeStops()]);
      });
      q<HTMLElement>('[data-anim="gapnote"]').forEach((el) => track(el, rise(GAP0 ? TL.rows[GAP0.r]!.landed + 200 : TL.words.start, 480)));

      // ---- (f) WORDS: the closed-up letters slide apart into words; each word is underlined in its tint ----
      q<HTMLElement>('.sh-word').forEach((w) => {
        const shift = shiftOf.get(w) ?? 0;
        const closed = { transform: `translateX(${(-shift).toFixed(1)}px)` };
        track(w, [
          [TL.words.start, closed, 'cubic-bezier(.5,0,.2,1)'],
          [TL.words.slid, { transform: 'none' }],
        ], true);
      });
      q<HTMLElement>('.sh-wline').forEach((el) => {
        const at = TL.wordAt(Number(el.dataset.w));
        track(el, [
          [at, { opacity: 0, transform: 'scaleX(0)' }, EASE],
          [at + WORD_LINE_MS, { opacity: 1, transform: 'none' }],
          ...fadeStops(),
        ]);
      });

      // ---- (g) PHRASE: the letter rows give way to the words arranged in today's Tamil ----
      const read = one('.sh-read');
      track(read, [
        ...(carry ? ([[CARRY_OUT[0], { opacity: 0, transform: 'none' }, 'ease-out'], [CARRY_OUT[1], SHOWN]] as Stop[]) : [[0, SHOWN]] as Stop[]),
        [TL.phrase.start, SHOWN, 'cubic-bezier(.4,0,1,1)'],
        [TL.phrase.paneIn, { opacity: 0, transform: 'translateY(-10px)' }],
      ]);
      const mean = one('.sh-mean');
      track(mean, [
        ...(carry ? ([[0, SHOWN], [CARRY_OUT[0], SHOWN, 'ease-in'], [CARRY_OUT[1], { opacity: 0, transform: 'translateY(-6px)' }]] as Stop[]) : []),
        [TL.phrase.start + PANE_MS * 0.4, { opacity: 0, transform: 'translateY(10px)' }, EASE],
        [TL.phrase.start + PANE_MS * 0.4 + PANE_MS, SHOWN],
      ]);
      q<HTMLElement>('.sh-tok').forEach((el, k) => track(el, kept(TL.tokenAt(k), TOKEN_MS, 10)));
      track(one('.sh-phrase-iso'), kept(TL.phrase.end - 200, 420, 4));
      track(one('.sh-mean-k'), kept(TL.phrase.start + PANE_MS * 0.4, 400, 4));
      // ---- (h) MEANING: in the UI language first, then the other ----
      track(one('[data-anim="mean-1"]'), kept(TL.meaning.first, MEANING_MS, 8));
      track(one('[data-anim="mean-2"]'), kept(TL.meaning.second, MEANING_MS, 8));
      track(one('[data-anim="mean-head"]'), kept(TL.meaning.first - 150, 400, 4));
      // ---- verdict, call to action ----
      q<HTMLElement>('[data-anim="verdict"]').forEach((el, k) => track(el, rise(TL.verdict + k * VERDICT_STAGGER, VERDICT_MS, 8)));
      track(one('[data-anim="verdict-words"]'), rise(TL.words.end, 420, 4));
      const cta = ctaRef?.current;
      if (cta) {
        cta.querySelectorAll('.btn').forEach((b, k) =>
          list.push(b.animate([{ transform: 'none' }, { transform: 'translateY(-3px) scale(1.04)', offset: 0.35 }, { transform: 'none' }], { duration: 800, delay: TL.cta + k * 140, easing: 'ease-in-out' })),
        );
      }

      // The clock: when it finishes, the next cycle starts (if still on screen and not paused).
      const clock = stage.animate([], { duration: C });
      clock.onfinish = () => {
        if (visible.current && tabVisible.current && !userPausedRef.current) startRef.current(true);
      };
      list.push(clock);
      anims.current = list;
      clockRef.current = clock;
      setPhase('running');
    },
    [clear, ctaRef],
  );
  startRef.current = start;

  const pause = useCallback(() => {
    for (const a of anims.current) if (a.playState === 'running') a.pause();
    setPhase((p) => (p === 'running' ? 'paused' : p));
  }, []);
  const resume = useCallback(() => {
    if (!ready.current) return;
    if (!anims.current.length) return start();
    for (const a of anims.current) if (a.playState === 'paused') a.play();
    setPhase('running');
  }, [start]);

  // Start when on screen; pause when off screen or when the tab is hidden.
  useEffect(() => {
    const root = rootRef.current;
    if (!animated || !root) return;
    const sync = () => {
      const go = ready.current && visible.current && tabVisible.current && !userPausedRef.current;
      if (go) resume();
      else pause();
    };
    // Wait until the photo has decoded, so the first frame of the cycle has pixels to show.
    let cancelled = false;
    const img = root.querySelector<HTMLImageElement>('.sh-kb > picture img');
    const loaded = !img
      ? Promise.resolve()
      : img.complete && img.naturalWidth > 0
        ? Promise.resolve()
        : new Promise<void>((res) => {
            img.addEventListener('load', () => res(), { once: true });
            img.addEventListener('error', () => res(), { once: true });
          });
    loaded
      .then(() => img?.decode?.())
      .catch(() => undefined)
      .then(() => {
        if (cancelled) return;
        ready.current = true;
        sync();
      });
    let io: IntersectionObserver | null = null;
    if (typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver(
        ([e]) => {
          visible.current = !!e?.isIntersecting;
          sync();
        },
        { threshold: 0.2 },
      );
      io.observe(root);
    } else {
      visible.current = true;
      sync();
    }
    const onVis = () => {
      tabVisible.current = document.visibilityState !== 'hidden';
      sync();
    };
    document.addEventListener('visibilitychange', onVis);
    return () => {
      cancelled = true;
      io?.disconnect();
      document.removeEventListener('visibilitychange', onVis);
      clear();
    };
  }, [animated, pause, resume, clear]);

  // A language switch or a resize changes where letters sit: rebuild the cycle from the start.
  useEffect(() => {
    if (!animated || !anims.current.length) return;
    if (!userPausedRef.current && visible.current) start();
    else clear();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang]);
  useEffect(() => {
    if (!animated) return;
    let w = window.innerWidth;
    let timer = 0;
    const onResize = () => {
      if (Math.abs(window.innerWidth - w) < 40) return;
      w = window.innerWidth;
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        if (!anims.current.length) return;
        if (!userPausedRef.current && visible.current) start();
        else clear();
      }, 250);
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.removeEventListener('resize', onResize);
      window.clearTimeout(timer);
    };
  }, [animated, start, clear]);

  const togglePause = () => {
    const next = !userPaused;
    userPausedRef.current = next;
    setUserPaused(next);
    if (next) pause();
    else resume();
  };
  const replay = () => {
    userPausedRef.current = false;
    setUserPaused(false);
    if (ready.current) start();
  };

  const { photo, boxes, rows } = HERO;
  const vars = { '--sh-aspect': `${photo.width} / ${photo.height}` } as CSSProperties;
  const era = lang === 'ta' ? HERO.script.label_ta : HERO.script.label_en;
  const cut = pctLabel(HERO.abstainBelow);
  const best0 = GAP0?.g.gap?.best;
  const gapFoot = GAP0
    ? `${t('stoneHero.restorer')}: ${best0?.ta ?? '–'} ${pctLabel(best0?.c)} · ${GAP0.g.gap!.decision === 'abstain' ? t('stoneHero.abstain') : t('stoneHero.decider')}`
    : '';
  const open = HERO.gaps.length - HERO.fills;

  return (
    <section
      ref={rootRef}
      className="stone-hero"
      data-testid="stone-hero"
      data-motion={animated ? 'animated' : 'static'}
      data-phase={animated ? phase : undefined}
      aria-label={t('stoneHero.label')}
      style={vars}
    >
      <div className="sh-stage" ref={stageRef}>
        <figure className="sh-photo" aria-hidden="true">
          <div className="sh-frame">
            <div className="sh-kb">
              <Photo />
              {boxes.map((row, r) =>
                row.map(([x0, y0, x1, y1], i) => (
                  <span
                    key={`${r}-${i}`}
                    className="sh-box"
                    data-row={r}
                    data-i={i}
                    style={{ left: pct(x0, photo.width), top: pct(y0, photo.height), width: pct(x1 - x0, photo.width), height: pct(y1 - y0, photo.height) }}
                  />
                )),
              )}
              {FLAT.map(({ idx, g, box }) => (
                <Badge key={idx} idx={idx} g={g} box={box} />
              ))}
              {FLAT.slice(0, HERO.featured).map(({ idx, g, box }) => (
                <MatchCard key={idx} idx={idx} g={g} box={box} place="below" era={era} foot={`→ ${t('stoneHero.toModern')}`} />
              ))}
              {GAP0 && readingIndex(LETTERS, GAP0.r, GAP0.i) >= HERO.featured && (
                <MatchCard
                  gap
                  idx={readingIndex(LETTERS, GAP0.r, GAP0.i)}
                  g={GAP0.g}
                  box={HERO.boxes[GAP0.r]![GAP0.i]!}
                  place="right"
                  era={`${t('stoneHero.match')} ${pctLabel(GAP0.g.c)} < ${cut}`}
                  foot={gapFoot}
                />
              )}
            </div>
            <span className="sh-rake" />
            <span className="sh-beam" />
          </div>
          <figcaption className="sh-place">{t('stoneHero.place')}</figcaption>
        </figure>

        <ol className="sh-pipe" aria-hidden="true">
          {(
            [
              ['reader', 'stoneHero.reader', 'stoneHero.readerSub', `${HERO.letters} ${t('stoneHero.letters')} · ${pctLabel(HERO.mean)}`],
              ['restorer', 'stoneHero.restorer', 'stoneHero.restorerSub', best0 ? `${best0.ta} ${pctLabel(best0.c)}` : `0 ${t('stoneHero.gaps')}`],
              ['decider', 'stoneHero.decider', 'stoneHero.deciderSub', open ? `? · ${t('stoneHero.abstain')}` : `${HERO.fills} ✓`],
              ['interpreter', 'stoneHero.interpreter', 'stoneHero.interpreterSub', `${HERO.words.length} ${t('stoneHero.words')}`],
            ] as const
          ).map(([key, label, sub, out], i, all) => (
            <li key={key} className="sh-node" data-node={key}>
              <span className="sh-node-dot">
                <span className="sh-node-glow" />
                <span className="sh-node-n">{i + 1}</span>
              </span>
              <span className="sh-node-text">
                <b>{t(label)}</b>
                <small>{t(sub)}</small>
                <span className="sh-node-out" lang={key === 'restorer' ? 'ta' : undefined}>
                  {out}
                </span>
              </span>
              {i < all.length - 1 && (
                <span className="sh-wire">
                  {[0, 1, 2].map((s) => (
                    <span key={s} className="sh-spark" data-seg={i} data-k={s} />
                  ))}
                </span>
              )}
            </li>
          ))}
        </ol>

        <div className="sh-out">
          <p className="sh-out-head">
            <span>{t('stoneHero.output')}</span>
            <span className="sh-legend" aria-label={t('stoneHero.legend')}>
              <i className="sh-c-high">≥ 70%</i>
              <i className="sh-c-mid">50–69%</i>
              <i className="sh-c-low">&lt; 50%</i>
            </span>
          </p>
          <div className="sh-panes">
            <div className="sh-read">
              <div className="sh-lines">
                {rows.map((row, r) => (
                  <div key={r} className="sh-line" data-line={r}>
                    <ReadingRow r={r} gapLabel={t('stoneHero.gap')} />
                    <span className={`sh-lc ${confClass(row.c)}`} data-anim="chip" title={t('stoneHero.rowConfidence')}>
                      {pctLabel(row.c)}
                    </span>
                  </div>
                ))}
              </div>
              {HERO.gaps.map(({ r, g }, k) => (
                <p key={k} className="sh-gapnote" data-anim="gapnote">
                  <span className="sh-gap-mark" aria-hidden="true">
                    ?
                  </span>
                  <span>
                    {fill(t(g.gap!.decision === 'abstain' ? 'stoneHero.gapOpen' : 'stoneHero.gapFilled'), {
                      r: r + 1,
                      ta: g.ta,
                      c: pctLabel(g.c),
                      cut,
                      fill: g.gap!.best?.ta ?? '–',
                      fc: pctLabel(g.gap!.best?.c),
                    })}
                  </span>
                </p>
              ))}
            </div>
            <div className="sh-mean" data-testid="hero-meaning">
              <p className="sh-k sh-mean-k">{t('stoneHero.phrase')}</p>
              <p className="sh-phrase" lang="ta">
                {HERO.phraseTokens.map((tok, k) => (
                  <span key={k}>
                    {k > 0 && ' '}
                    <span className="sh-tok">{tok}</span>
                  </span>
                ))}
              </p>
              <p className="sh-phrase-iso" lang="ta-Latn">
                {HERO.phrase.iso}
              </p>
              <p className="sh-k sh-mean-head" data-anim="mean-head">
                <span>{t('stoneHero.meaning')}</span>
                <span className={`sh-mc ${confClass(HERO.meaningC)}`} title={t('stoneHero.meaningConfidence')}>
                  {t('stoneHero.confidence')} {pctLabel(HERO.meaningC)}
                </span>
              </p>
              {(lang === 'ta' ? (['ta', 'en'] as const) : (['en', 'ta'] as const)).map((l, k) => (
                <p key={l} className={`sh-mean-${l}`} lang={l} data-anim={`mean-${k + 1}`}>
                  {HERO.meaning[l]}
                </p>
              ))}
            </div>
          </div>
        </div>
        <div className="sh-sum">
          <p className="sh-verdict" data-anim="verdict">
            <span>{fill(t('stoneHero.verdictLetters'), { n: HERO.letters })}</span>
            <span>
              {fill(t('stoneHero.verdictMean'), { c: '' })}
              <b>{pctLabel(HERO.mean)}</b>
            </span>
            {open > 0 && <span>{fill(t('stoneHero.verdictOpen'), { n: open })}</span>}
            <span data-anim="verdict-words">{fill(t('stoneHero.verdictWords'), { n: HERO.words.length, k: WORDS_SURE, cut })}</span>
          </p>
          <p className="sh-flagged" data-anim="verdict">
            {fill(t('stoneHero.flagged'), { cut })}
          </p>
        </div>
      </div>

      <div className="sh-bar">
        <p className="sh-credit">
          <a href={photo.commons_url} target="_blank" rel="noreferrer" data-testid="hero-credit">
            {t('stoneHero.credit')}
          </a>
          {', '}
          <a href={photo.licence_url} target="_blank" rel="noreferrer">
            CC BY 2.0
          </a>
          {', '}
          {t('stoneHero.creditVia')}
          <span className="sh-credit-sep" aria-hidden="true">
            {' · '}
          </span>
          <span className="sh-credit-by">{t('stoneHero.readingBy')}</span>
          <span className="sh-credit-sep" aria-hidden="true">
            {' · '}
          </span>
          <span className="sh-credit-by">{t('stoneHero.meaningBy')}</span>
        </p>
        {animated && (
          <span className="sh-controls">
            <button className="evo-toggle" type="button" onClick={togglePause} aria-pressed={userPaused} data-testid="stone-toggle">
              {userPaused ? t('home.heroPlay') : t('home.heroPause')}
            </button>
            <button className="evo-toggle" type="button" onClick={replay} data-testid="stone-replay">
              {t('stoneHero.replay')}
            </button>
          </span>
        )}
      </div>
    </section>
  );
}
