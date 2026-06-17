import { Navigate, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { FullPageSpinner } from '../ui/Spinner';

/** Gate for public routes (login/signup). Sends authenticated users to the dashboard. */
export function PublicRoute() {
  const { user, loading } = useAuth();

  if (loading) return <FullPageSpinner />;
  return user ? <Navigate to="/dashboard" replace /> : <Outlet />;
}
