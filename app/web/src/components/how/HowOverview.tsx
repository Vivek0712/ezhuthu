import { useEffect, useState, type CSSProperties, type ReactNode } from 'react';
import { HERO, confClass, heroSrcSet, pctLabel } from '../../hero/heroData';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { usePrefersReducedMotion } from '../../lib/motion';
import { fmt, pctText } from '../../practice/engine';
import { NUMS, VARI, grouped } from './how-data';
import { useInView } from './useInView';
import '../../styles/how-overview.css';

// The animated overview at the top of /how-it-works: one real line of the Thanjavur photo (the home hero's stone)
// taken through the whole system. Every letter, percentage and decision comes from src/hero/hero-view.json (the real
// Reader / Restorer / Interpreter run, scripts/hero_read.py) or how-data.ts (recorded restorations and committed
// reports); nothing is invented for the animation. Reduced motion: every scene at once, as a composed still frame.

/** The line with the one letter that went to the Restorer (the hero's only gap). */
const GAP = HERO.gaps[0]!;
const ROW = HERO.rows[GAP.r]!;
const BOXES = HERO.boxes[GAP.r]!;
const { width: PW, height: PH } = HERO.photo;
const PAD = 16;
const BY0 = Math.max(0, Math.min(...BOXES.map((b) => b[1])) - PAD);
const BY1 = Math.min(PH, Math.max(...BOXES.map((b) => b[3])) + PAD);
const BH = BY1 - BY0;
/** Letters of the line before and after the gap, in today's Tamil, as the Reader named them. */
const BEFORE = ROW.glyphs.slice(Math.max(0, GAP.i - 2), GAP.i).map((g) => g.ta).join('');
const AFTER = ROW.glyphs.slice(GAP.i + 1, GAP.i + 4).map((g) => g.ta).join('');
/** The Interpreter's words that reached the Reader's own cut-off (the rest it marked unclear). */
const WORDS = HERO.words.filter((w) => (w.c ?? 0) >= HERO.letterCut);

export const SCENES = ['stone', 'reader', 'restorer', 'check', 'interp', 'tutor'] as const;
export type Scene = (typeof SCENES)[number];
const NAME: Record<Scene, MessageKey> = {
  stone: 'hx.stone',
  reader: 'hw.reader.name',
  restorer: 'hw.restorer.name',
  check: 'hw.check.name',
  interp: 'hw.interpreter.name',
  tutor: 'hw.tutor.name',
};
const ICON: Record<Scene, ReactNode> = {
  stone: <path d="M4 20h16M6 20V9l6-5 6 5v11M9 13h6M9 16h6" />,
  reader: <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z" />,
  restorer: <path d="M5 19 15 9M13 7l4 4M15 5l4 4-2 2-4-4zM4 20l2-1" />,
  check: <path d="M12 3v6M12 9l-6 6M12 9l6 6M4 17h4v4H4zM16 17h4v4h-4z" />,
  interp: <path d="M4 6h16M4 11h10M4 16h13M4 21h7" />,
  tutor: <path d="M3 9l9-5 9 5-9 5-9-5zM7 11.5V16c0 1.5 2.5 3 5 3s5-1.5 5-3v-4.5M21 9v6" />,
};

/** One gap on a 0-100% track: the fill level, and the best proposal sliding to its confidence. */
function Gauge({ label, ta, c, level, filled, testId }: { label: string; ta: string; c: number; level: number; filled: boolean; testId: string }) {
  const { t } = useI18n();
  return (
    <div className={`hx-gauge ${filled ? 'is-fill' : 'is-open'}`} data-testid={testId}>
      <div className="hx-gauge-head">
        <span className="hx-k">{label}</span>
        <span lang="ta" className="hx-ta">
          {ta}
        </span>
        <strong>{pctText(c)}</strong>
        <span className="hx-verdict">{filled ? t('hw.thrFill') : t('hw.thrOpen')}</span>
      </div>
      <div className="hx-track" style={{ '--lvl': level, '--c': c } as CSSProperties}>
        <span className="hx-track-open" />
        <span className="hx-track-level">
          <span>{fmt(t('hx.level'), { t: pctText(level) })}</span>
        </span>
        <span className="hx-track-dot" />
      </div>
    </div>
  );
}

