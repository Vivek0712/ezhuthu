import { useMemo, useState, type FormEvent } from 'react';
import { api, type Gap, type RestoreResponse } from '../api/client';
import { ConfidenceMeter } from '../components/ConfidenceMeter';
import { Busy, ErrorNote } from '../components/Feedback';
import { useI18n } from '../i18n/I18nProvider';
import { gapContext, parseGaps } from '../lib/gaps';
import { safeHref } from '../lib/format';
import { SAMPLE_RESTORE_ISO, SAMPLE_RESTORE_TAMIL } from '../lib/samples';

type Script = 'iso15919' | 'tamil';

function CorrectionForm({ text, res, gap }: { text: string; res: RestoreResponse; gap: Gap }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [reading, setReading] = useState('');
  const [state, setState] = useState<'idle' | 'busy' | 'sent'>('idle');
  const [error, setError] = useState<unknown>(null);
  const chosen = gap.chosen !== null ? gap.candidates[gap.chosen] : undefined;

  async function send(body: { accepted_candidate?: string; corrected_text?: string }) {
    setState('busy');
    setError(null);
    try {
      const ctx = gapContext(text, gap.index);
      await api.correction({
        gap_ref: { trace_id: res.trace_id, gap_index: gap.index, left: ctx.left, right: ctx.right, gap_chars: gap.gap_chars },
        user: name.trim() || 'anonymous',
        ...body,
      });
      setState('sent');
    } catch (err) {
      setError(err);
      setState('idle');
    }
  }

  if (state === 'sent') return <p className="badge ok" role="status">{t('restore.sent')}</p>;
  return (
    <div className="grid" style={{ gap: 10 }}>
      <div className="row">
        {chosen && (
          <button className="btn btn-ghost btn-small" type="button" disabled={state === 'busy'} onClick={() => void send({ accepted_candidate: chosen.text })}>
            {t('restore.accept')}
          </button>
        )}
        <button className="btn btn-ghost btn-small" type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} data-testid={`suggest-${gap.index}`}>
          {t('restore.suggest')}
        </button>
      </div>
      {open && (
        <form
          className="grid grid-2"
          onSubmit={(e) => {
            e.preventDefault();
            if (reading.trim()) void send({ corrected_text: reading.trim() });
          }}
        >
          <label className="field">
            {t('restore.yourReading')}
            <input type="text" value={reading} onChange={(e) => setReading(e.target.value)} required data-testid={`reading-${gap.index}`} />
          </label>
          <label className="field">
            {t('restore.yourName')}
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} maxLength={64} />
          </label>
          <div className="row">
            <button className="btn btn-primary btn-small" type="submit" disabled={state === 'busy'} data-testid={`send-${gap.index}`}>
              {t('restore.send')}
            </button>
          </div>
        </form>
      )}
      {error != null && <ErrorNote error={error} />}
    </div>
  );
}

