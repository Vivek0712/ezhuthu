import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Layout } from './components/Layout';
import { RequireAuth } from './components/RequireAuth';
import { AboutPage } from './pages/AboutPage';
import { AuthCallbackPage } from './pages/AuthCallbackPage';
import { HomePage } from './pages/HomePage';
import { HowItWorksPage } from './pages/HowItWorksPage';
import { LearnPage } from './pages/LearnPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { PracticeHubPage } from './pages/PracticeHubPage';
import { PracticeSessionPage, TrialPage } from './pages/PracticeSessionPage';
import { ProgressPage } from './pages/ProgressPage';
import { RestorePage } from './pages/RestorePage';
import { ReviewPage } from './pages/ReviewPage';
import { TestPage } from './pages/TestPage';

/** Old paths (Learn, Test) before the positioning-C renames: keep links, bookmarks and state working. */
function Moved({ to }: { to: string }) {
  const loc = useLocation();
  return <Navigate replace to={{ pathname: to, search: loc.search, hash: loc.hash }} state={loc.state} />;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="practice" element={<PracticeHubPage />} />
        <Route path="practice/guided" element={<LearnPage />} />
        <Route path="practice/trial" element={<TrialPage />} />
        <Route path="practice/:kind" element={<PracticeSessionPage />} />
        <Route path="how-it-works" element={<HowItWorksPage />} />
        <Route path="learn" element={<Moved to="/practice" />} />
        <Route path="progress" element={<ProgressPage />} />
        <Route path="restore" element={<RestorePage />} />
        <Route path="test" element={<Moved to="/benchmark" />} />
        {/* Public results; the runner inside the page asks for sign-in. */}
        <Route path="benchmark" element={<TestPage />} />
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
