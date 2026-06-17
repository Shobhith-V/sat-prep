import type { ReactNode } from 'react';
import type { DashboardMetrics } from '../../lib/stats';

function MetricCard({
  label, value, unit, sub,
}: { label: string; value: ReactNode; unit?: string; sub?: string }) {
  return (
    <div className="dash-metric">
      <div className="dash-metric-label">{label}</div>
      <div className="dash-metric-value">
        {value}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {sub && <div className="dash-metric-sub">{sub}</div>}
    </div>
  );
}

export function MetricsGrid({ metrics }: { metrics: DashboardMetrics }) {
  const hasData = metrics.totalAttempted > 0;
  return (
    <section>
      <div className="dash-section-head">
        <div>
          <div className="dash-eyebrow">Overview</div>
          <h2 className="dash-section-title">Your numbers</h2>
        </div>
      </div>
      <div className="dash-metrics">
        <MetricCard label="Questions" value={metrics.totalAttempted} sub="attempted" />
        <MetricCard
          label="Overall"
          value={hasData ? metrics.overallAccuracy : '—'}
          unit={hasData ? '%' : undefined}
          sub="accuracy"
        />
        <MetricCard
          label="Reading"
          value={metrics.readingAccuracy > 0 || hasData ? metrics.readingAccuracy : '—'}
          unit="%"
          sub="accuracy"
        />
        <MetricCard
          label="Math"
          value={metrics.mathAccuracy > 0 || hasData ? metrics.mathAccuracy : '—'}
          unit="%"
          sub="accuracy"
        />
        <MetricCard label="Sessions" value={metrics.sessions} sub="completed" />
        <MetricCard
          label="Streak"
          value={metrics.streak}
          sub={metrics.streak === 1 ? 'day' : 'days'}
        />
        <MetricCard label="Flagged" value={metrics.flaggedCount} sub="to review" />
      </div>
    </section>
  );
}
