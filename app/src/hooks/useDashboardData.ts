import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { fetchAttempts, fetchCompetency, fetchSessions } from '../lib/queries';
import { buildDashboard, type DashboardData } from '../lib/stats';

interface State {
  loading: boolean;
  error: string | null;
  data: DashboardData | null;
}

/**
 * Loads the three per-student tables in parallel and runs the pure
 * buildDashboard() aggregation. Re-fetches when the user changes.
 */
export function useDashboardData(): State {
  const { user } = useAuth();
  const [state, setState] = useState<State>({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    setState({ loading: true, error: null, data: null });

    (async () => {
      try {
        const [attempts, competency, sessions] = await Promise.all([
          fetchAttempts(user.id),
          fetchCompetency(user.id),
          fetchSessions(user.id),
        ]);
        if (cancelled) return;
        setState({ loading: false, error: null, data: buildDashboard(attempts, competency, sessions) });
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof Error ? err.message : 'Could not load your data.';
        setState({ loading: false, error: message, data: null });
      }
    })();

    return () => { cancelled = true; };
  }, [user]);

  return state;
}
