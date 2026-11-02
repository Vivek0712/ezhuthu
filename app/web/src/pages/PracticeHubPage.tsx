import { Navigate, useLocation, useSearchParams } from 'react-router-dom';
import { EvolutionHero } from '../components/EvolutionHero';
import { SessionCards } from '../components/practice/SessionCards';
import { useI18n } from '../i18n/I18nProvider';

/** /practice: every session type with its levels. Old links into the AI tutor lesson are forwarded to it. */
export function PracticeHubPage() {
  const { t } = useI18n();
  const loc = useLocation();
  const [params] = useSearchParams();
  // "Practise with this" (sample gallery: ?inscription=&sample=&level=L3) and Restore's hand-off (state.text) were
  // made for the AI tutor lesson, which now lives at /practice/guided.
  const handed = (loc.state as { text?: unknown } | null)?.text;
  if (params.get('inscription') || params.get('sample') || /^L[1-5]$/.test(params.get('level') ?? '') || typeof handed === 'string')
    return <Navigate replace to={{ pathname: '/practice/guided', search: loc.search }} state={loc.state} />;

  return (
    <>
      <header className="page-head">
        <h1>{t('prac.title')}</h1>
        <p className="lede">{t('prac.lede')}</p>
      </header>
      <SessionCards full />
      <p className="credit prac-credit" data-testid="practice-credit">
        {t('prac.credit')}
      </p>
      <section className="evo-section" aria-labelledby="evo-title">
        <h2 id="evo-title">{t('prac.eraTitle')}</h2>
        <EvolutionHero />
      </section>
    </>
  );
}
