import { useRef, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api, type AnswerResponse, type LessonResponse, type Level } from '../api/client';
import { Busy, ErrorNote } from '../components/Feedback';
import { GlyphTile } from '../components/GlyphTile';
import { LevelPicker } from '../components/LevelPicker';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { levelInfo } from '../lib/levels';
import { safeHref } from '../lib/format';
import { setSessionId } from '../lib/session';

export function LearnPage() {
  const { t, lang, pick } = useI18n();
  const [level, setLevel] = useState<Level>('L2');
  const [ownText, setOwnText] = useState('');
  const [lesson, setLesson] = useState<LessonResponse | null>(null);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<AnswerResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function start(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.lesson({ level, lang, ...(ownText.trim() ? { text: ownText.trim() } : {}) });
      setLesson(res);
      setSessionId(res.session_id);
      setIdx(0);
      setResult(null);
      setAnswer('');
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function check(e: FormEvent) {
    e.preventDefault();
    if (!lesson || !answer.trim()) return;
    const item = lesson.items[idx]!;
    setBusy(true);
    setError(null);
    try {
      const res = await api.answer({ session_id: lesson.session_id, item_id: item.item_id, answer: answer.trim() });
      setResult(res);
      if (res.next_action !== 'advance') {
        setAnswer('');
        inputRef.current?.focus();
      }
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  function next() {
    setIdx((i) => i + 1);
    setResult(null);
    setAnswer('');
    setTimeout(() => inputRef.current?.focus(), 0);
  }

  if (!lesson)
    return (
      <>
        <header className="page-head">
          <h1>{t('learn.title')}</h1>
          <p className="lede">{t('learn.lede')}</p>
        </header>
        <form onSubmit={start}>
          <h2>{t('learn.pickLevel')}</h2>
          <LevelPicker value={level} onChange={setLevel} />
          <p className="note">{lang === 'ta' ? levelInfo(level).noteTa : levelInfo(level).noteEn}</p>
          <label className="field" style={{ margin: '18px 0' }}>
            {t('learn.ownText')}
            <span className="hint-text">{t('learn.ownTextHint')}</span>
            <textarea value={ownText} onChange={(e) => setOwnText(e.target.value)} rows={2} style={{ minHeight: 70 }} />
          </label>
          <div className="row">
            <button className="btn btn-primary" type="submit" disabled={busy} data-testid="start-lesson">
              {t('learn.start')}
            </button>
            {busy && <Busy />}
          </div>
          {error != null && <ErrorNote error={error} onRetry={() => void start()} />}
        </form>
      </>
    );

  const done = idx >= lesson.items.length;
  const item = lesson.items[Math.min(idx, lesson.items.length - 1)]!;
  const ctx = lesson.context;
  const insc = lesson.inscription;
  const source = safeHref(insc.source_url);

  return (
    <>
      <header className="page-head">
        <p className="kicker">
          {levelInfo(item.script_level).id} · {lang === 'ta' ? levelInfo(item.script_level).nameTa : levelInfo(item.script_level).nameEn}
        </p>
        <h1>{insc.title}</h1>
        <p className="lede">
          {[insc.dynasty, insc.approx_date].filter(Boolean).join(' · ')}
          {source && (
            <>
              {' · '}
              <a href={source} target="_blank" rel="noreferrer">
                {t('common.source')}
              </a>
            </>
          )}
        </p>
      </header>
      <div className="practice">
        <section aria-live="polite">
          {done ? (
            <div className="leaf holes" data-testid="lesson-done" style={{ paddingTop: 40 }}>
              <h2>{t('learn.done')}</h2>
              <p>{t('learn.doneBody')}</p>
              <div className="row">
                <Link className="btn btn-primary" to="/progress">
                  {t('learn.seeProgress')}
                </Link>
                <button className="btn btn-ghost" type="button" onClick={() => setLesson(null)}>
                  {t('learn.another')}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="progress-dots" aria-hidden="true">
                {lesson.items.map((it, i) => (
                  <i key={it.item_id} className={i < idx ? 'done' : i === idx ? 'now' : undefined} />
                ))}
              </div>
              <p className="row" style={{ justifyContent: 'space-between' }}>
                <span className="badge accent">{t(`learn.type.${item.type}` as MessageKey)}</span>
                <span data-testid="item-counter">
                  {t('learn.item')} {idx + 1} {t('learn.of')} {lesson.items.length}
                </span>
              </p>
              <h2>{pick(item.prompt_ta, item.prompt_en)}</h2>
              <GlyphTile item={item} label={pick(item.prompt_ta, item.prompt_en)} />
              <form onSubmit={check} style={{ marginTop: 16 }} className="grid">
                <label className="field">
                  {t('learn.answerLabel')}
                  <span className="hint-text">{t('learn.answerHint')}</span>
                  <input
                    ref={inputRef}
                    className="answer-input"
                    type="text"
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    autoComplete="off"
                    autoCapitalize="off"
                    spellCheck={false}
                    lang="ta"
                    disabled={result?.next_action === 'advance'}
                    data-testid="answer-input"
                  />
                </label>
                {result && (
                  <div className={`feedback ${result.correct ? 'ok' : 'no'}`} data-testid="feedback">
                    <strong lang="ta">{result.feedback_ta}</strong>
                    {lang === 'en' && <span className="sub">{result.feedback_en}</span>}
                    {result.hint_ta && (
                      <p style={{ margin: '8px 0 0' }} lang="ta">
                        <span className="badge">{t('learn.hint')}</span> {result.hint_ta}
                      </p>
                    )}
                    <p className="sub" style={{ margin: '8px 0 0' }}>
                      {t('learn.deciderSaid')}: {t(`learn.action.${result.next_action}` as MessageKey)} ·{' '}
                      {t('common.confidence')} {Math.round(result.decider_confidence * 100)}%
                    </p>
                  </div>
                )}
                <div className="row row-end">
                  {busy && <Busy />}
                  {result?.next_action === 'advance' ? (
                    <button className="btn btn-primary" type="button" onClick={next} data-testid="next-item" autoFocus>
                      {t('learn.next')}
                    </button>
                  ) : (
                    <button className="btn btn-primary" type="submit" disabled={busy || !answer.trim()} data-testid="check-answer">
                      {t('learn.check')}
                    </button>
                  )}
                </div>
                {error != null && <ErrorNote error={error} />}
              </form>
            </>
          )}
        </section>
        <aside className="leaf holes context" style={{ paddingTop: 40 }} data-testid="lesson-context">
          <h2>{t('learn.context')}</h2>
          <dl>
            {ctx.ruler && (
              <>
                <dt>{t('learn.ruler')}</dt>
                <dd>{ctx.ruler}</dd>
              </>
            )}
            {ctx.temple && (
              <>
                <dt>{t('learn.temple')}</dt>
                <dd>{ctx.temple}</dd>
              </>
            )}
            {ctx.grant && (
              <>
                <dt>{t('learn.grant')}</dt>
                <dd>{ctx.grant}</dd>
              </>
            )}
          </dl>
          <p>{pick(ctx.explain_ta, ctx.explain_en)}</p>
          <h3>{t('learn.restoredText')}</h3>
          <p className="inscription-line script-chola" lang="ta">
            {insc.restored_text_tamil}
          </p>
          <p className="iso">{insc.restored_text}</p>
        </aside>
      </div>
    </>
  );
}
