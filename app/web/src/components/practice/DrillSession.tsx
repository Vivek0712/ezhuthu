import { useCallback, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { buildSession, fmt, isRight, pctText, score, type Answer } from '../../practice/engine';
import { loadProgress, recordAnswer, recordSession } from '../../practice/progress';
import type { BankKind, Item, Level } from '../../practice/types';
import { Bi } from './Bi';
import { QuestionCard } from './QuestionCard';

export function ProgressDots({ total, idx, answers }: { total: number; idx: number; answers: readonly Answer[] }) {
  return (
    <div className="progress-dots" aria-hidden="true">
      {Array.from({ length: total }, (_, i) => (
        <i key={i} className={i < idx ? (answers[i]?.right ? 'done' : 'done miss') : i === idx ? 'now' : undefined} />
      ))}
    </div>
  );
}

/** Ten questions of one bank and level, then a score. Progress is saved after every answer. */
export function DrillSession({ kind, level, items, seed, onRestart }: { kind: BankKind; level: Level; items: readonly Item[]; seed: number; onRestart: () => void }) {
  const { t } = useI18n();
  const list = useMemo(() => buildSession(items, level, seed, undefined, new Set(loadProgress().recent)), [items, level, seed]);
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<Answer[]>([]);
  const started = useRef(performance.now());
  const done = idx >= list.length;
  const item = list[Math.min(idx, list.length - 1)];
  const choice = answers[idx]?.choice;

  const choose = useCallback(
    (i: number) => {
      if (!item || answers[idx]) return;
      const a: Answer = { id: item.id, kind: item.kind, level: item.level, choice: i, right: isRight(item, i), ms: performance.now() - started.current };
      setAnswers((xs) => [...xs, a]);
      recordAnswer(kind, a);
      if (idx + 1 >= list.length) recordSession(kind, [...answers, a].filter((x) => x.right).length, list.length);
    },
    [item, answers, idx, kind, list.length],
  );

  function next() {
    started.current = performance.now();
    setIdx((i) => i + 1);
    // Move focus to the new question for keyboard and screen-reader users.
    setTimeout(() => document.querySelector<HTMLElement>('[data-testid="question"] .q-title')?.focus(), 0);
  }

  if (!list.length) return <p className="note">{t('q.empty')}</p>;

  if (done) {
    const s = score(answers);
    return (
      <section className="leaf holes q-summary" data-testid="session-done" aria-labelledby="sum-title">
        <h2 id="sum-title" tabIndex={-1}>
          {t('sum.title')}
        </h2>
        <p className="q-score" data-testid="session-score">
          <strong>{fmt(t('sum.score'), { c: s.right, n: s.total })}</strong> <span className="hint-text">({pctText(s.ratio)})</span>
        </p>
        <ol className="q-review">
          {answers.map((a, i) => {
            const it = list[i]!;
            const ans = it.options[it.answer]!;
            return (
              <li key={a.id} className={a.right ? 'ok' : 'no'}>
                <span aria-hidden="true">{a.right ? '✓' : '·'}</span>{' '}
                {ans.en ? <span>{ans.en}</span> : <Bi ta={ans.ta} iso={ans.word_iso ?? ans.iso} className="bi-inline" />}
              </li>
            );
          })}
        </ol>
        <div className="row">
          <button className="btn btn-primary" type="button" onClick={onRestart} data-testid="session-again">
            {t('sum.again')}
          </button>
          {level < 3 && (
            <Link className="btn btn-ghost" to={`/practice/${kind}?level=${level + 1}`} data-testid="session-next-level">
              {t('sum.next')}
            </Link>
          )}
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

  return (
    <section className="q-session" data-testid="session">
      <div className="q-head">
        <ProgressDots total={list.length} idx={idx} answers={answers} />
        <span className="q-counter" data-testid="q-counter">
          {fmt(t('q.counter'), { i: idx + 1, n: list.length })}
        </span>
      </div>
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

export const LEVEL_KEYS: Record<BankKind, [MessageKey, MessageKey, MessageKey]> = {
  letters: ['sess.letters.l1', 'sess.letters.l2', 'sess.letters.l3'],
  words: ['sess.words.l1', 'sess.words.l2', 'sess.words.l3'],
  gaps: ['sess.gaps.l1', 'sess.gaps.l2', 'sess.gaps.l3'],
  formulas: ['sess.formulas.l1', 'sess.formulas.l2', 'sess.formulas.l3'],
};
