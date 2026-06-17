import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { SessionProvider } from './context/SessionContext';
import { ProtectedRoute } from './components/layout/ProtectedRoute';
import { PublicRoute } from './components/layout/PublicRoute';
import { Layout } from './components/layout/Layout';
import { Login } from './pages/Login';
import { SignUp } from './pages/SignUp';
import { Dashboard } from './pages/Dashboard';
import { PracticeSetup } from './pages/PracticeSetup';
import { PracticeSession } from './pages/PracticeSession';
import { Results } from './pages/Results';
import { FlaggedQuestions } from './pages/FlaggedQuestions';

/**
 * HashRouter is used so GitHub Pages deep links (e.g. /#/practice/session)
 * resolve without server-side rewrites.
 *
 * Route tree:
 *   public  (redirect to /dashboard if already signed in)
 *     /login, /signup
 *   protected (redirect to /login if signed out) → Layout (navbar) →
 *     /dashboard, /practice/setup, /practice/session, /practice/results
 */
export default function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <SessionProvider>
        <Routes>
          <Route element={<PublicRoute />}>
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<SignUp />} />
          </Route>

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/flagged" element={<FlaggedQuestions />} />
              <Route path="/practice/setup" element={<PracticeSetup />} />
              <Route path="/practice/session" element={<PracticeSession />} />
              <Route path="/practice/results" element={<Results />} />
            </Route>
          </Route>

          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
        </SessionProvider>
      </AuthProvider>
    </HashRouter>
  );
}
