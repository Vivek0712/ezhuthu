import { useEffect } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { SUMMARY } from '../benchmark/summary';
import { DharmaCredit } from '../components/Feedback';
import { AgentCards } from '../components/how/AgentCards';
import { CloudDiagram } from '../components/how/CloudDiagram';
import { FlowDiagram } from '../components/how/FlowDiagram';
import { HowOverview } from '../components/how/HowOverview';
import { ModelsSection } from '../components/how/ModelsSection';
import { OntologySection } from '../components/how/OntologySection';
import { PeopleSection } from '../components/how/PeopleSection';
import { useI18n } from '../i18n/I18nProvider';
import { fmt, pctText } from '../practice/engine';
import '../styles/how.css';

/** The sections under the overview: agents, how they work together, ontology, models, cloud, people. */
const HOW_SECTIONS = [
  { id: 'how-agents', title: 'hw.agentsTitle', lede: 'hw.agentsLede', body: <AgentCards /> },
  { id: 'how-flow', title: 'hw.flowTitle', lede: null, body: <FlowDiagram /> },
  { id: 'how-ontology', title: 'hw.ontoTitle', lede: null, body: <OntologySection /> },
  { id: 'how-models', title: 'hw.modelsTitle', lede: null, body: <ModelsSection /> },
  { id: 'how-cloud', title: 'hw.cloudTitle', lede: 'hw.cloudLede', body: <CloudDiagram /> },
  { id: 'how-people', title: 'hw.peopleTitle', lede: null, body: <PeopleSection /> },
] as const;

// benchmark/summary.json (scripts/build_benchmark_summary.py from eval/reports/2026-11-02-deployed-config.md).
const DEPLOYED = SUMMARY.leaderboard.full.rows.find((r) => r.id === 'deployed')!;
const ABST = SUMMARY.abstention;
const LONG = SUMMARY.gap_length.bins.find((b) => b.key === '4+ letters')!;

/** Scroll to #agent-reader etc. (the home chips) once the page has rendered; the router does not do it by itself. */
function useHashScroll() {
  const { hash } = useLocation();
  useEffect(() => {
    if (!hash) return;
    const el = document.getElementById(decodeURIComponent(hash.slice(1)));
    if (!el) return;
    el.scrollIntoView({ block: 'start' });
    if (el.tabIndex < 0 && el.hasAttribute('tabindex')) el.focus({ preventScroll: true });
  }, [hash]);
}

/** /how-it-works: an animated overview on one real stone, then each part of the system said with visuals and real
 * data (details under "More"), and the honest limits. */
export function HowItWorksPage() {
  const { t } = useI18n();
  useHashScroll();
  const tiles = [
    { k: 'top1', big: pctText(DEPLOYED.top1), text: fmt(t('hw.limTop1'), { k: DEPLOYED.matches, n: DEPLOYED.n }) },
    { k: 'fill', big: pctText(ABST.selective_accuracy), text: fmt(t('hw.limFill'), { cov: pctText(ABST.coverage), k: ABST.filled_matching, n: ABST.filled }) },
    { k: 'long', big: pctText(LONG.deployed), text: t('hw.limLong') },
    { k: 'brahmi', big: '✕', text: t('hw.limBrahmi') },
  ];
  return (
    <>
      <header className="page-head how-head">
        <h1>{t('how.pageTitle')}</h1>
        <p className="lede">{t('how.lede')}</p>
      </header>

      <HowOverview />

      {HOW_SECTIONS.map((sec) => (
        <section key={sec.id} id={sec.id} aria-labelledby={`${sec.id}-title`} className="how-section" data-testid={sec.id}>
          <h2 id={`${sec.id}-title`}>{t(sec.title)}</h2>
          {sec.lede && <p className="lede">{t(sec.lede)}</p>}
          {sec.body}
        </section>
      ))}

      <section aria-labelledby="limits-title" className="how-section how-limits" data-testid="how-limits">
        <h2 id="limits-title">{t('how.limitsTitle')}</h2>
        <ul className="lim-tiles">
          {tiles.map((x) => (
            <li key={x.k} className={`lim-tile lim-${x.k}`} data-testid={`lim-${x.k}`}>
              <strong>{x.big}</strong>
              <span>{x.text}</span>
            </li>
          ))}
        </ul>
        <p className="hint-text">
          {t('hw.limConf')} {t('hw.limData')} {t('how.limitsSource')}
        </p>
        <div data-testid="how-data">
          <DharmaCredit testId="how-credit" />
        </div>
        <p>
          <Link to="/benchmark" data-testid="how-results">
            {t('how.resultsLink')} →
          </Link>
        </p>
        <div className="row">
          <Link className="btn btn-primary" to="/practice">
            {t('how.ctaPractice')}
          </Link>
          <Link className="btn btn-ghost" to="/restore">
            {t('how.ctaRestore')}
          </Link>
        </div>
      </section>
    </>
  );
}
