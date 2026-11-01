import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { AuthProvider } from '../auth/AuthProvider';
import { I18nProvider, type Lang } from '../i18n/I18nProvider';

export function renderApp(ui: ReactElement, { lang = 'en', route = '/' }: { lang?: Lang; route?: string } = {}) {
  return render(
    <I18nProvider initial={lang}>
      <AuthProvider>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthProvider>
    </I18nProvider>,
  );
}
