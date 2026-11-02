import { useCallback, useEffect, useRef, useState, type CSSProperties, type RefObject } from 'react';
import { HERO, heroSrcSet, type HeroAkshara } from '../hero/heroData';
import { useI18n } from '../i18n/I18nProvider';
import { usePrefersReducedMotion } from '../lib/motion';
import '../styles/stone-hero.css';

/**
 * The home hero: a real photograph of a Chola-period inscription (Brihadisvara temple, Thanjavur; Richard Mortel,
 * CC BY 2.0), read by Ezhuthu's own Reader and Restorer. Every letter, confidence and abstention shown comes from
 * src/hero/hero-reading.json (scripts/hero_read.py + scripts/hero_build.py): nothing is invented for the animation.
 *
 * Storyboard, one cycle of CYCLE_MS: (a) the stone fades in with a slow Ken Burns drift and a raking-light sweep;
 * (b) a scan beam passes and the carved letters light up on their hand-annotated boxes, line by line; (c) the lit
 * letters lift off as glowing fragments and fly along curves into the pipeline (Reader -> Restorer -> Strands
 * Decider), whose nodes pulse as they work; (d) the reading lands letter by letter as Tamil Unicode, tinted by
 * confidence, with each abstained gap shown as "?"; (e) the transliteration, the verdict (confidence, gaps left open,
 * expert review) and the honest note follow, and the page's call-to-action row glows.
 *
 * Motion is the Web Animations API on transform and opacity only (no library). Positions are measured once per cycle
 * (getBoundingClientRect, batched before any animation starts), so there is no layout thrash during the cycle. The
 * cycle starts when the hero is on screen, pauses off screen or in a hidden tab, and has visible Pause and Replay
 * buttons. Under prefers-reduced-motion, or without element.animate (old browsers, jsdom), it renders the composed
 * final frame: photo with the letters marked, the pipeline, and the full reading. The artwork is aria-hidden; the
 * reading is real, selectable text with lang="ta".
 */

const CYCLE_MS = 16_000;
// Ken Burns drift of the photo: scale and translate (in % of the photo) at the start, reaching none at KB_END.
const KB = { s: 1.06, tx: -0.012, ty: 0.008 };
const KB_END = 0.9;
/** The drift at time t (ms into the cycle): linear, as the keyframes below. */
function kbAt(t: number) {
  const p = Math.min(1, t / (CYCLE_MS * KB_END));
  return { s: KB.s + (1 - KB.s) * p, tx: KB.tx * (1 - p), ty: KB.ty * (1 - p) };
}
const T = {
  photoIn: 0,
  rake: 500,
  beam: 1500,
  boxes: 1800, // + row * ROW_BOX + i * LETTER_BOX
  lift: 4600, // + row * ROW_LIFT + i * LETTER_LIFT
  reader: 4900,
  restorer: 6700,
  decider: 7500,
  land: 8500, // + line * ROW_LAND + k * LETTER_LAND
  verdict: 11_100,
  cta: 11_700,
  fadeOut: 14_300,
};
const ROW_BOX = 600;
const LETTER_BOX = 45;
const ROW_LIFT = 330;
const LETTER_LIFT = 32;
const ROW_LAND = 480;
const LETTER_LAND = 42;

type Phase = 'idle' | 'running' | 'paused';

function canAnimate(): boolean {
  return typeof Element !== 'undefined' && typeof Element.prototype.animate === 'function';
}

function pct(v: number, of: number): string {
  return `${((v / of) * 100).toFixed(3)}%`;
}

function confClass(c: number | null | undefined): string {
  if (c == null) return 'sh-c-none';
  if (c >= 0.75) return 'sh-c-high';
  if (c >= 0.5) return 'sh-c-mid';
  return 'sh-c-low';
}

function fmt(c: number | null | undefined): string {
  return c == null ? '–' : c.toFixed(2);
}

