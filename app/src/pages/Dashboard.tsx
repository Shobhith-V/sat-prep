import { useAuth } from '../context/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';
import { FullPageSpinner } from '../components/ui/Spinner';
import { DashboardHero } from '../components/dashboard/DashboardHero';
import { MetricsGrid } from '../components/dashboard/MetricsGrid';
import { ChartsSection } from '../components/dashboard/ChartsSection';
import { WeaknessSection } from '../components/dashboard/WeaknessSection';
import { CompetencySection } from '../components/dashboard/CompetencySection';
import '../components/dashboard/dashboard.css';

export function Dashboard() {
  const { profile, user } = useAuth();
  const { loading, error, data } = useDashboardData();

  if (loading) return <FullPageSpinner />;

  if (error) {
    return (
      <div className="container-narrow stack">
        <h1>Something went wrong</h1>
        <p className="text-muted">{error}</p>
        <button className="btn btn-outline" onClick={() => window.location.reload()}>
          Try again
        </button>
      </div>
    );
  }

  if (!data) return null;

  const name = profile?.name?.trim() || user?.email?.split('@')[0] || 'there';

  return (
    <div className="dash">
      <DashboardHero name={name} mastery={data.mastery} isEmpty={data.isEmpty} />
      <MetricsGrid metrics={data.metrics} />
      <ChartsSection data={data} />
      <WeaknessSection weakest={data.weakest} strongest={data.strongest} isEmpty={data.isEmpty} />
      <CompetencySection topics={data.topics} />
    </div>
  );
}
