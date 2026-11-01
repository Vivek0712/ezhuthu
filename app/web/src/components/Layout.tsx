import { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthProvider';
import { useI18n } from '../i18n/I18nProvider';
import type { MessageKey } from '../i18n/strings';

const LINKS: [string, MessageKey][] = [
  ['/learn', 'nav.learn'],
  ['/restore', 'nav.restore'],
  ['/progress', 'nav.progress'],
  ['/test', 'nav.test'],
  ['/review', 'nav.review'],
  ['/about', 'nav.about'],
];

export function Layout() {
  const { t, toggle } = useI18n();
  const auth = useAuth();
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);

  const links = LINKS.map(([to, key]) => (
    <NavLink key={to} to={to} className={({ isActive }) => (isActive ? 'active' : undefined)}>
      {t(key)}
    </NavLink>
  ));

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
          <NavLink to="/" className="brand" aria-label={`${t('app.name')} · ${t('nav.home')}`}>
            <span className="brand-ta" lang="ta">
              எழுத்து
            </span>
            <span className="brand-brahmi" aria-hidden="true">
              𑀏𑀵𑀼𑀢𑁆𑀢𑀼
            </span>
            <span className="brand-en" lang="en">
              Ezhuthu
            </span>
          </NavLink>
          <nav className="nav" aria-label="primary">
            {links}
          </nav>
          <button className="btn btn-ghost btn-small lang-btn" type="button" onClick={toggle} aria-label={t('lang.toggleLabel')} data-testid="lang-toggle">
            {t('lang.toggle')}
          </button>
          {auth.user ? (
            <button className="btn btn-ghost btn-small auth-btn" type="button" onClick={auth.signOut} title={`${t('auth.signedInAs')} ${auth.user.name}`}>
              {t('auth.signOut')}
            </button>
          ) : (
            <button className="btn btn-ghost btn-small auth-btn" type="button" onClick={() => void auth.signIn()} disabled={!auth.configured}>
              {t('auth.signIn')}
            </button>
          )}
          <button
            className="btn btn-ghost btn-small menu-btn"
            type="button"
            aria-expanded={open}
            aria-controls="drawer"
            onClick={() => setOpen((o) => !o)}
            data-testid="menu-toggle"
          >
            {t('nav.menu')}
          </button>
        </div>
        {open && (
          <div className="drawer" id="drawer">
            <nav className="wrap" aria-label="mobile">
              {links}
              {auth.user ? (
                <button className="btn btn-ghost" type="button" onClick={auth.signOut}>
                  {t('auth.signOut')}
                </button>
              ) : (
                <button className="btn btn-ghost" type="button" onClick={() => void auth.signIn()} disabled={!auth.configured}>
                  {t('auth.signIn')}
                </button>
              )}
            </nav>
          </div>
        )}
      </header>
      <main id="main" tabIndex={-1}>
        <div className="wrap">
          <Outlet />
        </div>
      </main>
      <footer className="site">
        <div className="wrap">
          <span>{t('about.builtWith')}</span>
          <span>
            {t('about.data1')}{' '}
            <a href="https://dharmalekha.info" rel="noreferrer" target="_blank">
              DHARMA
            </a>
          </span>
        </div>
      </footer>
    </div>
  );
}
