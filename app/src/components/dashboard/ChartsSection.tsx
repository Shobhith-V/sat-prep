import type { DashboardData } from '../../lib/stats';
import { ChartCard } from './ChartCard';
import { TopicBarChart, AccuracyBarChart } from './charts';

export function ChartsSection({ data }: { data: DashboardData }) {
  const sectionsHaveData = data.sections.some((s) => s.attempts > 0);
  const difficultiesHaveData = data.difficulties.some((d) => d.attempts > 0);

  return (
    <section>
      <div className="dash-section-head">
        <div>
          <div className="dash-eyebrow">Trends</div>
          <h2 className="dash-section-title">Accuracy breakdown</h2>
        </div>
      </div>
      <div className="dash-charts">
        <ChartCard
          title="Accuracy by topic"
          hasData={data.topicChart.length > 0}
          emptyTitle="No topics yet"
          emptyMessage="Answer questions to see which topics you're strong in."
        >
          <TopicBarChart data={data.topicChart} />
        </ChartCard>

        <ChartCard
          title="Reading vs. Math"
          hasData={sectionsHaveData}
          emptyTitle="No section data"
          emptyMessage="Practice both sections to compare them."
        >
          <AccuracyBarChart data={data.sections} />
        </ChartCard>

        <ChartCard
          title="By difficulty"
          hasData={difficultiesHaveData}
          emptyTitle="No difficulty data"
          emptyMessage="A mixed session fills this in across easy, medium, and hard."
        >
          <AccuracyBarChart data={data.difficulties} />
        </ChartCard>
      </div>
    </section>
  );
}