/** Quadratic Bezier from (0,0) to (dx,dy) bowing sideways, sampled for WAAPI keyframes. */
function flightKeyframes(dx: number, dy: number, bow: number, endScale: number): Keyframe[] {
  const cx = dx * 0.5 - dy * bow;
  const cy = dy * 0.5 + dx * bow - Math.abs(dx) * 0.18;
  const frames: Keyframe[] = [];
  const N = 12;
  for (let k = 0; k <= N; k++) {
    const t = k / N;
    const lift = k === 1 ? 0.08 : 0;
    const x = 2 * (1 - t) * t * cx + t * t * dx;
    const y = 2 * (1 - t) * t * cy + t * t * dy - lift * 40;
    const s = k === 0 ? 1 : k === 1 ? 1.12 : 1.12 + (endScale - 1.12) * ((k - 1) / (N - 1));
    frames.push({
      transform: `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${s.toFixed(3)})`,
      opacity: k === 0 || k === N ? 0 : k >= N - 2 ? 0.7 : 1,
      offset: t,
    });
  }
  return frames;
}

function Akshara({ a, gapLabel }: { a: HeroAkshara; gapLabel: string }) {
  if (a.kind === 'space') return <span className="sh-sp"> </span>;
  if (a.kind === 'gap')
    return (
      <span className="sh-ak sh-gap">
        <span aria-hidden="true">?</span>
        <span className="visually-hidden">{gapLabel}</span>
        {a.best && (
          <small className="sh-guess">
            {a.best.ta} {fmt(a.best.confidence)}
          </small>
        )}
      </span>
    );
  return (
    <span className="sh-ak">
      {a.ta}
    </span>
  );
}

