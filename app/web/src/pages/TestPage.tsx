import { useState, type ChangeEvent } from 'react';
import { api, type EvaluateBuiltinRequest, type EvaluateResponse } from '../api/client';
import { useAuth } from '../auth/AuthProvider';
import { SUMMARY, sourceUrl, type SourceId, type SystemId } from '../benchmark/summary';
import { BarChart } from '../components/BarChart';
import { Busy, CC_BY_SA, DharmaCredit, ErrorNote } from '../components/Feedback';
import { ReliabilityChart } from '../components/ReliabilityChart';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { pct } from '../lib/format';
import { validateJsonl, type JsonlReport } from '../lib/jsonl';
import { fmt } from '../practice/engine';

const S = SUMMARY;
const f4 = (x: number) => x.toFixed(4);
const f3 = (x: number) => x.toFixed(3);
/** The reports' p text ('0.0002' or '<0.0001') with its comparator: '= 0.0002', '< 0.0001'. */
const pRel = (p: string) => (p.startsWith('<') ? `< ${p.slice(1)}` : `= ${p}`);

function Source({ path }: { path: string }) {
  const { t } = useI18n();
  return (
    <p className="hint-text bench-source">
      {t('bench.source')}:{' '}
      <a href={sourceUrl(path)} target="_blank" rel="noreferrer">
        {path}
      </a>
    </p>
  );
}

