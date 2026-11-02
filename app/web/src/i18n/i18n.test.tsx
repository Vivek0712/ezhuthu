import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { Layout } from '../components/Layout';
import { renderApp } from '../test/render';
import { I18nProvider } from './I18nProvider';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthProvider';
import { en, ta } from './strings';

describe('strings', () => {
  it('has a non-empty Tamil string for every English key', () => {
    for (const k of Object.keys(en) as (keyof typeof en)[]) {
      expect(ta[k], k).toBeTruthy();
    }
    expect(Object.keys(ta).sort()).toEqual(Object.keys(en).sort());
  });
  it('actually translates UI text (Tamil strings contain Tamil script)', () => {
    const tamil = /[஀-௿]/;
    const untranslated = (Object.keys(en) as (keyof typeof en)[]).filter(
      (k) => !tamil.test(ta[k]) && !['about.builtWith', 'lang.toggle', 'test.cer', 'test.ece', 'restore.script.iso', 'learn.of', 'read.experimentalOther' /* the English half of the bilingual label */, 'stoneHero.decider' /* product name */].includes(k),
    );
    expect(untranslated).toEqual([]);
  });
});

describe('copy rules', () => {
  it('never says "experimental" in any user-visible English string, nor names Aivar', () => {
    const all = { ...en, ...Object.fromEntries(Object.entries(ta).filter(([, v]) => !/[\u0b80-\u0bff]/.test(v))) };
    expect(Object.entries(all).filter(([, v]) => /experimental|aivar/i.test(v)).map(([k]) => k)).toEqual([]);
  });
});

describe('language toggle', () => {
  it('defaults to English, sets <html lang>, and toggles to Tamil', async () => {
    render(
      <I18nProvider>
        <AuthProvider>
          <MemoryRouter>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<p>home</p>} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </I18nProvider>,
    );
    expect(document.documentElement.lang).toBe('en');
    expect(screen.getAllByText('Practice').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByTestId('lang-toggle'));
    expect(document.documentElement.lang).toBe('ta');
    expect(screen.getAllByText('பயிற்சி').length).toBeGreaterThan(0);
    expect(window.localStorage.getItem('ezhuthu.lang.v2')).toBe('ta');
  });
  it('ignores a language stored under the old key', () => {
    window.localStorage.setItem('ezhuthu.lang', 'ta');
    render(<I18nProvider><p>x</p></I18nProvider>);
    expect(document.documentElement.lang).toBe('en');
  });
  it('shows the mock-mode banner in development', () => {
    renderApp(
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<p>home</p>} />
        </Route>
      </Routes>,
    );
    expect(screen.getByTestId('mock-banner')).toBeInTheDocument();
  });
});
