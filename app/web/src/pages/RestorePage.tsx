import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api, type Candidate, type Gap, type RestoreResponse } from '../api/client';
import { ConfidenceMeter } from '../components/ConfidenceMeter';
import { EditionReveal } from '../components/EditionReveal';
import { Busy, DharmaCredit, ErrorNote } from '../components/Feedback';
import { ExperimentalNote, ReadPanel, type Accepted, type Tab } from '../components/ReadPanel';
import { GappedText, Lacuna, SampleGallery } from '../components/SampleGallery';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { gapContext, parseGaps } from '../lib/gaps';
import { pct, plural, safeHref } from '../lib/format';
import { SAMPLE_RESTORE_TAMIL } from '../lib/samples';
import { isoPartsToTamil, isoToTamil, looksTamil, type IsoPart, type TamilPiece } from '../lib/script';
import { useRestoreSample, type Sample } from '../samples';

type Script = 'iso15919' | 'tamil';
type ScriptChoice = Script | 'auto';
type Result = { text: string; script: Script; data: RestoreResponse; sample?: Sample };
type T = (k: MessageKey) => string;

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

const chosenOf = (g: Gap): Candidate | undefined => (g.decision === 'fill' && g.chosen !== null ? g.candidates[g.chosen] : undefined);
const fillLabel = (c: Candidate) => `${c.text_tamil} (${c.text})`;

/** How long a gap is, in plain words. */
function gapLength(t: T, chars: number | null): string {
  return chars == null ? t('restore.aboutUnknown') : chars === 1 ? t('restore.about1') : t('restore.aboutN').replace('{n}', String(chars));
}

/** The one plain sentence a result leads with: what was missing, and what was done about it. */
function resultSummary(t: T, gaps: Gap[]): string {
  const n = gaps.length;
  const filled = gaps.filter((g) => chosenOf(g));
  const one = gaps[0];
  const missing =
    n === 1 && one
      ? one.gap_chars === 1
        ? t('sum.missing1')
        : one.gap_chars == null
          ? t('sum.missingUnknown')
          : t('sum.missingN').replace('{n}', String(one.gap_chars))
      : t('sum.missingPlaces').replace('{n}', String(n));
  let done: string;
  if (filled.length === n && n === 1) {
    const c = chosenOf(one!)!;
    done = t('sum.filledOne').replace('{fill}', fillLabel(c)).replace('{pct}', pct(c.confidence));
  } else if (filled.length === n) done = t('sum.filledAll').replace('{n}', String(n));
  else if (filled.length === 0) done = t(n === 1 ? 'sum.openOne' : 'sum.openAll');
  else done = t('sum.mixed').replace('{f}', String(filled.length)).replace('{o}', String(n - filled.length));
  return `${missing} ${done}`;
}

/**
 * The restored line in Tamil script (filled letters highlighted, open gaps boxed) and, when it can be known, the same
 * line in English letters. Tamil input keeps the reader's own letters; ISO input is converted in the browser
 * (lib/script.ts), so a highlight always covers whole Tamil letters.
 */
function restoredLine(res: Result): { tamil: TamilPiece[]; iso: IsoPart[] | null; isoPlain: string | null } {
  const fill = (index: number) => {
    const g = res.data.gaps.find((x) => x.index === index);
    return g ? chosenOf(g) : undefined;
  };
  const isoParts = (text: string): IsoPart[] =>
    parseGaps(text).map((s) => {
      if (s.kind === 'text') return { kind: 'text', iso: s.text };
      const c = fill(s.index);
      return c ? { kind: 'fill', iso: c.text, gap: s.index } : { kind: 'gap', raw: s.raw, gap: s.index };
    });
  if (res.script === 'iso15919') {
    const iso = isoParts(res.text);
    return { tamil: isoPartsToTamil(iso), iso, isoPlain: null };
  }
  const tamil: TamilPiece[] = parseGaps(res.text).map((s) => {
    if (s.kind === 'text') return { kind: 'text', ta: s.text };
    const c = fill(s.index);
    return c ? { kind: 'fill', ta: c.text_tamil, gap: s.index } : { kind: 'gap', raw: s.raw, gap: s.index };
  });
  if (res.sample) return { tamil, iso: isoParts(res.sample.text_iso), isoPlain: null };
  const plain = res.data.restored_text;
  return { tamil, iso: null, isoPlain: plain && !/[஀-௿]/.test(plain) ? plain : null };
}