export function RestorePage() {
  const { t, lang } = useI18n();
  const [script, setScript] = useState<Script>(lang === 'ta' ? 'tamil' : 'iso15919');
  const [text, setText] = useState('');
  const [max, setMax] = useState(5);
  const [escalate, setEscalate] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<{ text: string; script: Script; data: RestoreResponse } | null>(null);
  const gapCount = useMemo(() => parseGaps(text).filter((s) => s.kind === 'gap').length, [text]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!gapCount) return;
    setBusy(true);
    setError(null);
    try {
      const data = await api.restore({ text, script, max_candidates: max, allow_escalation: escalate });
      setRes({ text, script, data });
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const display = (c: { text: string; text_tamil: string }) => (res?.script === 'tamil' || lang === 'ta' ? c.text_tamil : c.text);

  return (
    <>
      <header className="page-head">
        <h1>{t('restore.title')}</h1>
        <p className="lede">{t('restore.lede')}</p>
      </header>
      <form className="leaf grid" onSubmit={submit}>
        <label className="field">
          {t('restore.input')}
          <textarea value={text} onChange={(e) => setText(e.target.value)} lang={script === 'tamil' ? 'ta' : 'en'} data-testid="restore-input" />
        </label>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <span className={gapCount ? 'badge accent' : 'badge'} data-testid="gap-count">
            {gapCount} {t('restore.gapsFound')}
          </span>
          <button
            className="btn btn-ghost btn-small"
            type="button"
            onClick={() => setText(script === 'tamil' ? SAMPLE_RESTORE_TAMIL : SAMPLE_RESTORE_ISO)}
            data-testid="use-sample"
          >
            {t('restore.sample')}
          </button>
        </div>
        <div className="grid grid-3">
          <label className="field">
            {t('restore.script')}
            <select value={script} onChange={(e) => setScript(e.target.value as Script)}>
              <option value="tamil">{t('restore.script.tamil')}</option>
              <option value="iso15919">{t('restore.script.iso')}</option>
            </select>
          </label>
          <label className="field">
            {t('restore.maxCandidates')}
            <select value={max} onChange={(e) => setMax(Number(e.target.value))}>
              {[1, 3, 5, 10].map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="row" style={{ fontWeight: 600, alignSelf: 'end', minHeight: 44 }}>
            <input type="checkbox" checked={escalate} onChange={(e) => setEscalate(e.target.checked)} style={{ width: 20, height: 20 }} />
            {t('restore.escalation')}
          </label>
        </div>
        {text && !gapCount && <p className="note">{t('restore.noGaps')}</p>}
        <div className="row">
          <button className="btn btn-primary" type="submit" disabled={busy || !gapCount} data-testid="restore-submit">
            {t('restore.submit')}
          </button>
          {busy && <Busy />}
        </div>
        {error != null && <ErrorNote error={error} />}
      </form>

      {res && (
        <section style={{ marginTop: 28 }} className="grid" aria-live="polite" data-testid="restore-result">
          <h2>{t('restore.result')}</h2>
          <p className="restored" lang={res.script === 'tamil' ? 'ta' : undefined}>
            {parseGaps(res.text).map((s, i) => {
              if (s.kind === 'text') return <span key={i}>{s.text}</span>;
              const g = res.data.gaps.find((x) => x.index === s.index);
              const c = g && g.decision === 'fill' && g.chosen !== null ? g.candidates[g.chosen] : undefined;
              return c ? (
                <span key={i} className="fill" title={`${t('restore.gap')} ${s.index + 1}`}>
                  {display(c)}
                </span>
              ) : (
                <span key={i} className="unsure" title={t('restore.abstainTitle')}>
                  ?
                </span>
              );
            })}
          </p>
          <p className="hint-text">
            {t('restore.models')}: {res.data.models_used.join(', ')} · {t('restore.latency')}: {Math.round(res.data.latency_ms)} ms
          </p>
          {res.data.gaps.map((g) => (
            <article key={g.index} className="leaf gap-card" data-testid={`gap-${g.index}`}>
              <header>
                <h3 style={{ margin: 0 }}>
                  {t('restore.gap')} {g.index + 1}
                  {g.gap_chars ? ` · ~${g.gap_chars} ${t('restore.chars')}` : ''}
                </h3>
                <span className={g.decision === 'fill' ? 'badge ok' : 'badge'}>{g.decision}</span>
              </header>
              {g.decision === 'abstain' && (
                <div className="abstain" data-testid="abstain">
                  <h3>{t('restore.abstainTitle')}</h3>
                  <p style={{ margin: 0 }}>{t('restore.abstainBody')}</p>
                </div>
              )}
              {g.candidates.map((c, ci) => (
                <div key={ci} className={`cand ${g.chosen === ci && g.decision === 'fill' ? 'chosen' : ''}`}>
                  <div className="cand-top">
                    <span className="cand-text" lang={res.script === 'tamil' || lang === 'ta' ? 'ta' : undefined}>
                      {display(c)} <span className="iso">{res.script === 'tamil' || lang === 'ta' ? c.text : c.text_tamil}</span>
                    </span>
                    <span className="row" style={{ gap: 6 }}>
                      {g.chosen === ci && g.decision === 'fill' && <span className="badge ok">{t('restore.chosen')}</span>}
                      <span className="badge">{c.model}</span>
                    </span>
                  </div>
                  <ConfidenceMeter value={c.confidence} label={`${t('common.confidence')} ${display(c)}`} />
                  {c.ontology_hints.length > 0 && (
                    <div className="chips" aria-label={t('restore.hints')}>
                      {c.ontology_hints.map((h) => (
                        <span className="chip" key={h.id} title={h.id}>
                          {h.kind}: {h.label}
                        </span>
                      ))}
                    </div>
                  )}
                  {c.parallels.length > 0 && (
                    <details>
                      <summary>
                        {t('restore.parallels')} ({c.parallels.length})
                      </summary>
                      <ul className="parallels">
                        {c.parallels.map((p, pi) => {
                          const href = safeHref(p.url);
                          return (
                            <li key={pi}>
                              {href ? (
                                <a href={href} target="_blank" rel="noreferrer">
                                  {p.inscription_id} · {p.line_n}
                                </a>
                              ) : (
                                `${p.inscription_id} · ${p.line_n}`
                              )}{' '}
                              <span className="iso">{p.snippet}</span>
                            </li>
                          );
                        })}
                      </ul>
                    </details>
                  )}
                </div>
              ))}
              <CorrectionForm text={res.text} res={res.data} gap={g} />
            </article>
          ))}
          <p className="note">{t('restore.matchesNote')}</p>
        </section>
      )}
    </>
  );
}
