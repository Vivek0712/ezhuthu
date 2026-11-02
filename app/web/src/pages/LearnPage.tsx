import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Link, useLocation, useSearchParams } from 'react-router-dom';
import { api, type AnswerResponse, type LessonResponse, type Level } from '../api/client';
import { Busy, CC_BY_SA, ErrorNote } from '../components/Feedback';
import { GlyphTile } from '../components/GlyphTile';
import { LevelPicker } from '../components/LevelPicker';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { isLevel, levelInfo } from '../lib/levels';
import { sampleById, sampleByInscription, useSamples } from '../samples';
import { isDharmaUrl, safeHref } from '../lib/format';
import { LEARN_TEXT_LIMIT } from '../lib/learn';
import { setSessionId } from '../lib/session';

export function LearnPage() {
  const { t, lang, pick } = useI18n();
  // "Practise with this" from the home gallery: /practice?inscription=<id>&level=L3&sample=<id> starts that lesson.
  const [params] = useSearchParams();
  const linkedInscription = params.get('inscription')?.trim() || null;
  const linkedSampleId = params.get('sample');
  const samples = useSamples(linkedSampleId != null || linkedInscription != null);
  const linkedSample = sampleById(samples, linkedSampleId) ?? sampleByInscription(samples, linkedInscription);
  const [level, setLevel] = useState<Level>(() => {
    const l = params.get('level');
    return isLevel(l) ? l : 'L2';
  });
  // Restore -> Learn hand-off: a reading from a photo or file arrives as navigation state.
  const location = useLocation();
  const handed = (location.state as { text?: unknown } | null)?.text;
  const [ownText, setOwnText] = useState(typeof handed === 'string' ? handed.slice(0, LEARN_TEXT_LIMIT) : '');
  const handedCut = typeof handed === 'string' && handed.length > LEARN_TEXT_LIMIT;
  const [lesson, setLesson] = useState<LessonResponse | null>(null);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState('');
  const [result, setResult] = useState<AnswerResponse | null>(null);
  /** Set once the tutor team's explanation arrives as context_update on /api/answer. */
  const [explanationUpdated, setExplanationUpdated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function start(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.lesson({
        level,
        lang,
        ...(ownText.trim() ? { text: ownText.trim() } : linkedInscription ? { inscription_id: linkedInscription } : {}),
      });
      setLesson(res);
      setSessionId(res.session_id);
      setIdx(0);
      setResult(null);
      setAnswer('');
      setExplanationUpdated(false);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  // Start the linked lesson once on arrival (the ref survives React's dev double-invoke of effects).
  const autoStarted = useRef(false);
  useEffect(() => {
    if (!linkedInscription || autoStarted.current) return;
    autoStarted.current = true;
    void start();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once for the linked inscription
  }, [linkedInscription]);

  async function check(e: FormEvent) {
    e.preventDefault();
    if (!lesson || !answer.trim()) return;
    const item = lesson.items[idx]!;
    setBusy(true);
    setError(null);
    try {
      const res = await api.answer({ session_id: lesson.session_id, item_id: item.item_id, answer: answer.trim() });
      setResult(res);
      const update = res.context_update;
      if (update?.explain_ta || update?.explain_en) {
        // The async lesson explanation finished: it replaces the template text, keeping the lesson's facts.
        setLesson((l) =>
          l && l.session_id === lesson.session_id
            ? {
                ...l,
                context: {
                  ...l.context,
                  explain_ta: update.explain_ta || l.context.explain_ta,
                  explain_en: update.explain_en || l.context.explain_en,
                  explained_by: update.explained_by ?? 'tutor_team',
                  explanation_status: update.explanation_status ?? 'done',
                },
              }
            : l,
        );
        setExplanationUpdated(true);
      }
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
          {linkedSample && (
            <p className="sample-from" data-testid="learn-sample-source">
              {t('samples.from')}: <strong>{lang === 'ta' ? linkedSample.title_ta : linkedSample.title_en}</strong> ·{' '}
              <a href={linkedSample.dharma_url} target="_blank" rel="noreferrer">
                {t('credit.edition')} ↗
              </a>
            </p>
          )}
          <h2>{t('learn.pickLevel')}</h2>
          <LevelPicker value={level} onChange={setLevel} />
          <p className="note">{lang === 'ta' ? levelInfo(level).noteTa : levelInfo(level).noteEn}</p>
          <label className="field" style={{ margin: '18px 0' }}>
            {t('learn.ownText')}
            <span className="hint-text">{t('learn.ownTextHint')}</span>
            <textarea value={ownText} onChange={(e) => setOwnText(e.target.value)} rows={2} style={{ minHeight: 70 }} maxLength={LEARN_TEXT_LIMIT} />
          </label>
          {handedCut && (
            <p className="note" role="status" data-testid="learn-text-cut">
              {t('learn.textCut')}
            </p>
          )}
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
  // A learner's own text has no source. DHARMA editions (TEI under github.com/erc-dharma, or the dharmalekha.info
  // reader) are labelled as such and carry CC BY-SA 4.0 even if the API omits the licence; for any other source the
  // app states only the licence the API sent, and none when it sent none.
  const sourceHref = safeHref(insc.dharmalekha_url) ?? safeHref(insc.source_url);
  const fromDharma = isDharmaUrl(sourceHref);
  const licence = insc.licence?.trim() || (fromDharma ? 'CC BY-SA 4.0' : null);
  const licenceIsCcBySa = licence != null && /^CC BY-SA 4\.0$/i.test(licence);

  return (
    <>
      <header className="page-head">
        <p className="kicker">
          {levelInfo(item.script_level).id} · {lang === 'ta' ? levelInfo(item.script_level).nameTa : levelInfo(item.script_level).nameEn}
        </p>
        <h1>{insc.title}</h1>
        <div className="source-card" data-testid="lesson-source">
          <p className="source-facts">{[ctx.ruler ?? insc.ruler, insc.dynasty, insc.approx_date].filter(Boolean).join(' · ')}</p>
          {sourceHref ? (
            <p className="source-line">
              {t('common.source')}:{' '}
              <a href={sourceHref} target="_blank" rel="noreferrer">
                {fromDharma ? t('credit.edition') : new URL(sourceHref).hostname} ↗
              </a>
              {licence ? (
                <>
                  {' '}
                  ·{' '}
                  {licenceIsCcBySa ? (
                    <a href={CC_BY_SA} target="_blank" rel="noreferrer" data-testid="lesson-licence">
                      {licence}
                    </a>
                  ) : (
                    <span data-testid="lesson-licence">{licence}</span>
                  )}
                </>
              ) : null}
            </p>
          ) : null}
        </div>
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
              <GlyphTile key={item.item_id} item={item} label={pick(item.prompt_ta, item.prompt_en)} />
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
                  <div className={`feedback ${result.correct ? 'ok' : result.next_action === 'hint' ? 'hint' : 'no'}`} data-testid="feedback">
                    <strong lang="ta">
                      <span className="feedback-mark" aria-hidden="true">
                        {result.correct ? '✓' : result.next_action === 'hint' ? '?' : '·'}
                      </span>{' '}
                      {result.feedback_ta}
                    </strong>
                    <span className="visually-hidden">{t(result.correct ? 'learn.correct' : 'learn.notYet')}</span>
                    {result.feedback_en && (
                      <span className="sub" lang="en">
                        {result.feedback_en}
                      </span>
                    )}
                    {result.hint_ta && (
                      <p style={{ margin: '8px 0 0' }} lang="ta">
                        <span className="badge">{t('learn.hint')}</span> {result.hint_ta}
                      </p>
                    )}
                    <p className="sub decision" style={{ margin: '8px 0 0' }} data-testid="decision">
                      {t('learn.deciderSaid')}: {t(`learn.action.${result.next_action}` as MessageKey)} ·{' '}
                      {result.decider_confidence == null ? (
                        <span data-testid="decided-by-rules">{t('learn.decidedByRules')}</span>
                      ) : (
                        <>
                          {t('common.confidence')} {Math.round(result.decider_confidence * 100)}%
                        </>
                      )}
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
          <p data-testid="explanation" lang={lang}>
            {pick(ctx.explain_ta, ctx.explain_en)}
          </p>
          {ctx.explanation_status === 'pending' && !explanationUpdated && (
            <p className="note" role="status" data-testid="explanation-pending">
              {t('learn.explanationPending')}
            </p>
          )}
          {explanationUpdated && (
            <p className="chip chip-ok" role="status" data-testid="explanation-updated">
              {t('learn.explanationUpdated')}
            </p>
          )}
          {/* The restored text contains the answer to the current item: show it only once that item is resolved. */}
          {(done || result?.next_action === 'advance') && (
            <div data-testid="restored-text">
              <h3>{t('learn.restoredText')}</h3>
              <p className="inscription-line script-chola" lang="ta">
                {insc.restored_text_tamil}
              </p>
              <p className="iso">{insc.restored_text}</p>
            </div>
          )}
        </aside>
      </div>
    </>
  );
}