function RestoredLine({ res }: { res: Result }) {
  const { t } = useI18n();
  const line = useMemo(() => restoredLine(res), [res]);
  const gapChars = (i: number) => res.data.gaps.find((g) => g.index === i)?.gap_chars ?? null;
  const fillSpan = (key: number, text: string, gap: number) => (
    <span key={key} className="fill" title={`${t('restore.gap')} ${gap + 1}`}>
      {text}
    </span>
  );
  const open = (key: number, raw: string, gap: number) => <Lacuna key={key} chars={gapChars(gap)} raw={raw} className="unsure" />;
  return (
    <div className="restored-box">
      <p className="restored restored-ta" lang="ta" data-testid="restored-tamil">
        {line.tamil.map((p, i) => (p.kind === 'text' ? <span key={i}>{p.ta}</span> : p.kind === 'fill' ? fillSpan(i, p.ta, p.gap) : open(i, p.raw, p.gap)))}
      </p>
      {(line.iso || line.isoPlain) && (
        <div className="restored-iso" data-testid="restored-iso">
          <span className="biscript-label">{t('restore.inEnglish')}</span>
          <p lang="ta-Latn">
            {line.iso
              ? line.iso.map((p, i) => (p.kind === 'text' ? <span key={i}>{p.iso}</span> : p.kind === 'fill' ? fillSpan(i, p.iso, p.gap) : open(i, p.raw, p.gap)))
              : line.isoPlain}
          </p>
        </div>
      )}
      <p className="restored-legend hint-text">
        <span className="fill">அ</span> {t('restore.legendFill')} · <Lacuna chars={1} raw="[?1]" className="unsure" /> {t('restore.legendOpen')}
      </p>
    </div>
  );
}