/** The six scenes' content (the stage shows one at a time, or all of them as a still frame). */
function SceneBody({ k }: { k: Scene }) {
  const { t, lang } = useI18n();
  const best = GAP.g.gap!.best;
  switch (k) {
    case 'stone':
      return (
        <>
          <p className="hx-t">{t('hx.stoneT')}</p>
          <p className="hx-s">{t('hx.stoneS')}</p>
        </>
      );
    case 'reader':
      return (
        <>
          <p className="hx-t">{t('hx.readerT')}</p>
          {/* hero-view.json: script label, 46 letters, mean 0.65, letter_cut 0.5. */}
          <p className="hx-s">
            {fmt(t('hx.readerS'), { script: lang === 'ta' ? HERO.script.label_ta : HERO.script.label_en, n: HERO.letters, c: pctText(HERO.mean) })}
          </p>
          <p className="hx-pill hx-low">{fmt(t('hx.readerGap'), { cut: pctText(HERO.letterCut) })}</p>
        </>
      );
    case 'restorer':
      return (
        <>
          <p className="hx-t">
            {t('hx.restorerT')}{' '}
            <span lang="ta" className="hx-ta hx-ctx">
              {BEFORE} <span className="hx-q">[?]</span> {AFTER}…
            </span>
          </p>
          <ul className="hx-lanes">
            {/* how-data NUMS: 14,355 train lines (retrieval and 5-gram), 11 ms per gap; Opus for harder gaps (config/models.yaml routing). */}
            <li style={{ '--i': 0 } as CSSProperties}>
              <strong>{t('hx.lanePar')}</strong> <span>{fmt(t('hx.laneParS'), { lines: grouped(NUMS.trainLines) })}</span>
            </li>
            <li style={{ '--i': 1 } as CSSProperties}>
              <strong>{t('hx.laneNgram')}</strong> <span>{fmt(t('hx.laneNgramS'), { ms: NUMS.ngramMs })}</span>
            </li>
            <li style={{ '--i': 2 } as CSSProperties}>
              <strong>{t('hx.laneLlm')}</strong> <span>{t('hx.laneLlmS')}</span>
            </li>
          </ul>
          {best && (
            <p className="hx-best">
              {t('hx.best')}{' '}
              <span lang="ta" className="hx-ta">
                {best.ta}
              </span>{' '}
              <strong>{pctText(best.c)}</strong>
            </p>
          )}
        </>
      );
    case 'check':
      return (
        <>
          <p className="hx-t">{t('hx.checkT')}</p>
          <p className="hx-s">{t('hx.checkS')}</p>
          <div className="hx-gauges">
          {/* hero-view.json gap: best 0.0823 against its calibrated level 0.4887, abstain. */}
          {best && <Gauge label={t('hx.thisGap')} ta={best.ta} c={best.c} level={GAP.g.gap!.below} filled={GAP.g.gap!.decision !== 'abstain'} testId="hx-gauge-this" />}
          {/* how-data VARI (samples/recorded-restores.json): 0.9628 against the Sonnet level 0.4111, filled. */}
          <Gauge label={t('hx.otherGap')} ta={`வரி${VARI.top.text_tamil}பாடும்`} c={VARI.top.confidence} level={NUMS.thrSonnet} filled={VARI.decision === 'fill'} testId="hx-gauge-other" />
          </div>
        </>
      );
    case 'interp':
      return (
        <>
          <p className="hx-t">{t('hx.interpT')}</p>
          <ul className="hx-words">
            {WORDS.map((w, i) => (
              <li key={w.ta} style={{ '--i': i } as CSSProperties} className={confClass(w.c)}>
                <span lang="ta" className="hx-ta">
                  {w.ta}
                </span>
                <span className="hx-gloss">{w.en}</span>
                <span className="hx-pct">{pctLabel(w.c)}</span>
              </li>
            ))}
          </ul>
          <p className="hx-s" lang="ta">
            {HERO.phrase.ta}
          </p>
        </>
      );
    case 'tutor':
      return (
        <>
          <p className="hx-t">{t('hx.tutorT')}</p>
          {/* src/ezhuthu/agent/tutor/graph.py: restore -> lesson_builder -> tutor_team (Swarm: tutor <-> assessor). */}
          <ol className="hx-graph" aria-label={t('hx.tutorS')}>
            <li style={{ '--i': 0 } as CSSProperties}>
              <code>restore</code>
            </li>
            <li style={{ '--i': 1 } as CSSProperties}>
              <code>lesson_builder</code>
            </li>
            <li style={{ '--i': 2 } as CSSProperties} className="hx-swarm">
              {t('hx.swarm')}
            </li>
          </ol>
          {/* src/ezhuthu/agent/tutor/policy.py: the hosted Strands Decider picks the pedagogy move, inside rule guardrails. */}
          <p className="hx-s hx-dec">{t('hx.decider')}</p>
        </>
      );
  }
}

