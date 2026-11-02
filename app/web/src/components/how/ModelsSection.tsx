import { useI18n } from '../../i18n/I18nProvider';
import { fmt, pctText } from '../../practice/engine';
import { EXAMPLE } from '../Pipeline';
import { Bi } from '../practice/Bi';
import { NUMS, VARI } from './how-data';

/** Two real gaps on a 0-100% line with the Sonnet fill level: one left open, one filled. */
function ThresholdLine() {
  const { t } = useI18n();
  // practice/banks/worked-example.json (0.1495, open) and samples/recorded-restores.json vari gap (0.9628, filled);
  // both were answered by Sonnet, so the Sonnet level applies (deployed-config.md: 0.4111).
  const level = NUMS.thrSonnet;
  const open = EXAMPLE.candidates[0]!;
  const pts = [
    { key: 'open', c: open.confidence, ta: open.ta, iso: open.iso, out: t('hw.thrOpen') },
    { key: 'fill', c: VARI.top.confidence, ta: VARI.top.text_tamil, iso: VARI.top.text, out: t('hw.thrFill') },
  ];
  return (
    <figure className="thr" data-testid="threshold">
      <figcaption className="hint-text">{t('hw.thrLabel')}</figcaption>
      <div className="thr-track" role="img" aria-label={`${t('hw.thrLevel')} ${pctText(level)}; ${pts.map((p) => `${p.iso} ${pctText(p.c)} ${p.out}`).join('; ')}`}>
        <span className="thr-open-zone" style={{ width: `${level * 100}%` }} />
        <span className="thr-level" style={{ left: `${level * 100}%` }}>
          <span className="thr-level-label">
            {t('hw.thrLevel')} {pctText(level)}
          </span>
        </span>
        {pts.map((p) => (
          <span key={p.key} className={`thr-pt thr-${p.key}`} style={{ left: `${p.c * 100}%` }} />
        ))}
      </div>
      <ul className="thr-legend">
        {pts.map((p) => (
          <li key={p.key} className={`thr-${p.key}`}>
            <Bi ta={p.ta} iso={p.iso} /> <strong>{pctText(p.c)}</strong> · {p.out}
          </li>
        ))}
      </ul>
    </figure>
  );
}

/** "Models and decisions": Sonnet -> Opus routing, calibration and the fill level, where the Strands Decider is used. */
export function ModelsSection() {
  const { t } = useI18n();
  return (
    <div className="grid grid-3 models" data-testid="models">
      <section className="leaf" data-testid="models-route">
        <h3>{t('hw.routeTitle')}</h3>
        {/* config/models.yaml routing: escalate_if_gap_chars_over 12, escalate_if_no_parallel, escalate_if_confidence_below 0.6. */}
        <p>{t('hw.route1')}</p>
        {/* eval/reports/2026-11-02-deployed-config.md, "Cost and latency (TEST)": 296 of 413 use Opus (291 + 5), $0.0060 per gap, p50 3.2 s. */}
        <p>{fmt(t('hw.route2'), { n: NUMS.testGaps, opus: NUMS.opusGaps, pre: NUMS.opusPre, after: NUMS.opusAfter, usd: NUMS.usdPerGap, p50: NUMS.p50 })}</p>
      </section>
      <section className="leaf" data-testid="models-cal">
        <h3>{t('hw.calTitle')}</h3>
        <p>{t('hw.cal1')}</p>
        {/* eval/reports/2026-11-02-deployed-config.md: thresholds 0.4111 / 0.4887; TEST coverage 0.4988, selective accuracy 0.9078 (187/206). */}
        <p>
          {fmt(t('hw.cal2'), {
            ts: pctText(NUMS.thrSonnet),
            to: pctText(NUMS.thrOpus),
            cov: pctText(NUMS.coverage),
            acc: pctText(NUMS.selAcc),
            k: NUMS.selK,
            n: NUMS.selN,
          })}
        </p>
        <ThresholdLine />
      </section>
      <section className="leaf" id="decider-use" data-testid="models-decider">
        <h3>{t('hw.decTitle')}</h3>
        {/* src/ezhuthu/agent/tutor/policy.py: pedagogy choice by Strands Decider with rule guardrails. */}
        <p>{t('hw.dec1')}</p>
        {/* eval/reports/2026-11-02-deployed-config.md VAL stage 2: hosted v19 39 vs 41 of 120 (p = 0.69); 13 of 120 over the 27 s proxy limit. */}
        <p>
          {fmt(t('hw.dec2'), { n: NUMS.hostedN, d: NUMS.hostedMatches, w: NUMS.chosenMatches, slow: NUMS.hostedSlow, limit: NUMS.proxyLimitS })}
        </p>
      </section>
      <p className="hint-text models-source">{t('hw.modelsSource')}</p>
    </div>
  );
}