/** /benchmark: public results from the committed reports, then the runner for signed-in users. */
export function TestPage() {
  const { t } = useI18n();
  const [subset, setSubset] = useState<'full' | 'hard'>('full');
  const full = S.leaderboard.full;
  const dep = full.rows.find((r) => r.id === 'deployed')!;
  const ab = S.abstention;
  const long = S.gap_length.bins[S.gap_length.bins.length - 1]!;
  const lb = S.leaderboard[subset];
  const sys = (id: SystemId) => t(`bench.sys.${id}` as MessageKey);
  const h = S.decider.hosted;
  const sp = S.decider.sparrow;
  const m = S.method;
  const o = S.ocr;

  return (
    <>
      <header className="page-head">
        <p className="kicker">{t('bench.kicker')}</p>
        <h1>{t('bench.title')}</h1>
        <p className="lede">{fmt(t('bench.lede'), { n: m.splits.test.items, ins: m.splits.test.inscriptions })}</p>
        <p className="credit" data-testid="benchmark-credit">
          {t('credit.benchmark')}{' '}
          <a href={CC_BY_SA} target="_blank" rel="noreferrer">
            CC BY-SA 4.0
          </a>
        </p>
      </header>

      <div className="stats bench-stats" data-testid="bench-headline">
        <div className="stat">
          <div className="k">{t('bench.statTop1')}</div>
          <div className="v">{f4(dep.top1)}</div>
          <div className="hint-text">{fmt(t('bench.statTop1Sub'), { k: dep.matches, n: dep.n })}</div>
        </div>
        <div className="stat">
          <div className="k">{t('bench.statFill')}</div>
          <div className="v">{pct(ab.selective_accuracy, 1)}</div>
          <div className="hint-text">{fmt(t('bench.statFillSub'), { k: ab.filled_matching, n: ab.filled, cov: pct(ab.coverage, 1) })}</div>
        </div>
        <div className="stat">
          <div className="k">{t('bench.statLong')}</div>
          <div className="v">{f4(long.deployed)}</div>
          <div className="hint-text">{fmt(t('bench.statLongSub'), { n: long.n })}</div>
        </div>
      </div>

      <section className="bench-section" aria-labelledby="lb-title" data-testid="leaderboard">
        <h2 id="lb-title">{t('bench.lbTitle')}</h2>
        <p>{t('bench.lbLede')}</p>
        <div className="row" role="group" aria-label={t('bench.lbTitle')}>
          {(['full', 'hard'] as const).map((k) => (
            <button
              key={k}
              type="button"
              className={`chip-btn ${subset === k ? 'on' : ''}`}
              aria-pressed={subset === k}
              onClick={() => setSubset(k)}
              data-testid={`subset-${k}`}
            >
              {fmt(t(k === 'full' ? 'bench.subsetFull' : 'bench.subsetHard'), { n: S.leaderboard[k].n })}
            </button>
          ))}
        </div>
        {subset === 'hard' && <p className="hint-text">{t('bench.subsetHardHint')}</p>}
        <BarChart
          testId="leaderboard-chart"
          title={t('bench.lbTitle')}
          data={lb.rows.map((r) => ({
            key: r.id,
            label: sys(r.id),
            sub: t(`bench.sys.${r.id}D` as MessageKey),
            value: r.top1,
            valueText: f4(r.top1),
            ci: r.ci,
            highlight: r.id === 'deployed',
          }))}
        />
        <div className="table-scroll">
          <table data-testid="leaderboard-table">
            <thead>
              <tr>
                <th>{t('bench.colSystem')}</th>
                <th>{t('bench.colTop1')}</th>
                <th>{t('bench.colMatches')}</th>
                <th>{t('bench.colVs')}</th>
              </tr>
            </thead>
            <tbody>
              {lb.rows.map((r) => (
                <tr key={r.id}>
                  <th scope="row">{sys(r.id)}</th>
                  <td>
                    {f4(r.top1)}
                    {r.ci && ` [${r.ci[0]}–${r.ci[1]}]`}
                  </td>
                  <td>
                    {r.matches} / {r.n}
                  </td>
                  <td>
                    {r.id === 'deployed'
                      ? t('bench.vsSelf')
                      : r.vs_deployed
                        ? fmt(t('bench.vs'), { a: r.vs_deployed.only_deployed, b: r.vs_deployed.only_other, p: pRel(r.vs_deployed.p_text) })
                        : t('bench.vsNone')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="hint-text">{t('bench.vsNote')}</p>
        <Source path={S.sources.deployed} />
        <Source path={S.sources.test} />
      </section>

      <section className="bench-section" aria-labelledby="stop-title" data-testid="bench-stop">
        <h2 id="stop-title">{t('bench.stopTitle')}</h2>
        <p>
          {fmt(t('bench.stopBody'), { cov: pct(ab.coverage, 1), acc: pct(ab.selective_accuracy, 1), k: ab.filled_matching, n: ab.filled })}
        </p>
        <div className="grid grid-2">
          <div className="leaf">
            <h3>{t('bench.relTitle')}</h3>
            <ReliabilityChart
              title={t('bench.relChart')}
              binned={ab.reliability.map((b) => ({ lo: b.lo, hi: b.hi, count: b.n, accuracy: b.accuracy ?? 0, meanConfidence: b.confidence ?? 0 }))}
            />
            <p className="hint-text">{t('bench.relAxis')}</p>
          </div>
          <div>
            <p>{fmt(t('bench.relBody'), { n: ab.n })}</p>
            <p>{fmt(t('bench.ece'), { ece: f3(ab.ece) })}</p>
          </div>
        </div>
        <Source path={ab.source} />
      </section>

      <section className="bench-section" aria-labelledby="gap-title" data-testid="bench-gaps">
        <h2 id="gap-title">{t('bench.gapTitle')}</h2>
        <p>{fmt(t('bench.gapBody'), { x: f4(long.deployed), c: f4(long.copy) })}</p>
        <BarChart
          testId="gap-chart"
          title={t('bench.gapTitle')}
          data={S.gap_length.bins.map((b) => ({
            key: b.key,
            label: t(`bench.gap.${b.key}` as MessageKey),
            sub: `${b.n} ${t('bench.colGaps').toLowerCase()}`,
            value: b.deployed,
            valueText: f4(b.deployed),
            highlight: true,
          }))}
        />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{t('bench.colGap')}</th>
                <th>{t('bench.colGaps')}</th>
                {(['deployed', 'ngram', 'routed2b', 'copy'] as const).map((id) => (
                  <th key={id}>{sys(id)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {S.gap_length.bins.map((b) => (
                <tr key={b.key}>
                  <th scope="row">{t(`bench.gap.${b.key}` as MessageKey)}</th>
                  <td>{b.n}</td>
                  {(['deployed', 'ngram', 'routed2b', 'copy'] as const).map((id) => (
                    <td key={id}>{f4(b[id])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Source path={S.gap_length.source} />
      </section>

      <section className="bench-section" aria-labelledby="ocr-title" data-testid="bench-ocr">
        <h2 id="ocr-title">{t('bench.ocrTitle')}</h2>
        <p>{t('bench.ocrBody')}</p>
        <BarChart
          testId="ocr-chart"
          title={t('bench.ocrChart')}
          data={[
            ...(['clean', 'photo', 'weathered'] as const).map((k) => ({
              key: k,
              label: fmt(t(`bench.ocr.${k}` as MessageKey), { n: o.tamil_synthetic[k].n }),
              value: o.tamil_synthetic[k].cer,
              valueText: f3(o.tamil_synthetic[k].cer),
            })),
            { key: 'printed', label: fmt(t('bench.ocr.printed'), { n: o.printed_pages.n }), value: o.printed_pages.cer, valueText: f3(o.printed_pages.cer) },
            { key: 'brahmi', label: fmt(t('bench.ocr.brahmi'), { n: o.brahmi_real.n }), value: o.brahmi_real.cer, valueText: f3(o.brahmi_real.cer), highlight: true },
          ]}
        />
        <p className="note note-unsure">{fmt(t('bench.ocrFail'), { n: o.brahmi_real.n, x: f3(o.brahmi_real.cer) })}</p>
        <Source path={o.source} />
      </section>

      <section className="bench-section" aria-labelledby="dec-title" data-testid="bench-decider">
        <h2 id="dec-title">{t('bench.decTitle')}</h2>
        <p>
          {fmt(t('bench.dec1'), { n: h.n, a: h.hosted_matching, b: h.chosen_matching, x: h.only_hosted, y: h.only_chosen, p: h.p_text })}
        </p>
        <p>{fmt(t('bench.dec2'), { o: h.over_limit, n: h.n, s: h.limit_s })}</p>
        <p>{fmt(t('bench.dec3'), { best: f3(sp.best_top1), n: sp.n, rnd: f3(sp.random_top3), first: f3(sp.first_candidate) })}</p>
        <p>{fmt(t('bench.dec4'), { fin: f3(sp.nano_policy_final), raw: f3(sp.nano_policy_raw), n: sp.policy_n })}</p>
        <Source path={h.source} />
        <Source path={sp.source} />
      </section>

      <section className="bench-section leaf" aria-labelledby="method-title" data-testid="bench-method">
        <h2 id="method-title">{t('bench.methodTitle')}</h2>
        <ul>
          <li>
            {fmt(t('bench.m1'), {
              tr: m.splits.train.inscriptions,
              va: m.splits.val.inscriptions,
              te: m.splits.test.inscriptions,
              items: m.splits.test.items,
            })}
          </li>
          <li>{fmt(t('bench.m2'), { sel: m.val_selection_n })}</li>
          <li>{fmt(t('bench.m3'), { b: m.bootstrap_resamples.toLocaleString('en') })}</li>
          <li>{t('bench.m4')}</li>
          <li>{t('bench.m5')}</li>
          <li>{t('bench.m6')}</li>
        </ul>
        <h3>{t('bench.reports')}</h3>
        <ul className="bench-reports" data-testid="bench-reports">
          {(Object.entries(S.sources) as [SourceId, string][]).map(([k, path]) => (
            <li key={k}>
              <a href={sourceUrl(path)} target="_blank" rel="noreferrer">
                {t(`bench.rep.${k}` as MessageKey)}
              </a>{' '}
              <span className="hint-text">{path}</span>
            </li>
          ))}
        </ul>
        <DharmaCredit testId="bench-dharma-credit" />
        <p lang="en">{t('about.builtWith')}</p>
      </section>

      <Runner />
    </>
  );
}

/** The built-in benchmark runner and JSONL upload: signed-in users only. */
function Runner() {
  const { t } = useI18n();
  const auth = useAuth();
  return (
    <section className="bench-section" aria-labelledby="run-title" data-testid="bench-runner">
      <h2 id="run-title">{t('bench.runTitle')}</h2>
      <p>{t('bench.runLede')}</p>
      {auth.user ? (
        <RunnerForms />
      ) : (
        <div className="leaf" data-testid="runner-gate">
          <p>{t('bench.runSignIn')}</p>
          {auth.mock && <p className="note">{t('auth.mockNote')}</p>}
          <button className="btn btn-primary" type="button" onClick={() => void auth.signIn()} disabled={!auth.configured}>
            {t('auth.signIn')}
          </button>
        </div>
      )}
    </section>
  );
}

function RunnerForms() {
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
      <div className="grid grid-2">
        <form
          className="leaf grid"
          onSubmit={(e) => {
            e.preventDefault();
            void run(() => api.evaluate(form));
          }}
        >
          <h3>{t('test.builtin')}</h3>
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
          <h3>{t('test.upload')}</h3>
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
          <h3>{t('test.report')}</h3>
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
              <h4>{t('test.reliability')}</h4>
              <ReliabilityChart items={report.items} title={t('test.reliability')} />
              <p className="hint-text">{t('test.reliabilityHint')}</p>
            </section>
            <section className="leaf">
              <h4>{t('test.coverage')}</h4>
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
              <h4 style={{ marginTop: 18 }}>{t('test.byRouter')}</h4>
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
