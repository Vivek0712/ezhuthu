import { useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from 'react';
import { ApiError, api, type ReadResponse } from '../api/client';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { countGaps } from '../lib/gaps';
import {
  ACCEPT_IMAGES,
  ACCEPT_TEXT,
  ImagePrepError,
  looksLikeText,
  preparePhoto,
  readTextFile,
  type PreparedPhoto,
} from '../lib/imagePrep';
import { READ_SAMPLES, type ReadSample } from '../lib/readSamples';
import { safeHref } from '../lib/format';
import { LEARN_TEXT_LIMIT } from '../lib/learn';
import { ConfidenceMeter } from './ConfidenceMeter';
import { TrySampleImage } from './TrySampleImage';
import { ErrorNote } from './Feedback';
import '../styles/read.css';

export type Tab = 'photo' | 'file' | 'type';
type Script = 'iso15919' | 'tamil';
type Phase = 'idle' | 'preparing' | 'reading' | 'review';
export const MAX_RESTORE_GAPS = 5;

interface EditLine {
  n: string;
  iso: string;
  tamil: string;
  value: string;
  include: boolean;
  confidence: number | null;
  edited: boolean;
}

/** What the restore form receives when the learner accepts a reading. */
export interface Accepted {
  text: string;
  script: Script;
  source: ReadResponse['source'];
}

function errorKey(err: unknown): MessageKey | null {
  if (err instanceof ImagePrepError) return `read.err.${err.kind}` as MessageKey;
  if (err instanceof ApiError) {
    if (err.code === 'reader_unavailable' || err.status === 503) return 'read.err.unavailable';
    if (err.code === 'too_large' || err.status === 413) return 'read.err.too_large';
    if (err.code === 'unsupported_format' || err.status === 415) return 'read.err.unsupported';
    if (err.code === 'bad_image') return 'read.err.bad_image';
    if (err.code === 'no_text') return 'read.err.no_text';
    if (err.code === 'reread_token_invalid') return 'read.err.reread';
  }
  return null;
}

type Warning = NonNullable<ReadResponse['warning_codes']>[number];

/** Server warnings in the learner's language: codes from warning_codes, English text only as a fallback. */
export function warningText(w: Warning, res: ReadResponse, t: (k: MessageKey) => string, lang: string): string {
  const key = `read.warn.${w.code}` as MessageKey;
  let s = t(key);
  const params = (w.params ?? {}) as Record<string, unknown>;
  if (w.code === 'low_reliability_script') {
    const g = res.script_guess;
    params.script = g && g.script === params.script ? (lang === 'ta' ? g.label_ta : g.label_en) : params.script;
  }
  for (const [k, v] of Object.entries(params)) s = s.replace(`{${k}}`, String(v));
  return s;
}

function ReadError({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useI18n();
  const key = errorKey(error);
  if (!key) return <ErrorNote error={error} onRetry={onRetry} />;
  return (
    <div className="alert" role="alert" data-testid="read-error">
      <span className="alert-icon" aria-hidden="true">
        !
      </span>
      <div className="alert-body">
        <strong>{t(key)}</strong>
        {error instanceof ApiError && (
          <small className="alert-ref">
            {t('common.reference')}: {error.code} · HTTP {error.status}
          </small>
        )}
      </div>
    </div>
  );
}

/** Bilingual "check against the edition" note on photo readings, always both languages (AI output is labelled in Tamil and English). */
export function ExperimentalNote() {
  const { t, lang } = useI18n();
  return (
    <p className="read-experimental" data-testid="read-experimental">
      <span className="badge unsure" aria-hidden="true">!</span>
      <span>
        <strong lang={lang}>{t('read.experimental')}</strong>{' '}
        <span lang={lang === 'ta' ? 'en' : 'ta'} className="sub">
          {t('read.experimentalOther')}
        </span>
      </span>
    </p>
  );
}

function TabButton({ id, tab, setTab, children }: { id: Tab; tab: Tab; setTab: (t: Tab) => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="tab"
      id={`read-tab-${id}`}
      aria-selected={tab === id}
      aria-controls={`read-panel-${id}`}
      tabIndex={tab === id ? 0 : -1}
      className={`read-tab ${tab === id ? 'active' : ''}`}
      onClick={() => setTab(id)}
      data-testid={`read-tab-${id}`}
    >
      {children}
    </button>
  );
}

export function ReadPanel({
  tab,
  setTab,
  onAccept,
  onLearn,
  typePanel,
}: {
  tab: Tab;
  setTab: (t: Tab) => void;
  onAccept: (a: Accepted) => void;
  onLearn: (text: string, script: Script) => void;
  typePanel: ReactNode;
}) {
  const { t, lang } = useI18n();
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState<unknown>(null);
  const [photo, setPhoto] = useState<PreparedPhoto | null>(null);
  const [res, setRes] = useState<ReadResponse | null>(null);
  const [lines, setLines] = useState<EditLine[]>([]);
  const [script, setScript] = useState<Script>(lang === 'ta' ? 'tamil' : 'iso15919');
  const [drag, setDrag] = useState(false);
  const photoInput = useRef<HTMLInputElement>(null);
  const cameraInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const reviewRef = useRef<HTMLDivElement>(null);
  const lastRequest = useRef<{ photo?: PreparedPhoto; text?: string; filename?: string } | null>(null);
  const [pendingScript, setPendingScript] = useState<Script | null>(null);

  useEffect(() => () => void (photo && URL.revokeObjectURL(photo.previewUrl)), [photo]);

  function load(data: ReadResponse, s: Script = script) {
    setRes(data);
    setLines(
      data.lines.map((l) => ({
        n: l.n,
        iso: l.text,
        tamil: l.text_tamil,
        value: s === 'tamil' ? l.text_tamil : l.text,
        include: true,
        confidence: l.confidence ?? null,
        edited: false,
      })),
    );
    setPhase('review');
    requestAnimationFrame(() => reviewRef.current?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }));
  }

  async function readPhoto(p: PreparedPhoto, again?: { reread_token: string }) {
    setPhase('reading');
    setError(null);
    lastRequest.current = { photo: p, filename: p.filename };
    try {
      load(
        await api.read({
          image_base64: p.base64,
          media_type: p.mediaType,
          ...(p.filename ? { filename: p.filename } : {}),
          ...(again ? { router: 'opus' as const, reread_token: again.reread_token } : { router: 'routed' as const }),
        }),
      );
    } catch (err) {
      setError(err);
      setPhase('idle');
    }
  }

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setError(null);
    setRes(null);
    if (looksLikeText(file)) {
      setTab('file');
      return onTextFile(file);
    }
    setPhase('preparing');
    try {
      const p = await preparePhoto(file);
      setPhoto(p);
      await readPhoto(p);
    } catch (err) {
      setError(err);
      setPhase('idle');
    }
  }

  async function onTextFile(file: File | undefined) {
    if (!file) return;
    setError(null);
    setRes(null);
    setPhoto(null);
    setPhase('reading');
    try {
      const text = await readTextFile(file);
      lastRequest.current = { text, filename: file.name };
      load(await api.read({ text, filename: file.name }));
    } catch (err) {
      setError(err);
      setPhase('idle');
    }
  }

  async function onSample(s: ReadSample) {
    let bytes: ArrayBuffer;
    try {
      const r = await fetch(new URL(s.url, window.location.href));
      if (!r.ok) throw new Error(`sample ${r.status}`);
      bytes = await r.arrayBuffer();
    } catch (err) {
      setError(err);
      return;
    }
    const file = new File([bytes], s.url.split('/').pop() ?? 'sample', { type: s.type });
    if (s.kind === 'photo') {
      setTab('photo');
      await onPhoto(file);
    } else {
      setTab('file');
      await onTextFile(file);
    }
  }

  function onDrop(e: DragEvent<HTMLElement>) {
    e.preventDefault();
    setDrag(false);
    const f = e.dataTransfer.files?.[0];
    if (f) void (looksLikeText(f) ? onTextFile(f) : onPhoto(f));
  }

  function switchScript(s: Script, confirmed = false) {
    if (s === script) return setPendingScript(null);
    // Edited lines cannot be converted reliably between scripts: ask before throwing the learner's work away.
    if (!confirmed && lines.some((l) => l.edited)) return setPendingScript(s);
    setPendingScript(null);
    setScript(s);
    setLines((ls) => ls.map((l) => ({ ...l, value: s === 'tamil' ? l.tamil : l.iso, edited: false })));
  }

  function reset() {
    setPendingScript(null);
    setPhase('idle');
    setRes(null);
    setPhoto(null);
    setLines([]);
    setError(null);
  }

  const chosen = useMemo(() => lines.filter((l) => l.include && l.value.trim()), [lines]);
  const chosenText = chosen.map((l) => l.value.trim()).join('\n');
  const chosenGaps = countGaps(chosenText);
  const busy = phase === 'preparing' || phase === 'reading';

  const samples = (kind: 'photo' | 'file') => (
    <div className="read-samples" data-testid={`read-samples-${kind}`}>
      <p className="hint-text" style={{ margin: 0 }}>
        {t('read.samplesTitle')}
      </p>
      <div className="read-sample-row">
        {READ_SAMPLES.filter((s) => (kind === 'photo' ? s.kind === 'photo' : s.kind !== 'photo')).map((s) => (
          <button key={s.id} type="button" className="read-sample" disabled={busy} onClick={() => void onSample(s)} data-testid={`sample-${s.id}`}>
            {s.kind === 'photo' ? <img src={s.thumb ?? s.url} alt="" loading="lazy" /> : <span className="read-sample-doc" aria-hidden="true">{s.kind === 'epidoc' ? 'XML' : 'TXT'}</span>}
            <span>{lang === 'ta' ? s.label_ta : s.label_en}</span>
          </button>
        ))}
      </div>
      <p className="credit" data-testid={`read-samples-credit-${kind}`}>
        {t(kind === 'photo' ? 'read.platesNote' : 'read.filesNote')}{' '}
        {[...new Set(READ_SAMPLES.filter((s) => (kind === 'photo' ? s.kind === 'photo' : s.kind !== 'photo')).map((s) => s.inscription_id))].map((id, i) => {
          const src = READ_SAMPLES.find((s) => s.inscription_id === id)!.source;
          return (
            <span key={id}>
              {i > 0 && ', '}
              <a href={safeHref(src)} target="_blank" rel="noreferrer">
                {id.replace('DHARMA_INS', '')}
              </a>
            </span>
          );
        })}
      </p>
    </div>
  );

  return (
    <div className="leaf read-card">
      <div className="read-tabs" role="tablist" aria-label={t('read.tabsLabel')}>
        <TabButton id="photo" tab={tab} setTab={setTab}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
            <circle cx="12" cy="13" r="3.5" />
          </svg>
          {t('read.tabPhoto')}
        </TabButton>
        <TabButton id="file" tab={tab} setTab={setTab}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M6 3h8l4 4v14H6z M14 3v4h4 M9 12h6 M9 16h6" />
          </svg>
          {t('read.tabFile')}
        </TabButton>
        <TabButton id="type" tab={tab} setTab={setTab}>
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 20h4L19 9l-4-4L4 16z M13 7l4 4" />
          </svg>
          {t('read.tabType')}
        </TabButton>
      </div>

      {tab === 'photo' && (
        <div role="tabpanel" id="read-panel-photo" aria-labelledby="read-tab-photo" className="grid read-panel">
          {phase !== 'review' && (
            <div
              className={`dropzone ${drag ? 'drag' : ''} ${busy ? 'busy' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              data-testid="dropzone"
            >
              {photo && busy ? (
                <div className="scan-preview">
                  <img src={photo.previewUrl} alt={t('read.image')} />
                  <span className="scan-line" aria-hidden="true" />
                </div>
              ) : (
                <svg className="dropzone-icon" viewBox="0 0 64 64" aria-hidden="true">
                  <rect x="8" y="14" width="48" height="36" rx="6" />
                  <path d="M14 42l12-12 9 9 6-6 9 9" />
                  <circle cx="44" cy="24" r="4" />
                </svg>
              )}
              <strong>{t('read.dropTitle')}</strong>
              <p className="hint-text">{t('read.dropBody')}</p>
              <div className="row" style={{ justifyContent: 'center' }}>
                <button type="button" className="btn btn-primary" disabled={busy} onClick={() => photoInput.current?.click()} data-testid="choose-photo">
                  {t('read.choosePhoto')}
                </button>
                <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => cameraInput.current?.click()} data-testid="take-photo">
                  {t('read.takePhoto')}
                </button>
              </div>
              <input ref={photoInput} type="file" accept={ACCEPT_IMAGES} hidden onChange={(e) => void onPhoto(e.target.files?.[0])} data-testid="photo-input" />
              <input ref={cameraInput} type="file" accept="image/*" capture="environment" hidden onChange={(e) => void onPhoto(e.target.files?.[0])} data-testid="camera-input" />
              {busy && (
                <p className="busy" role="status" data-testid="read-busy">
                  <span className="busy-bar" aria-hidden="true" />
                  {t(phase === 'preparing' ? 'read.preparing' : 'read.reading')}
                </p>
              )}
            </div>
          )}
          {phase !== 'review' && samples('photo')}
          {phase !== 'review' && <TrySampleImage disabled={busy} onPick={(file) => void onPhoto(file)} />}
        </div>
      )}

      {tab === 'file' && (
        <div role="tabpanel" id="read-panel-file" aria-labelledby="read-tab-file" className="grid read-panel">
          {phase !== 'review' && (
            <div
              className={`dropzone ${drag ? 'drag' : ''}`}
              onDragOver={(e) => {
                e.preventDefault();
                setDrag(true);
              }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              data-testid="file-dropzone"
            >
              <svg className="dropzone-icon" viewBox="0 0 64 64" aria-hidden="true">
                <path d="M18 8h20l10 10v38H18z M38 8v10h10 M24 30h18 M24 38h18 M24 46h12" />
              </svg>
              <p className="hint-text">{t('read.fileBody')}</p>
              <button type="button" className="btn btn-primary" disabled={busy} onClick={() => fileInput.current?.click()} data-testid="choose-file">
                {t('read.chooseFile')}
              </button>
              <input ref={fileInput} type="file" accept={ACCEPT_TEXT} hidden onChange={(e) => void onTextFile(e.target.files?.[0])} data-testid="file-input" />
              {busy && (
                <p className="busy" role="status">
                  <span className="busy-bar" aria-hidden="true" />
                  {t('common.loading')}
                </p>
              )}
            </div>
          )}
          {phase !== 'review' && samples('file')}
        </div>
      )}

      {tab === 'type' && (
        <div role="tabpanel" id="read-panel-type" aria-labelledby="read-tab-type" className="read-panel">
          {typePanel}
        </div>
      )}

      {error != null && tab !== 'type' && (
        <ReadError
          error={error}
          onRetry={lastRequest.current?.photo && !(error instanceof ApiError && error.code === 'reread_token_invalid') ? () => void readPhoto(lastRequest.current!.photo!) : undefined}
        />
      )}

      {phase === 'review' && res && tab !== 'type' && (
        <div ref={reviewRef} className="grid read-review" data-testid="read-result" aria-live="polite">
          {res.experimental && <ExperimentalNote />}
          <div className={photo ? 'read-split' : ''}>
            {photo && (
              <figure className="read-figure">
                <img src={photo.previewUrl} alt={t('read.image')} />
                <figcaption className="hint-text">
                  {photo.width}×{photo.height} · {Math.round(photo.bytes / 1024)} KB · {t('read.privacy')}
                </figcaption>
              </figure>
            )}
            <div className="grid" style={{ gap: 12 }}>
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h2 style={{ margin: 0 }}>{res.source === 'image' ? t('read.result') : t('read.fromFile')}</h2>
                <div className="segmented" role="radiogroup" aria-label={t('read.showAs')}>
                  {(['tamil', 'iso15919'] as const).map((s) => (
                    <button
                      key={s}
                      type="button"
                      role="radio"
                      aria-checked={script === s}
                      className={script === s ? 'on' : ''}
                      onClick={() => switchScript(s)}
                      data-testid={`read-script-${s}`}
                    >
                      {s === 'tamil' ? t('restore.script.tamil') : t('restore.script.iso')}
                    </button>
                  ))}
                </div>
              </div>
              <div className="chips" data-testid="read-meta">
                {res.script_guess && (
                  <span className="chip" data-testid="read-script-guess">
                    {t('read.script')}: {lang === 'ta' ? res.script_guess.label_ta : res.script_guess.label_en}
                    {res.script_guess.era ? ` · ${res.script_guess.era}` : ''}
                  </span>
                )}
                {res.title && <span className="chip">{res.title}</span>}
                <span className="chip">
                  {lines.length} {t('read.lines')} · {res.gaps} {t('read.gaps')}
                </span>
                {res.models_used.length > 0 && (
                  <span className="chip">
                    {t('read.models')}: {res.models_used.join(' → ')}
                  </span>
                )}
              </div>
              {res.source === 'epidoc' && (res.inscription_id || res.licence) && (
                <p className="credit" data-testid="read-edition">
                  {res.inscription_id && (
                    <>
                      {t('read.edition')}:{' '}
                      {res.source_url ? (
                        <a href={safeHref(res.source_url)} target="_blank" rel="noreferrer">
                          {res.inscription_id}
                        </a>
                      ) : (
                        res.inscription_id
                      )}
                      {' · '}
                    </>
                  )}
                  {res.licence && (
                    <>
                      {t('read.licence')}:{' '}
                      {res.licence_url ? (
                        <a href={safeHref(res.licence_url)} target="_blank" rel="noreferrer">
                          {res.licence}
                        </a>
                      ) : (
                        res.licence
                      )}
                    </>
                  )}
                </p>
              )}
              {res.confidence != null && <ConfidenceMeter value={res.confidence} label={t('read.confidence')} />}
              {res.warnings.map((message, i) => {
                const w = res.warning_codes?.[i];
                return (
                  <p key={i} className="note" data-testid="read-warning" data-code={w?.code}>
                    {w ? warningText(w, res, t, lang) : message}
                  </p>
                );
              })}
              {res.escalation_skipped === 'error' && <p className="note" data-testid="read-escalation-error">{t('read.escalationError')}</p>}
              {res.escalation_skipped === 'time_budget' && res.reread_token && photo && (
                <div className="row note">
                  <span>{t('read.againWhy')}</span>
                  <button type="button" className="btn btn-ghost btn-small" onClick={() => void readPhoto(photo, { reread_token: res.reread_token! })} data-testid="read-again">
                    {t('read.again')}
                  </button>
                </div>
              )}
              {pendingScript && (
                <div className="row note read-confirm" role="alertdialog" aria-live="assertive" data-testid="read-switch-confirm">
                  <span>{t('read.switchConfirm')}</span>
                  <button type="button" className="btn btn-ghost btn-small" onClick={() => switchScript(pendingScript, true)} data-testid="read-switch-yes">
                    {t('read.switchYes')}
                  </button>
                  <button type="button" className="btn btn-primary btn-small" onClick={() => setPendingScript(null)} data-testid="read-switch-no">
                    {t('read.switchNo')}
                  </button>
                </div>
              )}
              <p className="hint-text" style={{ margin: 0 }}>
                {t('read.editHint')}
              </p>
              <ol className="read-lines" data-testid="read-lines">
                {lines.map((l, i) => (
                  <li key={`${l.n}-${i}`} className={`read-line ${l.include ? '' : 'off'}`} style={{ animationDelay: `${Math.min(i, 12) * 60}ms` }}>
                    <label className="read-line-check">
                      <input
                        type="checkbox"
                        checked={l.include}
                        onChange={(e) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, include: e.target.checked } : x)))}
                        aria-label={`${t('read.useLine')} ${l.n}`}
                      />
                      <span className="read-line-n">{l.n}</span>
                    </label>
                    <textarea
                      rows={l.value.length > 34 ? 2 : 1}
                      className="read-line-input"
                      value={l.value}
                      lang={script === 'tamil' ? 'ta' : undefined}
                      aria-label={`${t('read.line')} ${l.n}`}
                      onChange={(e) => setLines((ls) => ls.map((x, j) => (j === i ? { ...x, value: e.target.value, edited: true } : x)))}
                      data-testid={`read-line-${i}`}
                    />
                    {l.confidence != null && (
                      <span className={`badge ${l.confidence < 0.6 ? 'unsure' : ''}`} title={t('read.confidence')}>
                        {Math.round(l.confidence * 100)}%
                      </span>
                    )}
                  </li>
                ))}
              </ol>
              {chosenGaps > MAX_RESTORE_GAPS && <p className="note" data-testid="read-too-many-gaps">{t('read.tooManyGaps')}</p>}
              {chosen.length > 0 && chosenGaps === 0 && <p className="note">{t('read.noGapsHere')}</p>}
              {chosenText.length > LEARN_TEXT_LIMIT && (
                <p className="hint-text" data-testid="read-learn-cut">
                  {t('read.learnCut')}
                </p>
              )}
              <div className="row">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!chosen.length || chosenGaps === 0 || chosenGaps > MAX_RESTORE_GAPS}
                  onClick={() => onAccept({ text: chosenText, script, source: res.source })}
                  data-testid="read-use-restore"
                >
                  {t('read.useForRestore')}
                </button>
                <button type="button" className="btn btn-ghost" disabled={!chosen.length} onClick={() => onLearn(chosenText, script)} data-testid="read-use-learn">
                  {t('read.useForLearn')}
                </button>
                <button type="button" className="btn btn-ghost btn-small" onClick={reset} data-testid="read-reset">
                  {t('read.startOver')}
                </button>
              </div>
              {res.experimental && (
                <p className="credit">
                  <a href="https://github.com/Vivek0712/ezhuthu/blob/main/eval/reports/2026-11-02-ocr-eval.md" target="_blank" rel="noreferrer">
                    {t('read.measured')}
                  </a>
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
