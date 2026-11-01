import { Link } from 'react-router-dom';
import { EvolutionHero } from '../components/EvolutionHero';
import { Frieze } from '../components/Frieze';
import { useI18n } from '../i18n/I18nProvider';

export function HomePage() {
  const { t } = useI18n();
  return (
    <>
      <section className="hero">
        <div>
          <p className="kicker">{t('home.kicker')}</p>
          <h1>{t('home.title')}</h1>
          <p className="lede">{t('home.lede')}</p>
          <div className="hero-actions">
            <Link className="btn btn-primary" to="/learn">
              {t('home.ctaLearn')}
            </Link>
            <Link className="btn btn-ghost" to="/restore">
              {t('home.ctaRestore')}
            </Link>
          </div>
        </div>
        <EvolutionHero />
      </section>
      <Frieze />
      <section style={{ marginTop: 36 }}>
        <h2>{t('home.stepsTitle')}</h2>
        <ol className="steps">
          <li>{t('home.step1')}</li>
          <li>{t('home.step2')}</li>
          <li>{t('home.step3')}</li>
          <li>{t('home.step4')}</li>
        </ol>
      </section>
    </>
  );
}
