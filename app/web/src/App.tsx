import { Route, Routes } from 'react-router-dom';
import { Layout } from './components/Layout';
import { RequireAuth } from './components/RequireAuth';
import { AboutPage } from './pages/AboutPage';
import { AuthCallbackPage } from './pages/AuthCallbackPage';
import { HomePage } from './pages/HomePage';
import { LearnPage } from './pages/LearnPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ProgressPage } from './pages/ProgressPage';
import { RestorePage } from './pages/RestorePage';
import { ReviewPage } from './pages/ReviewPage';
import { TestPage } from './pages/TestPage';

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="learn" element={<LearnPage />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="restore" element={<RestorePage />} />
        <Route
          path="test"
          element={
            <RequireAuth>
              <TestPage />
            </RequireAuth>
          }
        />
        <Route
          path="review"
          element={
            <RequireAuth expert>
              <ReviewPage />
            </RequireAuth>
          }
        />
        <Route path="about" element={<AboutPage />} />
        <Route path="auth/callback" element={<AuthCallbackPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
