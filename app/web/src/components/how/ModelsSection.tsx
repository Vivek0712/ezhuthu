import type { CSSProperties } from 'react';
import { useI18n } from '../../i18n/I18nProvider';
import { fmt, pctText } from '../../practice/engine';
import { EXAMPLE } from '../Pipeline';
import { Bi } from '../practice/Bi';
import { NUMS, VARI } from './how-data';
import { useInView } from './useInView';

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
          <span key={p.key} className={`thr-pt thr-${p.key}`} style={{ '--c': p.c } as CSSProperties} />
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

/** "Models and decisions": Sonnet -> Opus routing as a bar, calibration and the fill level on a line, and where the
 * Strands Decider is (and is not) used. Bars and points move into place when the section scrolls into view. */
export function ModelsSection() {
  const { t } = useI18n();
  const [ref, inView] = useInView<HTMLDivElement>(true);
  return (
    <div ref={ref} className={`grid grid-3 models ${inView ? 'is-in' : ''}`} data-testid="models">
      <section className="leaf" data-testid="models-route">
        <h3>{t('hw.routeTitle')}</h3>
        {/* config/models.yaml routing: escalate_if_gap_chars_over 12, escalate_if_no_parallel, escalate_if_confidence_below 0.6. */}
        <p>{t('hw.route1')}</p>
        {/* eval/reports/2026-11-02-deployed-config.md, "Cost and latency (TEST)": 296 of 413 use Opus (291 + 5), $0.0060 per gap, p50 3.2 s. */}
        <div className="route-bar" role="img" aria-label={fmt(t('hw.routeBar'), { opus: NUMS.opusGaps, n: NUMS.testGaps })} style={{ '--w': NUMS.opusGaps / NUMS.testGaps } as CSSProperties}>
          <span className="route-opus">Opus 4.6</span>
          <span className="route-sonnet">Sonnet 4.6</span>
        </div>
        <p className="hint-text">
          {fmt(t('hw.routeBar'), { opus: NUMS.opusGaps, n: NUMS.testGaps })} · {fmt(t('hw.routeCost'), { usd: NUMS.usdPerGap, p50: NUMS.p50 })}
        </p>
      </section>
      <section className="leaf" data-testid="models-cal">
        <h3>{t('hw.calTitle')}</h3>
        <p>{t('hw.cal1')}</p>
        <ThresholdLine />
        {/* eval/reports/2026-11-02-deployed-config.md: TEST coverage 0.4988, selective accuracy 0.9078 (187/206). */}
        <p className="hint-text">{fmt(t('hw.cal2'), { cov: pctText(NUMS.coverage), acc: pctText(NUMS.selAcc), k: NUMS.selK, n: NUMS.selN })}</p>
      </section>
      <section className="leaf" id="decider-use" data-testid="models-decider">
        <h3>{t('hw.decTitle')}</h3>
        <ul className="dec-uses">
          {/* src/ezhuthu/agent/tutor/policy.py: pedagogy choice by Strands Decider with rule guardrails. */}
          <li className="is-yes">{t('hw.dec1')}</li>
          {/* config/models.yaml restorer.strategy_llm: choice-topk with ezhuthu-strands-2b-ft (deployed 2026-11-04,
              DeciderBackend hosted); eval/reports/2026-11-02-finetuned-decider.md. The pre-rank is the fallback. */}
          <li className="is-yes">{t('hw.dec2')}</li>
        </ul>
        <details className="how-more">
          <summary>{t('hw.more')}</summary>
          {/* eval/reports/2026-11-02-deployed-config.md VAL stage 2: hosted v19 39 vs 41 of 120 (p = 0.69); 13 of 120 over the 27 s proxy limit. */}
          <p>{fmt(t('hw.dec3'), { n: NUMS.hostedN, d: NUMS.hostedMatches, w: NUMS.chosenMatches, slow: NUMS.hostedSlow, limit: NUMS.proxyLimitS })}</p>
        </details>
      </section>
      <p className="hint-text models-source">{t('hw.modelsSource')}</p>
    </div>
  );
}