/** The animated overview: stone → Reader → Restorer → confidence check → Interpreter → Tutor. */
export function HowOverview({ sceneMs = 3800 }: { sceneMs?: number }) {
  const { t } = useI18n();
  const reduced = usePrefersReducedMotion();
  const [ref, inView] = useInView<HTMLDivElement>();
  const [scene, setScene] = useState(0);
  const [playing, setPlaying] = useState(true);
  const still = reduced;
  const running = playing && inView && !still;

  useEffect(() => {
    if (!running) return;
    const id = window.setInterval(() => setScene((s) => (s + 1) % SCENES.length), sceneMs);
    return () => window.clearInterval(id);
  }, [running, sceneMs]);

  const at = still ? SCENES.length - 1 : scene;
  return (
    <figure className="hx" aria-label={t('hx.label')} data-testid="how-hero">
      <div ref={ref} className={`hx-stage ${still ? 'hx-still' : ''} ${running ? 'is-running' : ''}`} data-scene={SCENES[at]} data-testid="hx-stage">
        <div className="hx-band" style={{ aspectRatio: `${PW} / ${BH}` } as CSSProperties}>
          <picture>
            <source type="image/avif" srcSet={heroSrcSet('avif')} sizes="(min-width: 1200px) 1100px, 100vw" />
            <source type="image/webp" srcSet={heroSrcSet('webp')} sizes="(min-width: 1200px) 1100px, 100vw" />
            <img
              src="/hero/thanjavur-800.jpg"
              srcSet={heroSrcSet('jpg')}
              sizes="(min-width: 1200px) 1100px, 100vw"
              alt=""
              width={PW}
              height={PH}
              style={{ transform: `translateY(${(-100 * BY0) / PH}%)` }}
              decoding="async"
            />
          </picture>
          <span className="hx-rake" aria-hidden="true" />
          {BOXES.map((b, i) => {
            const g = ROW.glyphs[i];
            const isGap = i === GAP.i;
            return (
              <span
                key={i}
                className={`hx-box ${isGap ? 'is-gap' : ''} ${confClass(g?.c)}`}
                style={
                  {
                    left: `${(100 * b[0]) / PW}%`,
                    width: `${(100 * (b[2] - b[0])) / PW}%`,
                    top: `${(100 * (b[1] - BY0)) / BH}%`,
                    height: `${(100 * (b[3] - b[1])) / BH}%`,
                    '--i': i,
                  } as CSSProperties
                }
                data-testid={isGap ? 'hx-box-gap' : undefined}
                aria-hidden="true"
              />
            );
          })}
        </div>
        <ol className="hx-letters" aria-hidden="true">
          {BOXES.map((b, i) => {
            const g = ROW.glyphs[i];
            const isGap = i === GAP.i;
            return (
              <li key={i} className={`${confClass(g?.c)} ${isGap ? 'is-gap' : ''}`} style={{ left: `${(50 * (b[0] + b[2])) / PW}%`, '--i': i } as CSSProperties}>
                <span lang="ta" className="hx-ta">
                  {isGap ? '[?]' : g?.ta}
                </span>
                <span className="hx-pct">{pctLabel(g?.c)}</span>
              </li>
            );
          })}
        </ol>

        <div className="hx-rail-wrap">
          <ol className="hx-rail" style={{ '--at': at } as CSSProperties}>
            {SCENES.map((k, i) => (
              <li key={k}>
                <button
                  type="button"
                  className={`hx-step ${i === at && !still ? 'is-on' : ''} ${i < at || still ? 'is-done' : ''}`}
                  aria-current={i === at && !still ? 'step' : undefined}
                  onClick={() => {
                    setScene(i);
                    setPlaying(false);
                  }}
                  data-testid={`hx-step-${k}`}
                >
                  <svg viewBox="0 0 24 24" aria-hidden="true">
                    {ICON[k]}
                  </svg>
                  <span className="hx-step-name">{t(NAME[k])}</span>
                </button>
              </li>
            ))}
          </ol>
          {!still && (
            <button type="button" className="hx-play" onClick={() => setPlaying((p) => !p)} aria-pressed={!playing} data-testid="hx-play">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                {playing ? <path d="M8 5v14M16 5v14" /> : <path d="M7 5l12 7-12 7z" />}
              </svg>
              <span className="hx-play-label">{playing ? t('hx.pause') : t('hx.play')}</span>
            </button>
          )}
        </div>

        <div className="hx-scenes">
          {SCENES.map((k, i) => (
            <section key={k} className={`hx-scene hx-scene-${k} ${still || i === at ? 'is-on' : ''}`} aria-hidden={!still && i !== at} data-testid={`hx-scene-${k}`}>
              <p className="hx-name">
                <span className="hx-num">{i + 1}</span> {t(NAME[k])}
              </p>
              <SceneBody k={k} />
            </section>
          ))}
        </div>
      </div>
      <figcaption className="hx-credit">
        <a href={HERO.photo.commons_url} target="_blank" rel="noreferrer">
          {t('hx.credit')} ↗
        </a>
      </figcaption>
    </figure>
  );
}
