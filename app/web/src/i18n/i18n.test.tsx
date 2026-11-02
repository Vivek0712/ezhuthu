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
      (k) => !tamil.test(ta[k]) && !['about.builtWith', 'lang.toggle', 'test.cer', 'test.ece', 'restore.script.iso', 'learn.of', 'read.experimentalOther' /* the English half of the bilingual label */].includes(k),
    );
    expect(untranslated).toEqual([]);
  });
});

describe('language toggle', () => {
  it('defaults to Tamil, sets <html lang>, and toggles to English', async () => {
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
    expect(document.documentElement.lang).toBe('ta');
    expect(screen.getAllByText('கற்க').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByTestId('lang-toggle'));
    expect(document.documentElement.lang).toBe('en');
    expect(screen.getAllByText('Learn').length).toBeGreaterThan(0);
    expect(window.localStorage.getItem('ezhuthu.lang')).toBe('en');
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
