import { useState, type ChangeEvent } from 'react';
import { api, type EvaluateBuiltinRequest, type EvaluateResponse } from '../api/client';
import { Busy, CC_BY_SA, ErrorNote } from '../components/Feedback';
import { ReliabilityChart } from '../components/ReliabilityChart';
import { useI18n } from '../i18n/I18nProvider';
import { pct } from '../lib/format';
import { validateJsonl, type JsonlReport } from '../lib/jsonl';

export function TestPage() {
  const { t } = useI18n();
  const [form, setForm] = useState<EvaluateBuiltinRequest>({ benchmark: 'test-hard', limit: 50, router: 'routed' });
  const [upload, setUpload] = useState<{ name: string; text: string; report: JsonlReport } | null>(null);
  const [report, setReport] = useState<EvaluateResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function run(p: () => Promise<EvaluateResponse>) {
    setBusy(true);
    setError(null);
    try {
      setReport(await p());
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    const text = await f.text();
    setUpload({ name: f.name, text, report: validateJsonl(text) });
  }

  return (
    <>
      <header className="page-head">
        <h1>{t('test.title')}</h1>
        <p className="lede">{t('test.lede')}</p>
        <p className="credit" data-testid="benchmark-credit">
          {t('credit.benchmark')}{' '}
          <a href={CC_BY_SA} target="_blank" rel="noreferrer">
            CC BY-SA 4.0
          </a>
        </p>
      </header>
      <div className="grid grid-2">
        <form
          className="leaf grid"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => api.evaluate(form));
          }}
        >
          <h2>{t('test.builtin')}</h2>
          <label className="field">
            {t('test.benchmark')}
            <select value={form.benchmark} onChange={(e) => setForm({ ...form, benchmark: e.target.value as EvaluateBuiltinRequest['benchmark'] })}>
              <option value="test-hard">test-hard</option>
              <option value="test">test</option>
            </select>
          </label>
          <label className="field">
            {t('test.limit')}
            <input
              type="text"
              inputMode="numeric"
              value={form.limit}
              onChange={(e) => setForm({ ...form, limit: Math.max(1, Math.min(2000, Number(e.target.value.replace(/\D/g, '')) || 1)) })}
            />
          </label>
          <label className="field">
            {t('test.router')}
            <select value={form.router} onChange={(e) => setForm({ ...form, router: e.target.value as EvaluateBuiltinRequest['router'] })}>
              <option value="routed">routed</option>
              <option value="sonnet">sonnet</option>
              <option value="opus">opus</option>
            </select>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy} data-testid="run-benchmark">
            {t('test.run')}
          </button>
        </form>
        <div className="leaf grid">
          <h2>{t('test.upload')}</h2>
          <label className="field">
            <span className="hint-text">{t('test.uploadHint')}</span>
            <input type="file" accept=".jsonl,.ndjson,application/x-ndjson" onChange={(e) => void onFile(e)} data-testid="jsonl-file" />
          </label>
          {upload && (
            <div data-testid="jsonl-report">
              <p className="row">
                <span className="badge ok">
                  {upload.report.valid} {t('test.validLines')}
                </span>
                <span className={upload.report.errors.length ? 'badge accent' : 'badge'}>
                  {upload.report.errors.length} {t('test.invalidLines')}
                </span>
              </p>
              {upload.report.errors.length > 0 && (
                <ul className="errors">
                  {upload.report.errors.map((er) => (
                    <li key={er.line}>
                      {t('test.line')} {er.line}: {er.message}
                    </li>
                  ))}
                </ul>
              )}
              <button
                className="btn btn-primary"
                type="button"
                disabled={busy || upload.report.valid === 0 || upload.report.errors.length > 0}
                onClick={() => void run(() => api.evaluateUpload(upload.text))}
                data-testid="evaluate-upload"
              >
                {t('test.evaluateUpload')}
              </button>
            </div>
          )}
        </div>
      </div>
      <div style={{ marginTop: 16 }}>
        {busy && <Busy />}
        {error != null && <ErrorNote error={error} />}
      </div>
      {report && (
        <section className="grid" style={{ marginTop: 24 }} data-testid="score-report">
          <h2>{t('test.report')}</h2>
          <div className="stats">
            {(
              [
                ['test.n', String(report.n)],
                ['test.top1', pct(report.top1, 1)],
                ['test.top20', pct(report.top20, 1)],
                ['test.cer', report.cer.toFixed(3)],
                ['test.ece', report.ece.toFixed(3)],
              ] as const
            ).map(([k, v]) => (
              <div className="stat" key={k}>
                <div className="k">{t(k)}</div>
                <div className="v">{v}</div>
              </div>
            ))}
          </div>
          <div className="grid grid-2">
            <section className="leaf">
              <h3>{t('test.reliability')}</h3>
              <ReliabilityChart items={report.items} title={t('test.reliability')} />
              <p className="hint-text">{t('test.reliabilityHint')}</p>
            </section>
            <section className="leaf">
              <h3>{t('test.coverage')}</h3>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>{t('test.threshold')}</th>
                      <th>Coverage</th>
                      <th>{t('test.accuracy')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.coverage.map((c) => (
                      <tr key={c.threshold}>
                        <td>{c.threshold.toFixed(2)}</td>
                        <td>{pct(c.coverage, 1)}</td>
                        <td>{pct(c.accuracy, 1)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 style={{ marginTop: 18 }}>{t('test.byRouter')}</h3>
              <div className="table-scroll">
                <table>
                  <tbody>
                    {Object.entries(report.by_router).map(([name, s]) => (
                      <tr key={name}>
                        <th>{name}</th>
                        <td>n={s.n ?? '—'}</td>
                        <td>top-1 {pct(s.top1, 1)}</td>
                        <td>ECE {s.ece?.toFixed(3) ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        </section>
      )}
    </>
  );
}
