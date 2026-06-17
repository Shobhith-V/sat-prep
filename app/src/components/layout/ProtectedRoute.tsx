import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FullPageSpinner } from '../ui/Spinner';

/** Gate for authenticated routes. Redirects unauthenticated users to /login. */
export function ProtectedRoute() {
  const { user, loading } = useAuth();

  if (loading) return <FullPageSpinner />;
  return user ? <Outlet /> : <Navigate to="/login" replace />;
}
