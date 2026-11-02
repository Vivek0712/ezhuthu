import { useRef, useState, type MouseEvent } from 'react';
import { Link } from 'react-router-dom';
import { Pipeline } from '../components/Pipeline';
import { MiniDrill } from '../components/practice/MiniDrill';
import { SessionCards } from '../components/practice/SessionCards';
import { StoneHero } from '../components/StoneHero';
import { useI18n } from '../i18n/I18nProvider';
import { newSeed } from '../practice/engine';

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

/** Home: the stone hero, then practice (with a question to answer right here), how it works, and a word for scholars. */
export function HomePage() {
  const { t } = useI18n();
  const ctaRef = useRef<HTMLDivElement>(null);
  const [seed] = useState(newSeed);
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
              {/* One primary call to action: answer a real question on this page. */}
              <a className="btn btn-primary" href="#practice" data-testid="cta-practice" onClick={jumpTo('practice')}>
                {t('home2.ctaPractice')}
              </a>
              <Link className="btn btn-ghost" to="/restore" data-testid="cta-upload">
                <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                  <circle cx="12" cy="13" r="3.5" />
                </svg>
                {t('home.ctaUpload')}
              </Link>
              <a className="hero-link" href="#how" data-testid="cta-how" onClick={jumpTo('how')}>
                {t('home2.ctaHow')} ↓
              </a>
            </div>
          </div>
        </section>
        <StoneHero ctaRef={ctaRef} />
      </div>

      <section id="practice" className="home-section home-practice" aria-labelledby="practice-title" data-testid="home-practice">
        <header className="section-head">
          <p className="kicker">{t('home2.practiceKicker')}</p>
          <h2 id="practice-title" tabIndex={-1}>
            {t('home2.practiceTitle')}
          </h2>
          <p className="lede">{t('home2.practiceLede')}</p>
        </header>
        <div className="home-practice-grid">
          <div className="try-panel leaf" aria-labelledby="try-title">
            <h3 id="try-title" className="try-title">
              {t('home2.tryTitle')}
            </h3>
            <MiniDrill seed={seed} />
          </div>
          <SessionCards />
        </div>
      </section>

      <section id="how" className="home-section" aria-labelledby="how-title" data-testid="home-how">
        <header className="section-head">
          <p className="kicker">{t('home2.howKicker')}</p>
          <h2 id="how-title" tabIndex={-1}>
            {t('home2.howTitle')}
          </h2>
          <p className="lede">{t('home2.howLede')}</p>
        </header>
        <Pipeline />
        <p>
          <Link className="btn btn-ghost" to="/how-it-works" data-testid="how-more">
            {t('home2.howMore')} →
          </Link>
        </p>
      </section>

      <section id="scholars" className="home-section scholars" aria-labelledby="scholars-title" data-testid="scholars">
        <h2 id="scholars-title" tabIndex={-1}>
          {t('home2.scholarsTitle')}
        </h2>
        <p>{t('home2.scholarsBody')}</p>
        <p className="audience-links">
          <Link to="/benchmark" data-testid="scholars-benchmark">
            {t('home2.scholarsBench')} →
          </Link>
          <Link to="/restore">{t('home2.scholarsRestore')} →</Link>
          <Link to="/review">{t('nav.review')} →</Link>
        </p>
      </section>
    </>
  );
}
