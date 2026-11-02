import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, type PracticeItem, type ProgressResponse } from '../api/client';
import { Busy, EmptyState, ErrorNote, Skeleton } from '../components/Feedback';
import { GlyphTile } from '../components/GlyphTile';
import { useI18n } from '../i18n/I18nProvider';
import { pct, signedPct } from '../lib/format';
import { LEVELS } from '../lib/levels';
import { getSessionId } from '../lib/session';

type Phase = 'pre' | 'post';

function Assessment({ sessionId, phase, onDone }: { sessionId: string; phase: Phase; onDone: () => void }) {
  const { t, pick } = useI18n();
  const [items, setItems] = useState<PracticeItem[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState('');
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    api
      .assessment({ session_id: sessionId, phase })
      .then((r) => live && setItems(r.items))
      .catch((e: unknown) => live && setError(e));
    return () => {
      live = false;
    };
  }, [sessionId, phase]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!items) return;
    setBusy(true);
    try {
      // Assessment answers are graded but feedback is withheld so the score reflects unaided reading.
      await api.answer({ session_id: sessionId, item_id: items[idx]!.item_id, answer: answer.trim() || '-' });
      setAnswer('');
      if (idx + 1 >= items.length) onDone();
      else setIdx(idx + 1);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (error != null) return <ErrorNote error={error} />;
  if (!items) return <Skeleton lines={3} />;
  const item = items[idx]!;
  return (
    <section className="leaf holes" style={{ paddingTop: 40 }} data-testid={`assessment-${phase}`}>
      <p className="row" style={{ justifyContent: 'space-between' }}>
        <span className="badge accent">{phase === 'pre' ? t('progress.pre') : t('progress.post')}</span>
        <span data-testid="assessment-counter">
          {idx + 1} / {items.length}
        </span>
      </p>
      <h2>{pick(item.prompt_ta, item.prompt_en)}</h2>
      <GlyphTile key={item.item_id} item={item} label={pick(item.prompt_ta, item.prompt_en)} />
      <form onSubmit={submit} className="grid" style={{ marginTop: 16 }}>
        <label className="field">
          {t('learn.answerLabel')}
          <input className="answer-input" type="text" value={answer} onChange={(e) => setAnswer(e.target.value)} autoComplete="off" lang="ta" autoFocus data-testid="assessment-input" />
        </label>
        <div className="row row-end">
          {busy && <Busy />}
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="assessment-next">
            {idx + 1 >= items.length ? t('progress.finish') : t('learn.next')}
          </button>
        </div>
      </form>
    </section>
  );
}

export function ProgressPage() {
  const { t, lang } = useI18n();
  const sessionId = getSessionId();
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [phase, setPhase] = useState<Phase | null>(null);

  const load = useCallback(() => {
    if (!sessionId) return;
    setError(null);
    api.progress(sessionId).then(setProgress, setError);
  }, [sessionId]);
  useEffect(load, [load]);

  if (!sessionId)
    return (
      <>
        <header className="page-head">
          <h1>{t('progress.title')}</h1>
          <p className="lede">{t('progress.lede')}</p>
        </header>
        <EmptyState
          title="progress.noSession"
          testId="no-session"
          action={
            <Link className="btn btn-primary" to="/learn">
              {t('home.ctaLearn')}
            </Link>
          }
        />
      </>
    );

  const max = Math.max(1, ...Object.values(progress?.letters_correct_by_level ?? {}));
  return (
    <>
      <header className="page-head">
        <h1>{t('progress.title')}</h1>
        <p className="lede">{t('progress.lede')}</p>
      </header>
      {error != null && <ErrorNote error={error} onRetry={load} />}
      {phase ? (
        <Assessment
          sessionId={sessionId}
          phase={phase}
          onDone={() => {
            setPhase(null);
            load();
          }}
        />
      ) : !progress ? (
        error == null && <Skeleton lines={4} />
      ) : (
        <div className="grid">
          <div className="stats" data-testid="scores">
            <div className="stat">
              <div className="k">{t('progress.pre')}</div>
              <div className="v" data-testid="pre-score">
                {progress.pre_score === null ? <small className="hint-text">{t('progress.notYet')}</small> : pct(progress.pre_score)}
              </div>
            </div>
            <div className="stat">
              <div className="k">{t('progress.post')}</div>
              <div className="v" data-testid="post-score">
                {progress.post_score === null ? <small className="hint-text">{t('progress.notYet')}</small> : pct(progress.post_score)}
              </div>
            </div>
            <div className="stat">
              <div className="k">{t('progress.gain')}</div>
              <div className="v gain" data-testid="gain">
                {signedPct(progress.gain)}
              </div>
            </div>
            <div className="stat">
              <div className="k">{t('progress.median')}</div>
              <div className="v">
                {progress.median_seconds_per_letter === null ? '—' : `${progress.median_seconds_per_letter.toFixed(1)}${t('progress.seconds')}`}
              </div>
            </div>
          </div>
          <div className="row">
            <button className="btn btn-primary" type="button" onClick={() => setPhase('pre')} data-testid="take-pre">
              {t('progress.takePre')}
            </button>
            <button className="btn btn-ghost" type="button" onClick={() => setPhase('post')} data-testid="take-post">
              {t('progress.takePost')}
            </button>
          </div>
          <section className="leaf">
            <h2>{t('progress.byLevel')}</h2>
            <div className="bars">
              {LEVELS.map((l) => {
                const v = progress.letters_correct_by_level[l.id] ?? 0;
                return (
                  <div className="bar-row" key={l.id}>
                    <span>
                      {l.id} · {lang === 'ta' ? l.nameTa : l.nameEn}
                    </span>
                    <div className="meter" aria-hidden="true">
                      <span style={{ width: `${(v / max) * 100}%` }} />
                    </div>
                    <span>{v}</span>
                  </div>
                );
              })}
            </div>
          </section>
        </div>
      )}
    </>
  );
}
