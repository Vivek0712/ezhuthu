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
            {/* Points at the restore form, which exists today. When the upload/OCR flow (PR #34) is on main, this becomes
                "Upload a photo" (home.ctaUpload) and e2e/samples.spec.ts asserts the file input. */}
            <Link className="btn btn-primary" to="/restore" data-testid="cta-restore">
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 20h4L19 9l-4-4L4 16z" />
                <path d="M13.5 6.5l4 4" />
              </svg>
              {t('home.ctaRestore')}
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
