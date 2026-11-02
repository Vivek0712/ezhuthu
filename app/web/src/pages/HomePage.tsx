import { useRef, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { EvolutionHero } from '../components/EvolutionHero';
import { Frieze } from '../components/Frieze';
import { SampleGallery } from '../components/SampleGallery';
import { StoneHero } from '../components/StoneHero';
import { useI18n } from '../i18n/I18nProvider';

/** Scroll to an in-page section and move focus to its heading (keyboard and screen-reader users land there too). */
function jumpTo(id: string) {
  return (e: MouseEvent<HTMLAnchorElement>) => {
    const el = document.getElementById(id);
    if (!el) return;
    e.preventDefault();
    const smooth = !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    el.scrollIntoView({ behavior: smooth ? 'smooth' : 'auto', block: 'start' });
    el.querySelector<HTMLElement>('h2')?.focus({ preventScroll: true });
  };
}

export function HomePage() {
  const { t } = useI18n();
  const ctaRef = useRef<HTMLDivElement>(null);
  return (
    <>
      <div className="home-hero">
        <section className="hero hero-c">
          <div className="hero-copy">
            <p className="kicker">{t('home.kicker')}</p>
            <h1>{t('home.title')}</h1>
          </div>
          <div className="hero-copy">
            <p className="lede">{t('home.lede')}</p>
            <div className="hero-actions" ref={ctaRef} data-testid="hero-actions">
              {/* Upload is the primary input (people rarely have the text at hand): /restore opens on the photo tab,
                  with sample plates for anyone without a photo. e2e/samples.spec.ts asserts the file input. */}
              <Link className="btn btn-primary" to="/restore" data-testid="cta-upload">
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                  <circle cx="12" cy="13" r="3.5" />
                </svg>
                {t('home.ctaUpload')}
              </Link>
              <a className="btn btn-ghost" href="#samples" data-testid="cta-samples" onClick={jumpTo('samples')}>
                {t('home.ctaSamples')}
              </a>
              <a className="btn btn-ghost" href="#scholars" data-testid="cta-scholars" onClick={jumpTo('scholars')}>
                {t('home.ctaScholars')}
              </a>
              <Link className="hero-link" to="/practice">
                {t('home.ctaLearn')} →
              </Link>
            </div>
          </div>
        </section>
        <StoneHero ctaRef={ctaRef} />
      </div>
      <Frieze />
      <section className="evo-section" aria-labelledby="evo-title">
        <h2 id="evo-title">{t('home.evolutionTitle')}</h2>
        <EvolutionHero />
      </section>
      <SampleGallery />
      <div className="grid grid-2 audience">
        <section aria-labelledby="students-title">
          <h2 id="students-title">{t('home.stepsTitle')}</h2>
          <ol className="steps">
            <li>{t('home.step1')}</li>
            <li>{t('home.step2')}</li>
            <li>{t('home.step3')}</li>
            <li>{t('home.step4')}</li>
          </ol>
          <Link className="btn btn-ghost" to="/practice">
            {t('home.ctaLearn')}
          </Link>
        </section>
        <section id="scholars" aria-labelledby="scholars-title" data-testid="scholars">
          <h2 id="scholars-title" tabIndex={-1}>
            {t('home.scholarsTitle')}
          </h2>
          <ol className="steps">
            <li>{t('home.scholar1')}</li>
            <li>{t('home.scholar2')}</li>
            <li>{t('home.scholar3')}</li>
            <li>{t('home.scholar4')}</li>
          </ol>
          <p className="audience-links">
            <Link to="/restore">{t('nav.restore')}</Link>
            <Link to="/review">{t('nav.review')}</Link>
            <Link to="/benchmark">{t('nav.test')}</Link>
          </p>
        </section>
      </div>
    </>
  );
}
