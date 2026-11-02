import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import { buildTrial, fmt, isRight, score, TRIAL_SECONDS, type Answer } from '../../practice/engine';
import { loadProgress, recordAnswer, recordTrial } from '../../practice/progress';
import type { BankKind, Item } from '../../practice/types';
import { Bi } from './Bi';
import { ProgressDots } from './DrillSession';
import { QuestionCard } from './QuestionCard';

function secs(ms: number): string {
  return `${(ms / 1000).toFixed(1)} s`;
}

/** Ten mixed questions, TRIAL_SECONDS each (or no limit), then a score, the time and the best so far. */
export function TimedTrial({ banks, seed, onRestart }: { banks: Record<BankKind, Item[]>; seed: number; onRestart: () => void }) {
  const { t } = useI18n();
  const list = useMemo(() => buildTrial(banks, seed), [banks, seed]);
  const [phase, setPhase] = useState<'intro' | 'run' | 'done'>('intro');
  const [noLimit, setNoLimit] = useState(false);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const [left, setLeft] = useState(TRIAL_SECONDS * 1000);
  const [result, setResult] = useState<{ newBest: boolean; best: { right: number; total: number; ms: number } | null } | null>(null);
  const started = useRef(0);
  const item = list[idx];
  const choice = answers[idx]?.choice;

  const choose = useCallback(
    (i: number | null) => {
      if (!item || answers[idx]) return;
      const a: Answer = { id: item.id, kind: item.kind, level: item.level, choice: i, right: isRight(item, i), ms: Math.min(performance.now() - started.current, TRIAL_SECONDS * 1000) };
      setAnswers((xs) => [...xs, a]);
      recordAnswer('trial', a);
    },
    [item, answers, idx],
  );

  // The clock: only while a question is open and a limit is on.
  useEffect(() => {
    if (phase !== 'run' || noLimit || choice !== undefined) return;
    const id = window.setInterval(() => {
      const rest = TRIAL_SECONDS * 1000 - (performance.now() - started.current);
      setLeft(Math.max(0, rest));
      if (rest <= 0) choose(null);
    }, 200);
    return () => window.clearInterval(id);
  }, [phase, noLimit, choice, choose, idx]);

  function begin() {
    setPhase('run');
    setIdx(0);
    setAnswers([]);
    setLeft(TRIAL_SECONDS * 1000);
    started.current = performance.now();
  }

  function next() {
    if (idx + 1 >= list.length) {
      const s = score(answers);
      const { newBest } = recordTrial(s.right, s.total, Math.round(s.ms));
      setResult({ newBest, best: loadProgress().trial.best });
      setPhase('done');
      setTimeout(() => document.getElementById('trial-result')?.focus(), 0);
      return;
    }
    setIdx((i) => i + 1);
    setLeft(TRIAL_SECONDS * 1000);
    started.current = performance.now();
  }

  if (phase === 'intro')
    return (
      <section className="leaf holes q-intro" data-testid="trial-intro">
        <p className="lede">{fmt(t('trial.lede'), { s: TRIAL_SECONDS })}</p>
        <label className="check">
          <input type="checkbox" checked={noLimit} onChange={(e) => setNoLimit(e.target.checked)} data-testid="trial-nolimit" />
          {t('trial.noLimit')}
        </label>
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={begin} data-testid="trial-start" autoFocus>
            {t('trial.start')}
          </button>
        </div>
      </section>
    );

  if (phase === 'done') {
    const s = score(answers);
    return (
      <section className="leaf holes q-summary" data-testid="trial-done" aria-labelledby="trial-result">
        <h2 id="trial-result" tabIndex={-1}>
          {t('trial.result')}
        </h2>
        <div className="stats">
          <div className="stat">
            <div className="k">{t('trial.result')}</div>
            <div className="v" data-testid="trial-score">
              {s.right} / {s.total}
            </div>
          </div>
          <div className="stat">
            <div className="k">{t('trial.time')}</div>
            <div className="v">{secs(s.ms)}</div>
          </div>
          {result?.best && (
            <div className="stat">
              <div className="k">{t('trial.best')}</div>
              <div className="v" data-testid="trial-best">
                {result.best.right} / {result.best.total} <small className="hint-text">{secs(result.best.ms)}</small>
              </div>
            </div>
          )}
        </div>
        {result?.newBest && (
          <p className="chip chip-ok" role="status" data-testid="trial-newbest">
            {t('trial.newBest')}
          </p>
        )}
        <ol className="q-review">
          {answers.map((a, i) => {
            const it = list[i]!;
            const ans = it.options[it.answer]!;
            return (
              <li key={a.id} className={a.right ? 'ok' : 'no'}>
                <span aria-hidden="true">{a.right ? '✓' : '·'}</span> {ans.en ? <span>{ans.en}</span> : <Bi ta={ans.ta} iso={ans.word_iso ?? ans.iso} className="bi-inline" />}
                {a.choice === null && <span className="hint-text"> ({t('trial.timedOut')})</span>}
              </li>
            );
          })}
        </ol>
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={onRestart} data-testid="trial-again">
            {t('trial.again')}
          </button>
          <Link className="btn btn-ghost" to="/practice">
            {t('sum.hub')}
          </Link>
          <Link className="hero-link" to="/progress">
            {t('sum.progress')} →
          </Link>
        </div>
      </section>
    );
  }

  const frac = left / (TRIAL_SECONDS * 1000);
  return (
    <section className="q-session" data-testid="trial">
      <div className="q-head">
        <ProgressDots total={list.length} idx={idx} answers={answers} />
        <span className="q-counter" data-testid="q-counter">
          {fmt(t('q.counter'), { i: idx + 1, n: list.length })}
        </span>
      </div>
      {noLimit ? (
        <p className="hint-text">{t('trial.noClock')}</p>
      ) : (
        <div className="q-clock" data-low={frac < 0.3 ? 'yes' : 'no'}>
          <div className="q-bar q-clock-bar" aria-hidden="true">
            <span style={{ width: `${(choice === undefined ? frac : 0) * 100}%` }} />
          </div>
          <span className="q-clock-text" data-testid="trial-clock">
            {fmt(t('trial.left'), { s: Math.ceil(left / 1000) })}
          </span>
        </div>
      )}
      <QuestionCard
        key={item!.id}
        item={item!}
        choice={choice}
        onChoose={choose}
        footer={
          choice !== undefined && (
            <div className="row row-end">
              <button className="btn btn-primary" type="button" onClick={next} autoFocus data-testid="q-next">
                {idx + 1 >= list.length ? t('q.finish') : t('q.next')}
              </button>
            </div>
          )
        }
      />
    </section>
  );
}
