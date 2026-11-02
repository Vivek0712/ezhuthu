import { Link } from 'react-router-dom';
import { EvolutionHero } from '../components/EvolutionHero';
import { Frieze } from '../components/Frieze';
import { SampleGallery } from '../components/SampleGallery';
import { useI18n } from '../i18n/I18nProvider';

export function HomePage() {
  const { t } = useI18n();
  return (
    <>
      <section className="hero">
        <div className="hero-copy">
          <p className="kicker">{t('home.kicker')}</p>
          <h1>{t('home.title')}</h1>
          <p className="lede">{t('home.lede')}</p>
          <div className="hero-actions">
            {/* Upload is the primary input (user feedback: people rarely have the text at hand): /restore opens on the
                photo tab, with sample plates for anyone without a photo. e2e/samples.spec.ts asserts the file input. */}
            <Link className="btn btn-primary" to="/restore" data-testid="cta-upload">
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                <circle cx="12" cy="13" r="3.5" />
              </svg>
              {t('home.ctaUpload')}
            </Link>
            <a
              className="btn btn-ghost"
              href="#samples"
              data-testid="cta-samples"
              onClick={(e) => {
                const el = document.getElementById('samples');
                if (!el) return;
                e.preventDefault();
                const smooth = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
                el.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
                // Move focus to the gallery heading so keyboard and screen-reader users land there too.
                el.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
              }}
            >
              {t('home.ctaSamples')}
            </a>
            <Link className="hero-link" to="/learn">
              {t('home.ctaLearn')} →
            </Link>
          </div>
        </div>
        <EvolutionHero />
      </section>
      <Frieze />
      <SampleGallery />
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
