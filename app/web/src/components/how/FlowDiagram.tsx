import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { usePrefersReducedMotion } from '../../lib/motion';
import { fmt } from '../../practice/engine';
import { Diagram, useNarrow, type DEdge, type DLayout, type DNode } from './Diagram';
import { useInView } from './useInView';

// One request through the agents (src/ezhuthu/agent/README.md, config/models.yaml): the photo path (Reader, Opus
// re-read when unsure), the text path, the Restorer's evidence (parallels, ontology over MCP, 5-gram, Sonnet ->
// Opus), the confidence check (pre-rank + VAL Platt calibration), fill or abstain, the Interpreter, expert review.
const EDGES: DEdge[] = [
  { id: 'e-photo-reader', from: 'photo', to: 'reader', kind: 'photo' },
  { id: 'e-reader-reread', from: 'reader', to: 'reread', kind: 'branch', dashed: true },
  { id: 'e-reader-restorer', from: 'reader', to: 'restorer', kind: 'photo' },
  { id: 'e-text-restorer', from: 'text', to: 'restorer', kind: 'text' },
  { id: 'e-restorer-retrieval', from: 'restorer', to: 'retrieval' },
  { id: 'e-restorer-ontology', from: 'restorer', to: 'ontology' },
  { id: 'e-restorer-ngram', from: 'restorer', to: 'ngram' },
  { id: 'e-restorer-sonnet', from: 'restorer', to: 'sonnet' },
  { id: 'e-sonnet-opus', from: 'sonnet', to: 'opus', kind: 'branch', dashed: true },
  { id: 'e-retrieval-check', from: 'retrieval', to: 'check' },
  { id: 'e-ontology-check', from: 'ontology', to: 'check' },
  { id: 'e-ngram-check', from: 'ngram', to: 'check' },
  { id: 'e-sonnet-check', from: 'sonnet', to: 'check' },
  { id: 'e-opus-check', from: 'opus', to: 'check', kind: 'branch', dashed: true },
  { id: 'e-check-fill', from: 'check', to: 'fill' },
  { id: 'e-check-open', from: 'check', to: 'open', kind: 'branch', dashed: true },
  { id: 'e-fill-interp', from: 'fill', to: 'interp' },
  { id: 'e-interp-you', from: 'interp', to: 'you' },
  { id: 'e-open-expert', from: 'open', to: 'expert', kind: 'branch', dashed: true },
  { id: 'e-expert-you', from: 'expert', to: 'you', kind: 'branch', dashed: true },
];

/** The hops, in order. Each lights up its nodes and edges and shows its caption. */
export const FLOW_STEPS: { caption: MessageKey; ids: string[] }[] = [
  { caption: 'hw.s1', ids: ['photo', 'e-photo-reader', 'reader'] },
  { caption: 'hw.s2', ids: ['reader', 'e-reader-reread', 'reread'] },
  { caption: 'hw.s3', ids: ['text', 'e-text-restorer', 'e-reader-restorer', 'restorer'] },
  { caption: 'hw.s4', ids: ['restorer', 'e-restorer-retrieval', 'e-restorer-ontology', 'e-restorer-ngram', 'retrieval', 'ontology', 'ngram'] },
  { caption: 'hw.s5', ids: ['restorer', 'e-restorer-sonnet', 'sonnet'] },
  { caption: 'hw.s6', ids: ['sonnet', 'e-sonnet-opus', 'opus'] },
  { caption: 'hw.s7', ids: ['e-retrieval-check', 'e-ontology-check', 'e-ngram-check', 'e-sonnet-check', 'e-opus-check', 'check'] },
  { caption: 'hw.s8', ids: ['check', 'e-check-fill', 'fill'] },
  { caption: 'hw.s9', ids: ['check', 'e-check-open', 'open'] },
  { caption: 'hw.s10', ids: ['fill', 'e-fill-interp', 'interp', 'e-interp-you', 'you'] },
  { caption: 'hw.s11', ids: ['open', 'e-open-expert', 'expert', 'e-expert-you', 'you'] },
];

