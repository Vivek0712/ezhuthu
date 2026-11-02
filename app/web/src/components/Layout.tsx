import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import lockupColor from '../../../../design/brand/logo/lockup-horizontal-color.svg';
import lockupReversed from '../../../../design/brand/logo/lockup-horizontal-reversed.svg';
import wordmarkColor from '../../../../design/brand/logo/wordmark-ta-color.svg';
import wordmarkReversed from '../../../../design/brand/logo/wordmark-ta-reversed.svg';
import { useAuth } from '../auth/AuthProvider';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';
import { DharmaCredit } from './Feedback';

// Top nav at 1000 px and wider. Review is shown only to signed-in experts (design/ux/UX.md section 2).
const TOP: [string, MessageKey, boolean][] = [
  ['/learn', 'nav.learn', false],
  ['/restore', 'nav.restore', false],
  ['/progress', 'nav.progress', false],
  ['/test', 'nav.test', false],
  ['/review', 'nav.review', true],
  ['/about', 'nav.about', false],
];
// Bottom tabs below 1000 px; Test, About, Home, sign-in and the language live in the "More" sheet.
const TABS: [string, MessageKey, boolean, ReactNode][] = [
  ['/learn', 'nav.learn', false, <path key="i" d="M4 6c3-1.5 6-1.5 8 0v13c-2-1.5-5-1.5-8 0zM12 6c2-1.5 5-1.5 8 0v13c-3-1.5-6-1.5-8 0" />],
  ['/restore', 'nav.restore', false, <path key="i" d="M5 19 15 9M13 7l4 4M15 5l4 4-2 2-4-4z M4 20l2-1" />],
  ['/progress', 'nav.progress', false, <path key="i" d="M5 19V12M10 19V8M15 19v-5M20 19V5M3 19h18" />],
  ['/review', 'nav.review', true, <path key="i" d="M5 12.5 10 17l9-10" />],
];
const MORE: [string, MessageKey][] = [
  ['/', 'nav.home'],
  ['/test', 'nav.test'],
  ['/about', 'nav.about'],
];

function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine !== false));
  useEffect(() => {
    const up = () => setOnline(true);
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, []);
  return online;
}

export function Layout() {
  const { t, toggle } = useI18n();
  const auth = useAuth();
  const online = useOnline();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  const show = (expertOnly: boolean) => !expertOnly || auth.isExpert;
  const cls = ({ isActive }: { isActive: boolean }) => (isActive ? 'active' : undefined);

  const authButton = (extra = '') =>
    auth.user ? (
      <button className={`btn btn-ghost btn-small ${extra}`} type="button" onClick={auth.signOut} title={`${t('auth.signedInAs')} ${auth.user.name}`}>
        {t('auth.signOut')}
      </button>
    ) : (
      <button className={`btn btn-ghost btn-small ${extra}`} type="button" onClick={() => void auth.signIn()} disabled={!auth.configured}>
        {t('auth.signIn')}
      </button>
    );

  return (
    <div className="shell">
      <a className="skip" href="#main">
        {t('nav.home')} ↓
      </a>
      {auth.mock && (
        <div className="mock-banner" role="note" data-testid="mock-banner">
          <div className="wrap">{t('mock.banner')}</div>
        </div>
      )}
      <header className="topbar">
        <div className="wrap">
          <NavLink to="/" className="brand" aria-label={t('brand.home')} data-testid="brand">
            <img className="logo logo-lockup logo-on-light" src={lockupColor} alt="" width={175} height={34} />
            <img className="logo logo-lockup logo-on-dark" src={lockupReversed} alt="" width={175} height={34} />
            <img className="logo logo-wordmark logo-on-light" src={wordmarkColor} alt="" width={102} height={32} />
            <img className="logo logo-wordmark logo-on-dark" src={wordmarkReversed} alt="" width={102} height={32} />
          </NavLink>
          <nav className="nav" aria-label="primary">
            {TOP.filter(([, , x]) => show(x)).map(([to, key]) => (
              <NavLink key={to} to={to} className={cls}>
                {t(key)}
              </NavLink>
            ))}
          </nav>
          {!online && (
            <span className="chip chip-lamp" role="status" data-testid="offline">
              {t('status.offline')}
            </span>
          )}
          <button className="btn btn-ghost btn-small lang-btn" type="button" onClick={toggle} aria-label={t('lang.toggleLabel')} data-testid="lang-toggle">
            {t('lang.toggle')}
          </button>
          {authButton('auth-btn')}
        </div>
      </header>
      <main id="main" tabIndex={-1}>
        <div className="wrap">
          {/* Keyed on the path so each page change replays the entrance (.page in app.css; none under reduced motion). */}
          <div className="page" key={loc.pathname}>
            <Outlet />
          </div>
        </div>
      </main>
      <footer className="site">
        <div className="wrap">
          <span lang="en">{t('about.builtWith')}</span>
          <DharmaCredit testId="footer-credit" />
        </div>
      </footer>

      <nav className="tabbar" aria-label={t('nav.tabs')} data-testid="tabbar">
        {TABS.filter(([, , x]) => show(x)).map(([to, key, , icon]) => (
          <NavLink key={to} to={to} className={cls}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              {icon}
            </svg>
            <span>{t(key)}</span>
          </NavLink>
        ))}
        <button type="button" className={open ? 'active' : undefined} aria-expanded={open} aria-controls="more-sheet" onClick={() => setOpen((o) => !o)} data-testid="menu-toggle">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
          <span>{t('nav.more')}</span>
        </button>
      </nav>
      {open && (
        <div className="sheet" id="more-sheet">
          <nav className="wrap" aria-label="mobile">
            {MORE.map(([to, key]) => (
              <NavLink key={to} to={to} end className={cls}>
                {t(key)}
              </NavLink>
            ))}
            {authButton()}
          </nav>
        </div>
      )}
    </div>
  );
}
