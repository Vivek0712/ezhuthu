import { useEffect, useState } from 'react';
import { Link, Navigate, useParams, useSearchParams } from 'react-router-dom';
import { ErrorNote, Skeleton } from '../components/Feedback';
import { DrillSession, LEVEL_KEYS } from '../components/practice/DrillSession';
import { TimedTrial } from '../components/practice/TimedTrial';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { loadAllBanks, useBank } from '../practice/banks';
import { fmt, newSeed } from '../practice/engine';
import type { BankKind, Item, Level } from '../practice/types';

const BANKS: BankKind[] = ['letters', 'words', 'gaps', 'formulas'];

function Head({ title, sub }: { title: string; sub?: string }) {
  const { t } = useI18n();
  return (
    <header className="page-head session-head">
      <p className="kicker">
        <Link to="/practice">← {t('prac.title')}</Link>
      </p>
      <h1>{title}</h1>
      {sub && <p className="lede">{sub}</p>}
    </header>
  );
}

/** /practice/:kind?level=N: one instant session; it starts as soon as the bank chunk is loaded. */
export function PracticeSessionPage() {
  const { t } = useI18n();
  const { kind } = useParams();
  const [params, setParams] = useSearchParams();
  const level = Math.min(3, Math.max(1, Number(params.get('level')) || 1)) as Level;
  const bank = BANKS.includes(kind as BankKind) ? (kind as BankKind) : null;
  const { items, error } = useBank(bank);
  const [seed, setSeed] = useState(newSeed);

  if (!bank) return <Navigate replace to="/practice" />;
  const title = t(`sess.${bank}.title` as MessageKey);
  return (
    <>
      <Head title={title} sub={`${fmt(t('prac.levelN'), { n: level })} · ${t(LEVEL_KEYS[bank][level - 1]!)}`} />
      <nav className="level-tabs" aria-label={t('prac.level')}>
        {[1, 2, 3].map((l) => (
          <button key={l} type="button" className={`chip-btn ${l === level ? 'on' : ''}`} aria-pressed={l === level} onClick={() => setParams({ level: String(l) })}>
            {fmt(t('prac.levelN'), { n: l })}
          </button>
        ))}
      </nav>
      {error != null ? (
        <ErrorNote error={error} onRetry={() => window.location.reload()} />
      ) : !items ? (
        <Skeleton lines={3} label={t('q.loading')} />
      ) : (
        <DrillSession key={`${bank}:${level}:${seed}`} kind={bank} level={level} items={items} seed={seed} onRestart={() => setSeed(newSeed())} />
      )}
    </>
  );
}

/** /practice/trial: the timed, mixed challenge. */
export function TrialPage() {
  const { t } = useI18n();
  const [banks, setBanks] = useState<Record<BankKind, Item[]> | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [seed, setSeed] = useState(newSeed);
  useEffect(() => {
    let live = true;
    loadAllBanks().then(
      (b) => live && setBanks(b),
      (e: unknown) => live && setError(e),
    );
    return () => {
      live = false;
    };
  }, []);
  return (
    <>
      <Head title={t('sess.trial.title')} />
      {error != null ? (
        <ErrorNote error={error} onRetry={() => window.location.reload()} />
      ) : !banks ? (
        <Skeleton lines={3} label={t('q.loading')} />
      ) : (
        <TimedTrial key={seed} banks={banks} seed={seed} onRestart={() => setSeed(newSeed())} />
      )}
    </>
  );
}
