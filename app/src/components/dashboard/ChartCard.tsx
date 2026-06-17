import type { ReactNode } from 'react';
import { EmptyState } from './EmptyState';

/**
 * Chart container that shows an informative empty state when there's no data,
 * rather than rendering empty axes.
 */
export function ChartCard({
  title,
  hasData,
  emptyTitle,
  emptyMessage,
  children,
}: {
  title: string;
  hasData: boolean;
  emptyTitle: string;
  emptyMessage: string;
  children: ReactNode;
}) {
  return (
    <div className="dash-chart-card">
      <div className="dash-chart-title">{title}</div>
      <div className="dash-chart-body">
        {hasData ? children : <EmptyState icon="📈" title={emptyTitle} message={emptyMessage} />}
      </div>
    </div>
  );
}