function CandidateCard({ c, used }: { c: Candidate; used: boolean }) {
  const { t } = useI18n();
  return (
    <div className={`cand ${used ? 'chosen' : ''}`}>
      <div className="cand-top">
        <span className="cand-text">
          <span lang="ta">{c.text_tamil}</span>{' '}
          <span className="iso" lang="ta-Latn">
            ({c.text})
          </span>
        </span>
        <span className="row" style={{ gap: 6 }}>
          {used && <span className="badge ok">{t('restore.chosen')}</span>}
          <span className="badge" data-testid="cand-source">
            {c.model === 'retrieval' ? t('restore.srcSimilar') : t('restore.srcAI')}
          </span>
        </span>
      </div>
      <ConfidenceMeter value={c.confidence} label={`${t('common.confidence')} ${c.text_tamil} (${c.text})`} />
      {c.ontology_hints.length > 0 && (
        <p className="cand-hints">
          <span className="hint-text" title={t('restore.hintsHelp')}>
            {t('restore.hints')}:
          </span>{' '}
          <span className="chips" style={{ display: 'inline-flex' }}>
            {c.ontology_hints.map((h) => (
              <span className="chip" key={h.id} title={h.kind}>
                {h.label}
              </span>
            ))}
          </span>
        </p>
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
  );
}

function GapCard({ g, res }: { g: Gap; res: Result }) {
  const { t } = useI18n();
  const chosen = chosenOf(g);
  return (
    <article className="leaf gap-card" data-testid={`gap-${g.index}`}>
      <header>
        <h3 style={{ margin: 0 }}>
          {t('restore.gap')} {g.index + 1} · {gapLength(t, g.gap_chars)}
        </h3>
        <span className={chosen ? 'badge ok' : 'badge unsure'}>{chosen ? t('restore.filled') : t('restore.leftOpen')}</span>
      </header>
      {chosen && (
        <div className="gap-fill" data-testid={`gap-fill-${g.index}`}>
          <p className="cand-text" style={{ margin: 0 }}>
            <span className="hint-text">{t('restore.filledWith')}:</span> <span lang="ta">{chosen.text_tamil}</span>{' '}
            <span className="iso" lang="ta-Latn">
              ({chosen.text})
            </span>
          </p>
          <ConfidenceMeter value={chosen.confidence} label={`${t('common.confidence')} ${fillLabel(chosen)}`} />
        </div>
      )}
      {g.decision === 'abstain' &&
        (res.sample?.group === 'masked' ? (
          // The editors did restore this gap, so "experts are unsure" would be untrue here.
          <div className="abstain" data-testid="abstain">
            <h3>{t('restore.abstainAskTitle')}</h3>
            <p style={{ margin: 0 }}>{t('restore.abstainAskBody')}</p>
          </div>
        ) : (
          <div className="abstain" data-testid="abstain">
            <h3 lang="ta">வல்லுநர்களுக்கும் உறுதியில்லை</h3>
            <p className="abstain-sub" lang="en">
              Experts are unsure
            </p>
            <p style={{ margin: 0 }}>{t('restore.abstainBody')}</p>
          </div>
        ))}
      {g.candidates.length > 0 && (
        <details className="cand-disclosure" data-testid={`options-${g.index}`}>
          <summary>
            {chosen ? t('restore.otherOptions') : t('restore.showCandidates')} ({g.candidates.length})
          </summary>
          <div className="grid" style={{ gap: 10, marginTop: 10 }}>
            {g.candidates.map((c, ci) => (
              <CandidateCard key={ci} c={c} used={!!chosen && g.chosen === ci} />
            ))}
          </div>
        </details>
      )}
      <CorrectionForm text={res.text} res={res.data} gap={g} />
    </article>
  );
}

/** "What happens when you press Restore": open until the first result, then folded away (one tap to reopen). */
function HowItWorks({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const { t } = useI18n();
  return (
    <details className="how leaf" open={open} onToggle={(e) => setOpen(e.currentTarget.open)} data-testid="restore-how">
      <summary>{t('how.title')}</summary>
      <ol className="how-steps">
        <li>{t('how.1')}</li>
        <li>{t('how.2')}</li>
        <li>{t('how.3')}</li>
        <li>{t('how.4')}</li>
      </ol>
      <p className="hint-text" style={{ margin: 0 }}>
        {t('restore.markHelp')}
      </p>
    </details>
  );
}

export function RestorePage() {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  // /restore?sample=<id> (the home gallery) starts the form with that DHARMA passage, in Tamil script.
  // The samples load on demand, so the passage arrives a moment after the first render: fill the form once per sample.
  const fromSample = useRestoreSample();
  // Upload is the primary input (user feedback: people rarely have the text to paste); typing is the third tab,
  // except when a gallery sample brings its own text.
  // /restore?tab=type (the home page's "Restore a line") opens on typing.
  const location = useLocation();
  const [tab, setTab] = useState<Tab>(fromSample || new URLSearchParams(location.search).get('tab') === 'type' ? 'type' : 'photo');
  // /restore#samples (the home page's "Try a sample inscription") lands on the sample gallery below the form.
  useEffect(() => {
    if (location.hash !== '#samples') return;
    const el = document.getElementById('samples');
    el?.scrollIntoView({ block: 'start' });
    el?.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
  }, [location.hash]);
  // "auto": the script follows what is in the box (Tamil letters or English letters); Advanced options can force it.
  const [scriptChoice, setScriptChoice] = useState<ScriptChoice>('auto');
  const [text, setText] = useState(fromSample?.text ?? '');
  const script: Script = scriptChoice === 'auto' ? (looksTamil(text) ? 'tamil' : 'iso15919') : scriptChoice;
  const [fromReader, setFromReader] = useState<Accepted['source'] | null>(null);
  const filledFrom = useRef<string | null>(fromSample?.sample.id ?? null);
  useEffect(() => {
    if (!fromSample || filledFrom.current === fromSample.sample.id) return;
    filledFrom.current = fromSample.sample.id;
    setScriptChoice('auto');
    setText(fromSample.text);
    setFromReader(null);
    setTab('type');
  }, [fromSample]);
  const [max, setMax] = useState(5);
  const [escalate, setEscalate] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [howOpen, setHowOpen] = useState(true);
  const resultRef = useRef<HTMLElement>(null);
  const gapCount = useMemo(() => parseGaps(text).filter((s) => s.kind === 'gap').length, [text]);
  const shownSample = fromSample && text === fromSample.text ? fromSample.sample : null;

  async function run(body: string, sc: Script) {
    setBusy(true);
    setError(null);
    try {
      const data = await api.restore({ text: body, script: sc, max_candidates: max, allow_escalation: escalate });
      // The edition reveal applies only to a gallery sample's own, unedited passage.
      const s = fromSample?.sample;
      const sample = s && (body === s.text_iso || body === s.text_tamil) ? s : undefined;
      setRes({ text: body, script: sc, data, sample });
      setHowOpen(false);
      requestAnimationFrame(() => resultRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }));
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!gapCount) return;
    await run(text, script);
  }

  function accept(a: Accepted) {
    setText(a.text);
    setScriptChoice('auto');
    setFromReader(a.source);
    setTab('type');
    void run(a.text, a.script);
  }

  // The other form of what is in the box: English letters under a sample's Tamil, Tamil script under typed ISO.
  const preview =
    text.trim() === ''
      ? null
      : script === 'iso15919'
        ? { label: t('restore.inTamil'), text: isoToTamil(text), lang: 'ta' }
        : shownSample
          ? { label: t('restore.inEnglish'), text: shownSample.text_iso, lang: 'ta-Latn' }
          : null;

  const typePanel = (
    <form className="grid" onSubmit={submit}>
      {fromReader === 'image' && <ExperimentalNote />}
      {shownSample && (
        <div className="sample-from" data-testid="restore-sample-source">
          <p style={{ margin: 0 }}>
            {t('samples.from')}: <strong>{lang === 'ta' ? shownSample.title_ta : shownSample.title_en}</strong> ·{' '}
            <a href={shownSample.dharma_url} target="_blank" rel="noreferrer">
              {t('credit.edition')} ↗
            </a>{' '}
            ·{' '}
            <a href={shownSample.licence_url} target="_blank" rel="noreferrer license">
              {shownSample.licence}
            </a>
          </p>
          <p style={{ margin: '4px 0 0' }} data-testid="restore-sample-about">
            <strong>{t('restore.sampleAbout')}:</strong> {lang === 'ta' ? shownSample.why_ta : shownSample.why_en}
          </p>
        </div>
      )}
      <label className="field">
        {t('restore.input')}
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          lang={script === 'tamil' ? 'ta' : 'ta-Latn'}
          rows={Math.min(8, Math.max(3, text.split('\n').length + 1))}
          aria-describedby="restore-mark-help"
          data-testid="restore-input"
        />
      </label>
      <p id="restore-mark-help" className="hint-text" style={{ margin: 0 }}>
        {t('restore.markHelp')}
      </p>
      {preview && (
        <div className="input-preview" data-testid="input-preview">
          <span className="biscript-label">{preview.label}</span>
          <p>
            <GappedText text={preview.text} lang={preview.lang} />
          </p>
        </div>
      )}
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className={gapCount ? 'badge accent' : 'badge'} data-testid="gap-count">
          {gapCount} {t(plural(gapCount, 'restore.gapFound', 'restore.gapsFound'))}
        </span>
        <button
          className="btn btn-ghost btn-small"
          type="button"
          onClick={() => {
            setText(SAMPLE_RESTORE_TAMIL);
            setScriptChoice('auto');
            setFromReader(null);
          }}
          data-testid="use-sample"
        >
          {t('restore.sample')}
        </button>
      </div>
      <details className="advanced" data-testid="restore-advanced">
        <summary>{t('restore.advanced')}</summary>
        <div className="grid grid-3" style={{ marginTop: 10 }}>
          <label className="field">
            {t('restore.script')}
            <select value={scriptChoice} onChange={(e) => setScriptChoice(e.target.value as ScriptChoice)} data-testid="restore-script">
              <option value="auto">
                {t('restore.script.auto')} ({script === 'tamil' ? t('restore.script.tamil') : t('restore.script.iso')})
              </option>
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
      </details>
      {text && !gapCount && <p className="note">{t('restore.noGaps')}</p>}
      <div className="row">
        <button className="btn btn-primary" type="submit" disabled={busy || !gapCount} data-testid="restore-submit">
          {t('restore.submit')}
        </button>
        {busy && <Busy />}
      </div>
      {error != null && <ErrorNote error={error} />}
    </form>
  );

  return (
    <>
      <header className="page-head">
        <h1>{t('restore.title')}</h1>
        <p className="lede">{t('restore.lede')}</p>
      </header>
      <HowItWorks open={howOpen} setOpen={setHowOpen} />
      <ReadPanel
        tab={tab}
        setTab={setTab}
        onAccept={accept}
        onLearn={(body) => navigate('/practice', { state: { text: body } })}
        typePanel={typePanel}
      />

      {res && (
        <section ref={resultRef} style={{ marginTop: 28 }} className="grid" aria-live="polite" data-testid="restore-result">
          <h2>{t('restore.result')}</h2>
          <p className="restore-summary" data-testid="restore-summary">
            {resultSummary(t, res.data.gaps)}
          </p>
          <RestoredLine res={res} />
          {res.sample && <EditionReveal sample={res.sample} data={res.data} />}
          {res.data.gaps.map((g) => (
            <GapCard key={g.index} g={g} res={res} />
          ))}
          <p className="note">{t('restore.matchesNote')}</p>
          <details className="tech" data-testid="restore-tech">
            <summary>{t('restore.tech')}</summary>
            <p className="hint-text">
              {t('restore.models')}: {res.data.models_used.join(', ')} · {t('restore.latency')}: {Math.round(res.data.latency_ms)} ms · trace{' '}
              {res.data.trace_id}
            </p>
          </details>
          <DharmaCredit testId="restore-credit" />
        </section>
      )}
      {/* The try-it gallery lives here (it was on the home page, where its 13 cards pushed everything else down). */}
      <SampleGallery />
    </>
  );
}