export function StoneHero({ ctaRef }: { ctaRef?: RefObject<HTMLElement | null> }) {
  const { lang, t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const animated = !reduced && canAnimate();
  const rootRef = useRef<HTMLElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const flightRef = useRef<HTMLDivElement>(null);
  const anims = useRef<Animation[]>([]);
  const [phase, setPhase] = useState<Phase>('idle');
  const [userPaused, setUserPaused] = useState(false);
  const visible = useRef(false);
  const tabVisible = useRef(true);
  const userPausedRef = useRef(false);

  const clear = useCallback(() => {
    for (const a of anims.current) a.cancel();
    anims.current = [];
    const fl = flightRef.current;
    if (fl) fl.replaceChildren();
  }, []);

  /** Build and start one full cycle. All measuring happens here, before the first animation is created. */
  const start = useCallback(() => {
    const root = rootRef.current;
    const stage = stageRef.current;
    const flight = flightRef.current;
    if (!root || !stage || !flight) return;
    clear();
    const list: Animation[] = [];
    const add = (el: Element, kf: Keyframe[], o: KeyframeAnimationOptions) => {
      list.push(el.animate(kf, { fill: 'both', easing: 'cubic-bezier(.2,0,0,1)', ...o }));
    };
    const q = <E extends Element>(sel: string) => Array.from(root.querySelectorAll<E>(sel));

    // ---- measure (one batch of reads) ----
    const sr = stage.getBoundingClientRect();
    const rel = (r: DOMRect) => ({ x: r.left - sr.left, y: r.top - sr.top, w: r.width, h: r.height });
    const img = root.querySelector<HTMLImageElement>('.sh-photo img');
    const kb = root.querySelector<HTMLElement>('.sh-kb');
    const boxes = q<HTMLElement>('.sh-box');
    const boxRects = boxes.map((b) => rel(b.getBoundingClientRect()));
    const kbRect = kb ? rel(kb.getBoundingClientRect()) : null;
    const nodes = q<HTMLElement>('.sh-node-dot');
    const nodeRects = nodes.map((n) => rel(n.getBoundingClientRect()));
    const landEls = q<HTMLElement>('[data-anim="land"]');
    const landRects = landEls.map((n) => rel(n.getBoundingClientRect()));
    const src = img?.currentSrc || img?.src || '';
    const vertical = nodeRects.length === 3 && Math.abs(nodeRects[2]!.y - nodeRects[0]!.y) > Math.abs(nodeRects[2]!.x - nodeRects[0]!.x);

    // ---- (a) stone, drift, raking light ----
    if (kb) {
      add(kb, [
        { opacity: 0, transform: `scale(${KB.s}) translate(${KB.tx * 100}%, ${KB.ty * 100}%)` },
        { opacity: 1, offset: 0.07 },
        { opacity: 1, transform: 'scale(1) translate(0, 0)', offset: KB_END },
        { opacity: 1, transform: 'scale(1) translate(0, 0)' },
      ], { duration: CYCLE_MS, easing: 'linear' });
    }
    q('.sh-rake').forEach((el) =>
      add(el, [{ transform: 'translateX(-60%)', opacity: 0 }, { opacity: 1, offset: 0.25 }, { opacity: 1, offset: 0.7 }, { transform: 'translateX(60%)', opacity: 0 }], { duration: 2400, delay: T.rake, easing: 'cubic-bezier(.65,0,.35,1)' }),
    );
    // ---- (b) scan beam + letters lighting up ----
    q('.sh-beam').forEach((el) =>
      add(el, [{ transform: 'translateY(-56%)', opacity: 0 }, { opacity: 1, offset: 0.1 }, { opacity: 1, offset: 0.88 }, { transform: 'translateY(56%)', opacity: 0 }], { duration: 2900, delay: T.beam, easing: 'linear' }),
    );
    boxes.forEach((b) => {
      const r = Number(b.dataset.row);
      const i = Number(b.dataset.i);
      const on = T.boxes + r * ROW_BOX + i * LETTER_BOX;
      const lift = T.lift + r * ROW_LIFT + i * LETTER_LIFT;
      add(b, [
        { opacity: 0, transform: 'scale(1.18)' },
        { opacity: 1, transform: 'scale(1)', offset: 420 / (lift - on + 900) },
        { opacity: 1, transform: 'scale(1)', offset: (lift - on) / (lift - on + 900) },
        { opacity: 0.35, transform: 'scale(1)' },
      ], { duration: lift - on + 900, delay: on });
      add(b, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: T.fadeOut, composite: 'replace', fill: 'forwards' });
    });

    // ---- (c) fragments fly into the Reader; nodes pulse ----
    const reader = nodeRects[0];
    if (reader && kbRect && src) {
      const frag = document.createDocumentFragment();
      boxes.forEach((b, idx) => {
        const r = Number(b.dataset.row);
        const i = Number(b.dataset.i);
        const delay = T.lift + r * ROW_LIFT + i * LETTER_LIFT;
        // Where the letter is at lift time: the photo is still drifting (scale about its centre, then translate).
        const { s, tx, ty } = kbAt(delay);
        const cx = kbRect.x + kbRect.w / 2;
        const cy = kbRect.y + kbRect.h / 2;
        const map = (x: number, y: number) => [cx + s * (x - cx + tx * kbRect.w), cy + s * (y - cy + ty * kbRect.h)] as const;
        const b0 = boxRects[idx]!;
        const [bx, by] = map(b0.x, b0.y);
        const [kx, ky] = map(kbRect.x, kbRect.y);
        const br = { x: bx, y: by, w: b0.w * s, h: b0.h * s };
        const el = document.createElement('span');
        el.className = 'sh-frag';
        el.style.left = `${br.x}px`;
        el.style.top = `${br.y}px`;
        el.style.width = `${br.w}px`;
        el.style.height = `${br.h}px`;
        el.style.backgroundImage = `url("${src}")`;
        el.style.backgroundSize = `${kbRect.w * s}px ${kbRect.h * s}px`;
        el.style.backgroundPosition = `${kx - br.x}px ${ky - br.y}px`;
        frag.appendChild(el);
        const dx = reader.x + reader.w / 2 - (br.x + br.w / 2);
        const dy = reader.y + reader.h / 2 - (br.y + br.h / 2);
        const bow = vertical ? 0.12 + (i % 3) * 0.05 : -0.1 - (r % 2) * 0.08 - (i % 3) * 0.03;
        list.push(el.animate(flightKeyframes(dx, dy, bow, 0.18), { duration: 1250 + (i % 4) * 90, delay, fill: 'both', easing: 'cubic-bezier(.45,0,.25,1)' }));
      });
      flight.appendChild(frag);
    }
    const pulse = (sel: string, at: number, ms: number) =>
      q(sel).forEach((el) => {
        add(el, [{ opacity: 0, transform: 'scale(.8)' }, { opacity: 1, transform: 'scale(1)', offset: 0.15 }, { opacity: 1, transform: 'scale(1.06)', offset: 0.5 }, { opacity: 1, transform: 'scale(1)', offset: 0.85 }, { opacity: 0, transform: 'scale(1.25)' }], { duration: ms, delay: at, easing: 'ease-in-out' });
      });
    pulse('[data-node="reader"] .sh-node-glow', T.reader, 2200);
    pulse('[data-node="restorer"] .sh-node-glow', T.restorer, 1400);
    pulse('[data-node="decider"] .sh-node-glow', T.decider, 1500);
    const readout = (sel: string, at: number) =>
      q(sel).forEach((el) => add(el, [{ opacity: 0, transform: 'translateY(4px)' }, { opacity: 1, transform: 'none' }], { duration: 380, delay: at }));
    readout('[data-node="reader"] .sh-node-out', T.reader + 1900);
    readout('[data-node="restorer"] .sh-node-out', T.restorer + 1100);
    readout('[data-node="decider"] .sh-node-out', T.decider + 1200);
    // Sparks along the connectors, Reader -> Restorer -> Decider.
    q<HTMLElement>('.sh-spark').forEach((el) => {
      const seg = Number(el.dataset.seg);
      const a = nodeRects[seg];
      const z = nodeRects[seg + 1];
      if (!a || !z) return;
      const dx = z.x - a.x;
      const dy = z.y - a.y;
      const k = Number(el.dataset.k);
      add(el, [{ transform: 'translate(0,0) scale(.6)', opacity: 0 }, { opacity: 1, offset: 0.2 }, { opacity: 1, offset: 0.8 }, { transform: `translate(${dx}px, ${dy}px) scale(1)`, opacity: 0 }], { duration: 650, delay: (seg === 0 ? T.restorer - 450 : T.decider - 420) + k * 120, easing: 'cubic-bezier(.45,0,.25,1)' });
    });

    // ---- (d) the reading lands, letter by letter, out of the Decider ----
    const dec = nodeRects[2];
    if (dec) {
      landEls.forEach((el, idx) => {
        const lr = landRects[idx]!;
        const line = Number(el.closest<HTMLElement>('[data-line]')?.dataset.line ?? 0);
        const k = Number(el.dataset.k ?? idx);
        const dx = dec.x + dec.w / 2 - (lr.x + lr.w / 2);
        const dy = dec.y + dec.h / 2 - (lr.y + lr.h / 2);
        const at = T.land + line * ROW_LAND + k * LETTER_LAND;
        add(el, [
          { opacity: 0, transform: `translate(${dx}px, ${dy}px) scale(.35)` },
          { opacity: 1, offset: 0.35 },
          { opacity: 1, transform: 'translate(0, -6%) scale(1.12)', offset: 0.78 },
          { opacity: 1, transform: 'none' },
        ], { duration: 760, delay: at, easing: 'cubic-bezier(.3,0,.2,1)' });
        add(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: T.fadeOut, fill: 'forwards' });
      });
    }
    q<HTMLElement>('[data-anim="after-line"]').forEach((el) => {
      const line = Number(el.closest<HTMLElement>('[data-line]')?.dataset.line ?? 0);
      add(el, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], { duration: 500, delay: T.land + line * ROW_LAND + 620 });
      add(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: T.fadeOut, fill: 'forwards' });
    });
    // ---- (e) verdict, note, call to action ----
    q<HTMLElement>('[data-anim="verdict"]').forEach((el, i) => {
      add(el, [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], { duration: 600, delay: T.verdict + i * 380 });
      add(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: T.fadeOut, fill: 'forwards' });
    });
    q('[data-anim="node-out-hide"]').forEach((el) => add(el, [{ opacity: 1 }, { opacity: 0 }], { duration: 700, delay: T.fadeOut, fill: 'forwards' }));
    const cta = ctaRef?.current;
    if (cta) {
      cta.querySelectorAll('.btn').forEach((b, i) =>
        list.push(b.animate([{ transform: 'none' }, { transform: 'translateY(-3px) scale(1.04)', offset: 0.35 }, { transform: 'none' }], { duration: 800, delay: T.cta + i * 140, easing: 'ease-in-out' })),
      );
    }

    // The clock: when it finishes, the next cycle starts (if still on screen and not paused).
    const clock = stage.animate([], { duration: CYCLE_MS });
    clock.onfinish = () => {
      if (visible.current && tabVisible.current && !userPausedRef.current) start();
    };
    list.push(clock);
    anims.current = list;
    setPhase('running');
  }, [clear, ctaRef]);

  const pause = useCallback(() => {
    for (const a of anims.current) if (a.playState === 'running') a.pause();
    setPhase((p) => (p === 'running' ? 'paused' : p));
  }, []);
  const resume = useCallback(() => {
    if (!anims.current.length) return start();
    for (const a of anims.current) if (a.playState === 'paused') a.play();
    setPhase('running');
  }, [start]);

  // Start when on screen; pause when off screen or when the tab is hidden.
  useEffect(() => {
    const root = rootRef.current;
    if (!animated || !root) return;
    const sync = () => {
      const go = visible.current && tabVisible.current && !userPausedRef.current;
      if (go) resume();
      else pause();
    };
    let io: IntersectionObserver | null = null;
    if (typeof IntersectionObserver !== 'undefined') {
      io = new IntersectionObserver(([e]) => {
        visible.current = !!e?.isIntersecting;
        sync();
      }, { threshold: 0.2 });
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
    start();
  };

  const { photo, boxes, lines } = HERO;
  const lowestLine = Math.min(...lines.map((l) => l.confidence ?? 1));
  let k = 0;
  const vars = { '--sh-aspect': `${photo.width} / ${photo.height}` } as CSSProperties;

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
              <picture>
                <source type="image/avif" srcSet={heroSrcSet('avif')} sizes="(min-width: 900px) 46vw, 100vw" />
                <source type="image/webp" srcSet={heroSrcSet('webp')} sizes="(min-width: 900px) 46vw, 100vw" />
                <img
                  src="/hero/thanjavur-800.jpg"
                  srcSet={heroSrcSet('jpg')}
                  sizes="(min-width: 900px) 46vw, 100vw"
                  width={photo.width}
                  height={photo.height}
                  alt=""
                  decoding="async"
                  fetchPriority="high"
                />
              </picture>
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
            </div>
            <span className="sh-rake" />
            <span className="sh-beam" />
          </div>
          <figcaption className="sh-place">{t('stoneHero.place')}</figcaption>
        </figure>

        <ol className="sh-pipe" aria-hidden="true">
          {(
            [
              ['reader', 'stoneHero.reader', 'stoneHero.readerSub', `${lang === 'ta' ? HERO.script.label_ta : HERO.script.label_en} · ${fmt(HERO.confidence)}`],
              ['restorer', 'stoneHero.restorer', 'stoneHero.restorerSub', `${HERO.gaps} ${t('stoneHero.gaps')}`],
              ['decider', 'stoneHero.decider', 'stoneHero.deciderSub', `${HERO.gaps - HERO.fills} × ? · ${t('stoneHero.abstain')}`],
            ] as const
          ).map(([key, label, sub, out], i) => (
            <li key={key} className="sh-node" data-node={key}>
              <span className="sh-node-dot">
                <span className="sh-node-glow" />
                <span className="sh-node-n">{i + 1}</span>
              </span>
              <span className="sh-node-text">
                <b>{t(label)}</b>
                <small>{t(sub)}</small>
                <span className="sh-node-out" data-anim="node-out-hide">
                  {out}
                </span>
              </span>
              {i < 2 && (
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
            <span className="sh-chip">{t('stoneHero.unverified')}</span>
          </p>
          <div className="sh-lines">
            {lines.map((l, li) => (
              <div key={l.n} className="sh-line" data-line={li}>
                <p className={`sh-ta script-chola ${confClass(l.confidence)}`} lang="ta">
                  {l.aksharas.map((a, ai) => {
                    if (a.kind === 'space') return <Akshara key={ai} a={a} gapLabel={t('stoneHero.gap')} />;
                    return (
                      <span key={ai} className="sh-akw" data-k={k++} data-anim="land">
                        <Akshara a={a} gapLabel={t('stoneHero.gap')} />
                      </span>
                    );
                  })}
                </p>
                <p className="sh-meta" data-anim="after-line">
                  <span className="sh-iso iso" lang="ta-Latn">
                    {l.iso}
                  </span>
                  <span className="sh-lc" title={t('stoneHero.lineConfidence')}>
                    {fmt(l.confidence)}
                  </span>
                </p>
              </div>
            ))}
          </div>
          <p className="sh-verdict" data-anim="verdict">
            <span>
              {t('stoneHero.confidence')} <b>{fmt(HERO.confidence)}</b>
            </span>
            <span>
              {HERO.gaps - HERO.fills} {t('stoneHero.abstained')}
            </span>
          </p>
          <p className="sh-review" data-anim="verdict">
            {HERO.confidence < HERO.abstainBelow && lowestLine < HERO.abstainBelow ? t('stoneHero.toReview') : null}
          </p>
          <p className="sh-note" data-anim="verdict">
            {t('stoneHero.noEdition')}
          </p>
        </div>
        <div className="sh-flight" ref={flightRef} aria-hidden="true" />
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
