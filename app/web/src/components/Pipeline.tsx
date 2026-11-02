import type { ReactNode } from 'react';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { fmt, pctText } from '../practice/engine';
import worked from '../practice/banks/worked-example.json';
import type { WorkedExample } from '../practice/types';
import { Bi } from './practice/Bi';

export const EXAMPLE = worked as unknown as WorkedExample;

/** The few words either side of the gap, both scripts, with the gap marker kept. */
export function exampleSnippet(ex: WorkedExample = EXAMPLE, words = 1): { ta: string; iso: string } {
  const lastWords = (s: string) => s.trim().split(/\s+/).slice(-words).join(' ');
  const firstWords = (s: string) => s.trim().split(/\s+/).slice(0, words + 1).join(' ');
  const marker = `[?${ex.gap_chars}]`;
  return {
    ta: `${lastWords(ex.left.ta)} ${marker} ${firstWords(ex.right.ta)}`,
    iso: `${lastWords(ex.left.iso)} ${marker} ${firstWords(ex.right.iso)}`,
  };
}

const STEPS: { key: string; name: MessageKey; does: MessageKey; icon: ReactNode }[] = [
  { key: 'reader', name: 'pipe.reader', does: 'pipe.readerDo', icon: <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6z M12 9.5a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z" /> },
  { key: 'restorer', name: 'pipe.restorer', does: 'pipe.restorerDo', icon: <path d="M5 19 15 9M13 7l4 4M15 5l4 4-2 2-4-4zM4 20l2-1" /> },
  { key: 'decider', name: 'pipe.decider', does: 'pipe.deciderDo', icon: <path d="M12 3v6M12 9l-6 6M12 9l6 6M4 17h4v4H4zM16 17h4v4h-4z" /> },
  { key: 'interpreter', name: 'pipe.interpreter', does: 'pipe.interpreterDo', icon: <path d="M4 6h16M4 11h10M4 16h13M4 21h7" /> },
  { key: 'expert', name: 'pipe.expert', does: 'pipe.expertDo', icon: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21c1-4 4.5-6 8-6s7 2 8 6M16 11l2 2 4-4" /> },
];

/** Reader -> Restorer -> Strands Decider -> Interpreter -> expert review, each with one line and a real example. */
export function Pipeline({ ex = EXAMPLE }: { ex?: WorkedExample }) {
  const { t, lang } = useI18n();
  const top = ex.candidates.slice(0, 2);
  const snippet = exampleSnippet(ex);
  const examples: Record<string, ReactNode> = {
    reader: (
      <>
        <span className="pipe-ex-k">{t('pipe.exReader')}</span>
        <Bi ta={snippet.ta} iso={snippet.iso} taClass="script-chola" />
      </>
    ),
    restorer: (
      <>
        <span className="pipe-ex-k">{t('pipe.exRestorer')}</span>
        <span className="pipe-cands">
          {top.map((c) => (
            <span key={c.iso} className="pipe-cand">
              <Bi ta={c.ta} iso={c.iso} /> <span className="pipe-conf">{pctText(c.confidence)}</span>
            </span>
          ))}
        </span>
      </>
    ),
    decider: (
      <span className="pipe-ex-k pipe-verdict" data-testid="pipe-decider-example">
        {fmt(t('pipe.exDecider'), { c: pctText(top[0]?.confidence ?? 0), t: ex.threshold == null ? '—' : pctText(ex.threshold) })}
      </span>
    ),
    interpreter: (
      <>
        <Bi ta={ex.word.ta} iso={ex.word.iso} />
        <span className="pipe-ex-k">{fmt(t('pipe.exInterpreter'), { m: lang === 'ta' ? ex.word.ta_meaning : ex.word.en })}</span>
      </>
    ),
    expert: <span className="pipe-ex-k">{t('pipe.exExpert')}</span>,
  };
  return (
    <figure className="pipeline" data-testid="pipeline">
      <ol className="pipe-steps">
        {STEPS.map((s, i) => (
          <li key={s.key} className={`pipe-step pipe-${s.key}`} style={{ ['--i' as string]: i }} data-testid={`pipe-${s.key}`}>
            <span className="pipe-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">{s.icon}</svg>
            </span>
            <h3>{t(s.name)}</h3>
            <p className="pipe-does">{t(s.does)}</p>
            <div className="pipe-ex">{examples[s.key]}</div>
          </li>
        ))}
      </ol>
      <figcaption className="hint-text">
        {fmt(t('pipe.exampleFrom'), { title: lang === 'ta' ? ex.title_ta : ex.title_en, date: ex.recorded_on })} ·{' '}
        <a href={ex.url} target="_blank" rel="noreferrer">
          {t('q.edition')} ↗
        </a>{' '}
        · CC BY-SA 4.0
      </figcaption>
    </figure>
  );
}
