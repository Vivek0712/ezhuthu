import { useEffect, useRef, useState, type CSSProperties } from 'react';
import hero from '../../../../design/glyphs/hero-evolution.json';
import { useI18n } from '../i18n/I18nProvider';
import { usePrefersReducedMotion } from '../lib/motion';

/**
 * The home hero: one letter, ka, carved through five stages (Tamil-Brahmi, Vatteluttu, Pallava, Chola, today),
 * plus the word எழுத்து drawn once. Every shape is a vector outline from design/glyphs/hero-evolution.json
 * (design/tools/build_hero.py), so the hero never waits for a web font and cannot shift the layout.
 *
 * Motion is CSS only (transform, opacity, stroke-dashoffset), driven by one cycle with staggered delays.
 * Under prefers-reduced-motion it renders a static frame: all five stages side by side, labelled.
 * The animation pauses off screen and has a visible pause control (WCAG 2.2.2). The artwork is aria-hidden;
 * the caption states what it shows.
 */
interface Stage {
  key: string;
  level: string;
  ta: string;
  en: string;
  period_ta: string;
  period_en: string;
  kind: 'fill' | 'stroke';
  d: string;
}
const STAGES = hero.stages as Stage[];
const STEP_S = 2.8; // seconds per stage; the cycle is STEP_S * STAGES.length

// Faint carved letters behind the well, in four scripts (decorative).
const BACKDROP = ['𑀓', '𑀫', '𑀢', 'க', 'ம', 'ழ', '𑌕', '𑌮', 'எ', 'ழு', 'த்', 'து', '𑀅', 'ன', 'ற', '𑀬'].map((c) => {
  const cp = c.codePointAt(0)!;
  return { c, cls: cp >= 0x11000 && cp < 0x11080 ? 'script-brahmi' : cp >= 0x11300 && cp < 0x11380 ? 'script-grantha' : 'script-chola' };
});

function Glyph({ stage, animate }: { stage: Stage; animate: boolean }) {
  if (stage.kind === 'stroke')
    return <path className={animate ? 'evo-ink evo-trace-line' : 'evo-ink-line'} d={stage.d} pathLength={1} />;
  return (
    <>
      {animate && <path className="evo-trace" d={stage.d} pathLength={1} />}
      <path className={animate ? 'evo-ink evo-fill' : 'evo-ink-fill'} d={stage.d} />
    </>
  );
}

export function EvolutionHero() {
  const { lang, t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const ref = useRef<HTMLElement>(null);
  const [paused, setPaused] = useState(false);
  const [offscreen, setOffscreen] = useState(false);
  const animate = !reduced;

  // Pause while scrolled out of view or the tab is hidden: no work for frames nobody sees.
  useEffect(() => {
    const el = ref.current;
    if (!animate || !el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(([e]) => setOffscreen(!e?.isIntersecting), { threshold: 0.05 });
    io.observe(el);
    return () => io.disconnect();
  }, [animate]);

  // Pointer parallax: CSS variables --px/--py in [-1, 1], written at most once per frame.
  useEffect(() => {
    const el = ref.current;
    if (!animate || !el) return;
    let raf = 0;
    let next: [number, number] | null = null;
    const move = (e: PointerEvent) => {
      if (e.pointerType === 'touch') return;
      const r = el.getBoundingClientRect();
      next = [((e.clientX - r.left) / r.width) * 2 - 1, ((e.clientY - r.top) / r.height) * 2 - 1];
      if (!raf)
        raf = requestAnimationFrame(() => {
          raf = 0;
          if (!next) return;
          el.style.setProperty('--px', next[0].toFixed(3));
          el.style.setProperty('--py', next[1].toFixed(3));
        });
    };
    const leave = () => {
      el.style.setProperty('--px', '0');
      el.style.setProperty('--py', '0');
    };
    el.addEventListener('pointermove', move);
    el.addEventListener('pointerleave', leave);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('pointermove', move);
      el.removeEventListener('pointerleave', leave);
    };
  }, [animate]);

  const name = (s: Stage) => (lang === 'ta' ? s.ta : s.en);
  const period = (s: Stage) => (lang === 'ta' ? s.period_ta : s.period_en);
  const vars = { '--evo-step': `${STEP_S}s`, '--evo-cycle': `${STEP_S * STAGES.length}s` } as CSSProperties;

  return (
    <figure
      ref={ref}
      className="evo-hero"
      data-testid="evolution-hero"
      data-motion={animate ? 'animated' : 'static'}
      data-paused={animate && (paused || offscreen) ? 'true' : undefined}
      style={vars}
    >
      <div className="evo-stage" aria-hidden="true">
        <div className="evo-backdrop">
          {BACKDROP.map((b, i) => (
            <span key={i} className={b.cls} style={{ '--i': i } as CSSProperties}>
              {b.c}
            </span>
          ))}
        </div>
        <svg className="evo-word" viewBox={hero.word.viewBox} data-testid="evo-word">
          {animate && <path className="evo-word-trace" d={hero.word.d} pathLength={1} />}
          <path className={animate ? 'evo-word-fill' : 'evo-word-static'} d={hero.word.d} />
        </svg>

        {animate ? (
          <>
            <div className="evo-well">
              <svg viewBox={hero.viewBox} className="evo-glyphs">
                {STAGES.map((s, i) => (
                  <g key={s.key} className="evo-frame" data-stage={s.key} style={{ '--i': i } as CSSProperties}>
                    <Glyph stage={s} animate />
                  </g>
                ))}
              </svg>
            </div>
            <div className="evo-labels">
              {STAGES.map((s, i) => (
                <p key={s.key} className="evo-label" style={{ '--i': i } as CSSProperties}>
                  <span className="evo-label-main">{name(s)}</span>
                  <span className="evo-label-sub">
                    {s.level} · {period(s)}
                  </span>
                </p>
              ))}
            </div>
          </>
        ) : (
          <div className="evo-well evo-well-static">
            <svg viewBox={hero.viewBox} className="evo-glyphs">
              <Glyph stage={STAGES[STAGES.length - 1]!} animate={false} />
            </svg>
          </div>
        )}

        <ol className="evo-rail" data-testid="evo-rail">
          {STAGES.map((s, i) => (
            <li key={s.key} className="evo-pip" style={{ '--i': i } as CSSProperties}>
              <svg viewBox={hero.viewBox}>
                <Glyph stage={s} animate={false} />
              </svg>
              {!animate && <span className="evo-pip-label">{name(s)}</span>}
            </li>
          ))}
          {animate && <li className="evo-progress" />}
        </ol>
      </div>
      <figcaption>
        <span>{t('home.heroCaption')}</span>
        {animate && (
          <button className="evo-toggle" type="button" onClick={() => setPaused((p) => !p)} aria-pressed={paused} data-testid="evo-toggle">
            {paused ? t('home.heroPlay') : t('home.heroPause')}
          </button>
        )}
      </figcaption>
    </figure>
  );
}