const W = 142;
const H = 72;
const col = (i: number) => 10 + i * 184;
const row = (i: number) => 16 + i * 96;
const WIDE: DLayout = {
  width: col(5) + W + 10,
  height: row(5) + H + 16,
  w: W,
  h: H,
  at: {
    photo: [col(0), row(0)],
    reader: [col(1), row(0)],
    reread: [col(2), row(0)],
    text: [col(0), row(2)],
    restorer: [col(1), row(2)],
    retrieval: [col(2), row(1)],
    ontology: [col(2), row(2)],
    ngram: [col(2), row(3)],
    sonnet: [col(2), row(4)],
    opus: [col(3), row(4)],
    check: [col(3), row(2)],
    fill: [col(4), row(1)],
    open: [col(4), row(3)],
    interp: [col(5), row(1)],
    you: [col(5), row(3)],
    expert: [col(4), row(5)],
  },
};
const NW = 150;
const L = 8;
const R = 202;
const nrow = (i: number) => 10 + i * 92;
const NARROW: DLayout = {
  width: 360,
  height: nrow(9) + H + 10,
  w: NW,
  h: H,
  at: {
    photo: [L, nrow(0)],
    reread: [R, nrow(0)],
    reader: [L, nrow(1)],
    text: [R, nrow(1)],
    restorer: [L, nrow(2)],
    retrieval: [R, nrow(2)],
    ontology: [R, nrow(3)],
    sonnet: [L, nrow(4)],
    ngram: [R, nrow(4)],
    opus: [R, nrow(5)],
    check: [L, nrow(6)],
    fill: [L, nrow(7)],
    open: [R, nrow(7)],
    interp: [L, nrow(8)],
    expert: [R, nrow(8)],
    you: [L, nrow(9)],
  },
};

/** Animated, step-through diagram of one request flowing through the agents. It starts playing by itself the first
 * time it scrolls into view (not with reduced motion); "Play the flow" and the arrows step it by hand. */
