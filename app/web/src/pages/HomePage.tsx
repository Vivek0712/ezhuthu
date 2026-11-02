import { useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { AgentChips } from '../components/how/AgentChips';
import { exampleSnippet, Pipeline } from '../components/Pipeline';
import { Bi } from '../components/practice/Bi';
import { MiniDrill } from '../components/practice/MiniDrill';
import { StoneHero } from '../components/StoneHero';
import { useI18n } from '../i18n/I18nProvider';
import { useHeroT } from '../i18n/strings-hero';
import type { MessageKey } from '../i18n/strings';
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

interface Feature {
  key: 'practice' | 'restore' | 'read' | 'how';
  to: string;
  icon: ReactNode;
  /** A real micro-example: Tamil script, its English letters, and what it is. */
  ex: { ta: string; iso: string; glyph?: { text: string; cls: string } };
}

const snippet = exampleSnippet();

// Examples are real: the Tamil-Brahmi ka; the gap in the How-it-works passage (DHARMA_INSPallava00092, train);
// the opening formula of many stones; the regnal-year word.
const FEATURES: Feature[] = [
  {
    key: 'practice',
    to: '/practice',
    icon: <path d="M4 6c3-1.5 6-1.5 8 0v13c-2-1.5-5-1.5-8 0zM12 6c2-1.5 5-1.5 8 0v13c-3-1.5-6-1.5-8 0" />,
    ex: { ta: 'க', iso: 'ka', glyph: { text: '𑀓', cls: 'script-brahmi' } },
  },
  {
    key: 'restore',
    to: '/restore?tab=type',
    icon: <path d="M5 19 15 9M13 7l4 4M15 5l4 4-2 2-4-4zM4 20l2-1" />,
    ex: { ta: snippet.ta, iso: snippet.iso },
  },
  {
    key: 'read',
    to: '/restore',
    icon: (
      <>
        <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
        <circle cx="12" cy="13" r="3.5" />
      </>
    ),
    ex: { ta: 'ஸ்வஸ்தி ஶ்ரீ', iso: 'svasti śrī' },
  },
  {
    key: 'how',
    to: '/how-it-works',
    icon: <path d="M4 6h4v4H4zM16 6h4v4h-4zM10 15h4v4h-4zM8 8h8M6 10l5 5M18 10l-5 5" />,
    ex: { ta: 'யாண்டு', iso: 'yāṇṭu' },
  },
];

/**
 * Home, kept short (user feedback: the long sample gallery buried the features): the stone hero, what you can do,
 * one question to try, the pipeline in brief, and a strip for scholars.
 */
export function HomePage() {
  const { t } = useI18n();
  const ht = useHeroT();
  const ctaRef = useRef<HTMLDivElement>(null);
  const [seed] = useState(newSeed);
  const k = (f: Feature, s: 'T' | 'D' | 'Ex' | 'Cta') => t(`home3.${f.key}${s}` as MessageKey);
  return (
    <>
      <div className="home-hero">
        {/* One column: what this is (headline), what you can do (one or two plain sentences), then one primary and one
            secondary call to action, with "How it works" as a quiet link. Styles in stone-hero.css (.hh). */}
        <section className="hh hero-copy" data-testid="hero-head">
          <p className="kicker hh-kicker">{ht('hero.kicker')}</p>
          <h1 className="hh-title">{ht('hero.title')}</h1>
          <p className="lede hh-sub">{ht('hero.sub')}</p>
          <div className="hero-actions hh-actions" ref={ctaRef} data-testid="hero-actions">
            {/* One primary call to action: answer a real question on this page. */}
            <a className="btn btn-primary" href="#try" data-testid="cta-practice" onClick={jumpTo('try')}>
              {t('home2.ctaPractice')}
            </a>
            <Link className="btn btn-ghost" to="/restore" data-testid="cta-upload">
              <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 8h3l2-3h6l2 3h3v11H4z" />
                <circle cx="12" cy="13" r="3.5" />
              </svg>
              {t('home.ctaUpload')}
            </Link>
            <a className="hero-link hh-how" href="#how" data-testid="cta-how" onClick={jumpTo('how')}>
              {t('home2.ctaHow')} ↓
            </a>
          </div>
        </section>
        <StoneHero ctaRef={ctaRef} />
      </div>

      <section id="features" className="home-section" aria-labelledby="features-title" data-testid="home-features">
        <h2 id="features-title" tabIndex={-1}>
          {t('home3.featuresTitle')}
        </h2>
        <ul className="feature-grid">
          {FEATURES.map((f, i) => (
            <li key={f.key} className="feature-card" style={{ ['--i' as string]: i }} data-testid={`feature-${f.key}`}>
              <span className="pipe-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24">{f.icon}</svg>
              </span>
              <h3>
                <Link to={f.to} className="session-link" data-testid={`feature-link-${f.key}`}>
                  {k(f, 'T')}
                </Link>
              </h3>
              <p className="feature-desc">{k(f, 'D')}</p>
              <div className="feature-ex">
                {f.ex.glyph && (
                  <span className={`feature-glyph ${f.ex.glyph.cls}`} aria-hidden="true">
                    {f.ex.glyph.text} →
                  </span>
                )}
                <Bi ta={f.ex.ta} iso={f.ex.iso} taClass="script-chola" />
                <span className="pipe-ex-k">{k(f, 'Ex')}</span>
              </div>
              <span className="feature-cta" aria-hidden="true">
                {k(f, 'Cta')} →
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section id="try" className="home-section home-try" aria-labelledby="try-title" data-testid="home-practice">
        <div className="home-try-copy">
          <p className="kicker">{t('home2.practiceKicker')}</p>
          <h2 id="try-title" tabIndex={-1}>
            {t('home2.tryTitle')}
          </h2>
          <p className="lede">{t('home3.tryLede')}</p>
          <p className="audience-links">
            <Link to="/practice" data-testid="home-all-practice">
              {t('home2.tryAll')} →
            </Link>
            <Link to="/restore#samples" data-testid="home-samples-link">
              {t('home3.samplesLink')} →
            </Link>
          </p>
        </div>
        <div className="try-panel leaf">
          <MiniDrill seed={seed} />
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
        <AgentChips />
        <Pipeline />
        <Link className="btn btn-ghost" to="/how-it-works" data-testid="how-more">
          {t('home2.howMore')} →
        </Link>
      </section>

      <section id="scholars" className="home-section scholars" aria-labelledby="scholars-title" data-testid="scholars">
        <h2 id="scholars-title" tabIndex={-1}>
          {t('home2.scholarsTitle')}
        </h2>
        <p>{t('home3.scholarsNumbers')}</p>
        <p className="audience-links">
          <Link to="/benchmark" data-testid="scholars-benchmark">
            {t('home2.scholarsBench')} →
          </Link>
          <Link to="/how-it-works">{t('how.limitsTitle')} →</Link>
          <Link to="/review">{t('nav.review')} →</Link>
        </p>
      </section>
    </>
  );
}
