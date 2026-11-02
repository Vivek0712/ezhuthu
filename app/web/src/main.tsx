import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import '@fontsource/noto-sans-tamil/400.css';
import '@fontsource/noto-sans-tamil/600.css';
import '@fontsource/noto-serif-tamil/500.css';
import '@fontsource/noto-serif-tamil/700.css';
import '@fontsource/noto-sans-brahmi/400.css';
import '@fontsource/noto-sans-grantha/400.css';
import '@fontsource/fraunces/600.css';
import '@fontsource/fraunces/600-italic.css';
import '@fontsource/instrument-sans/400.css';
import '@fontsource/instrument-sans/400-italic.css';
import '@fontsource/instrument-sans/600.css';
import '@fontsource/instrument-sans/700.css';
// Design system first (design/README.md, "For the app team"): tokens, then the bridge onto the app's names.
import '../../../design/tokens/tokens.css';
import '../../../design/tokens/app-compat.css';
import './styles/app.css';
import { AppRoutes } from './App';
import { AuthProvider } from './auth/AuthProvider';
import { I18nProvider } from './i18n/I18nProvider';
import { isMockMode, loadRuntimeConfig } from './lib/runtimeConfig';

async function start() {
  await loadRuntimeConfig();
  if (isMockMode()) {
    const { worker } = await import('./mocks/browser');
    await worker.start({ onUnhandledRequest: 'bypass', quiet: true });
  }
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </AuthProvider>
      </I18nProvider>
    </StrictMode>,
  );
}

void start();