export function FlowDiagram({ intervalMs = 2600, autoPlay = true }: { intervalMs?: number; autoPlay?: boolean }) {
  const { t } = useI18n();
  const narrow = useNarrow();
  const reduced = usePrefersReducedMotion();
  const [ref, inView] = useInView<HTMLElement>(true);
  const autoStarted = useRef(false);
  const [step, setStep] = useState(-1); // -1: not started (everything shown, nothing highlighted)
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);
  const total = FLOW_STEPS.length;

  const nodes: DNode[] = useMemo(
    () => [
      { id: 'photo', label: t('hw.n.photo'), sub: t('hw.n.photoSub'), tone: 'io' },
      { id: 'text', label: t('hw.n.text'), sub: t('hw.n.textSub'), tone: 'io' },
      { id: 'reader', label: t('hw.reader.name'), sub: t('hw.n.readerSub'), tone: 'agent' },
      { id: 'reread', label: t('hw.n.reread'), sub: t('hw.n.rereadSub'), tone: 'branch' },
      { id: 'restorer', label: t('hw.restorer.name'), sub: t('hw.n.restorerSub'), tone: 'agent' },
      { id: 'retrieval', label: t('hw.n.retrieval'), sub: t('hw.n.retrievalSub'), tone: 'data' },
      { id: 'ontology', label: t('hw.ontology.name'), sub: t('hw.n.ontologySub'), tone: 'data' },
      { id: 'ngram', label: t('hw.n.ngram'), sub: t('hw.n.ngramSub'), tone: 'data' },
      // Product names, the same in both languages (config/models.yaml llm.default / llm.escalate).
      { id: 'sonnet', label: 'Sonnet 4.6', sub: t('hw.n.sonnetSub'), tone: 'model' },
      { id: 'opus', label: 'Opus 4.6', sub: t('hw.n.opusSub'), tone: 'branch' },
      { id: 'check', label: t('hw.check.name'), sub: t('hw.n.checkSub'), tone: 'agent' },
      { id: 'fill', label: t('hw.n.fill'), sub: t('hw.n.fillSub'), tone: 'io' },
      { id: 'open', label: t('hw.n.open'), sub: t('hw.n.openSub'), tone: 'branch' },
      { id: 'interp', label: t('hw.interpreter.name'), sub: t('hw.n.interpreterSub'), tone: 'agent' },
      { id: 'you', label: t('hw.n.you'), sub: t('hw.n.youSub'), tone: 'io' },
      { id: 'expert', label: t('hw.review.name'), sub: t('hw.n.expertSub'), tone: 'people' },
    ],
    [t],
  );

  const stop = useCallback(() => {
    if (timer.current !== null) window.clearInterval(timer.current);
    timer.current = null;
    setPlaying(false);
  }, []);
  useEffect(() => stop, [stop]);
  useEffect(() => {
    if (!playing) return;
    timer.current = window.setInterval(() => setStep((s) => Math.min(s + 1, total - 1)), intervalMs);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
      timer.current = null;
    };
  }, [playing, intervalMs, total]);
  // The last hop stays on screen; playing stops there.
  useEffect(() => {
    if (playing && step >= total - 1) stop();
  }, [playing, step, total, stop]);

  useEffect(() => {
    if (!autoPlay || reduced || !inView || autoStarted.current) return;
    autoStarted.current = true;
    setStep(0);
    setPlaying(true);
  }, [autoPlay, reduced, inView]);

  const play = () => {
    autoStarted.current = true;
    if (playing) return stop();
    setStep((s) => (s < 0 || s >= total - 1 ? 0 : s + 1));
    setPlaying(true);
  };
  const go = (d: number) => {
    autoStarted.current = true;
    stop();
    setStep((s) => Math.min(total - 1, Math.max(0, (s < 0 ? -1 : s) + d)));
  };

  const active = useMemo(() => new Set(step >= 0 ? FLOW_STEPS[step]!.ids : []), [step]);
  const done = useMemo(() => new Set(FLOW_STEPS.slice(0, Math.max(0, step)).flatMap((s) => s.ids)), [step]);

  return (
    <figure ref={ref} className={`flow ${reduced ? 'flow-still' : ''}`} data-testid="flow" data-step={step + 1}>
      <div className="flow-controls">
        <button type="button" className="btn btn-primary" onClick={play} data-testid="flow-play" aria-pressed={playing}>
          {playing ? t('hw.flowPause') : t('hw.flowPlay')}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => go(-1)} disabled={step <= 0} data-testid="flow-prev" aria-label={t('hw.flowPrev')}>
          ←
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => go(1)} disabled={step >= total - 1} data-testid="flow-next" aria-label={t('hw.flowNext')}>
          →
        </button>
        <span className="flow-count" data-testid="flow-count">
          {step >= 0 ? fmt(t('hw.flowStep'), { n: step + 1, total }) : ''}
        </span>
      </div>
      <p className="flow-caption" aria-live="polite" data-testid="flow-caption">
        {step >= 0 ? t(FLOW_STEPS[step]!.caption) : t('hw.flowIdle')}
      </p>
      <div className="flow-canvas">
        <Diagram id="flow" nodes={nodes} edges={EDGES} layout={narrow ? NARROW : WIDE} active={active} done={done} title={t('hw.flowTitle')} testId="flow-svg" labelLines={2} />
      </div>
      <figcaption className="flow-legend hint-text">
        <span className="lg lg-photo">{t('hw.flowLegendPhoto')}</span>
        <span className="lg lg-text">{t('hw.flowLegendText')}</span>
        <span className="lg lg-branch">{t('hw.flowLegendBranch')}</span>
      </figcaption>
      <details className="flow-list">
        <summary>{t('hw.flowList')}</summary>
        <ol>
          {FLOW_STEPS.map((s) => (
            <li key={s.caption}>{t(s.caption)}</li>
          ))}
        </ol>
      </details>
    </figure>
  );
}
