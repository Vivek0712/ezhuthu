import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../../i18n/I18nProvider';
import type { MessageKey } from '../../i18n/strings';
import { BANK_SIZES } from '../../practice/banks';
import { fmt, pctText } from '../../practice/engine';
import { loadProgress, onProgress, type Progress } from '../../practice/progress';
import type { BankKind, SessionKind } from '../../practice/types';
import { LEVEL_KEYS } from './DrillSession';

export function useProgress(): Progress {
  const [p, setP] = useState(loadProgress);
  useEffect(() => onProgress(() => setP(loadProgress())), []);
  return p;
}

interface Card {
  kind: SessionKind;
  emblem: string;
  emblemClass: string;
}

// The emblem is a short form from the session: the Tamil-Brahmi ka, yā (yāṇṭu), a lost-letter mark, śrī.
const CARDS: Card[] = [
  { kind: 'letters', emblem: '𑀓', emblemClass: 'script-brahmi' },
  { kind: 'words', emblem: 'யா', emblemClass: 'script-chola' },
  { kind: 'gaps', emblem: '[?]', emblemClass: '' },
  { kind: 'formulas', emblem: 'ஶ்ரீ', emblemClass: 'script-chola' },
  { kind: 'trial', emblem: '10', emblemClass: '' },
  { kind: 'guided', emblem: 'AI', emblemClass: '' },
];
const BANKS: BankKind[] = ['letters', 'words', 'gaps', 'formulas'];

function isBank(k: SessionKind): k is BankKind {
  return (BANKS as string[]).includes(k);
}

/**
 * The practice sessions as cards. `full` (the hub) lists every level with what it covers; the compact form (home)
 * starts level 1 in one tap.
 */
export function SessionCards({ full = false }: { full?: boolean }) {
  const { t } = useI18n();
  const progress = useProgress();
  return (
    <ul className={`session-grid ${full ? 'session-grid-full' : ''}`} data-testid="session-cards">
      {CARDS.map(({ kind, emblem, emblemClass }) => {
        const s = progress.kinds[kind];
        const href = kind === 'guided' ? '/practice/guided' : kind === 'trial' ? '/practice/trial' : `/practice/${kind}?level=1`;
        const title = t(`sess.${kind}.title` as MessageKey);
        const stat =
          kind === 'trial' && progress.trial.best
            ? fmt(t('prac.best'), { p: `${progress.trial.best.right}/${progress.trial.best.total}` })
            : s && s.best !== null
              ? `${fmt(t('prac.best'), { p: pctText(s.best) })} · ${fmt(t('prac.played'), { n: s.sessions })}`
              : t('prac.new');
        return (
          <li key={kind} className={`session-card session-${kind}`} data-testid={`session-card-${kind}`}>
            <span className={`session-emblem ${emblemClass}`} aria-hidden="true" lang={emblemClass ? 'ta' : undefined}>
              {emblem}
            </span>
            <div className="session-body">
              <h3>
                <Link to={href} className="session-link" data-testid={`start-${kind}`}>
                  {title}
                </Link>
                {kind === 'guided' && <span className="badge accent">{t('sess.guided.badge')}</span>}
              </h3>
              <p>{t(`sess.${kind}.desc` as MessageKey)}</p>
              <p className="session-meta">
                <span>{kind === 'guided' ? t('sess.guided.badge') : t('prac.instant')}</span>
                {isBank(kind) && <span>{fmt(t('prac.bank'), { n: Object.values(BANK_SIZES[kind]).reduce((a, b) => a + b, 0) })}</span>}
                <span data-testid={`stat-${kind}`}>{stat}</span>
              </p>
              {full && isBank(kind) && (
                <div className="session-levels" role="group" aria-label={`${title}: ${t('prac.level')}`}>
                  {LEVEL_KEYS[kind].map((k, i) => (
                    <Link key={k} className="level-pill" to={`/practice/${kind}?level=${i + 1}`} data-testid={`start-${kind}-${i + 1}`}>
                      <strong>{fmt(t('prac.levelN'), { n: i + 1 })}</strong>
                      <span>{t(k)}</span>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </li>
        );
      })}
    </ul>
  );
}
