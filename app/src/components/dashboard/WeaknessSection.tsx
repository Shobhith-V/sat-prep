import { useNavigate } from 'react-router-dom';
import { BAND_COLOR, type TopicStat } from '../../lib/stats';
import { topicLabel } from '../../lib/taxonomy';
import { EmptyState } from './EmptyState';
import { startTopicDrill } from './startTopicDrill';

function TopicList({ title, topics }: { title: string; topics: TopicStat[] }) {
  const navigate = useNavigate();
  return (
    <div className="dash-list-card">
      <div className="dash-chart-title">{title}</div>
      <ul className="dash-list">
        {topics.map((t) => (
          <li key={t.topic} className="dash-list-row">
            <button onClick={() => startTopicDrill(navigate, t)} title="Drill this topic">
              <span className="dash-list-name">{topicLabel(t.topic)}</span>
              <span className="dash-list-meta">{t.correct}/{t.attempts}</span>
              <span className="dash-list-acc" style={{ color: BAND_COLOR[t.band] }}>
                {t.accuracy}%
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function WeaknessSection({
  weakest, strongest, isEmpty,
}: { weakest: TopicStat[]; strongest: TopicStat[]; isEmpty: boolean }) {
  return (
    <section>
      <div className="dash-section-head">
        <div>
          <div className="dash-eyebrow">Focus</div>
          <h2 className="dash-section-title">Where to spend your time</h2>
        </div>
      </div>

      {isEmpty ? (
        <div className="dash-list-card">
          <EmptyState
            icon="🎯"
            title="No focus areas yet"
            message="Once you’ve answered some questions, your weakest and strongest topics show up here to guide practice."
          />
        </div>
      ) : (
        <div className="dash-weakness">
          <TopicList title="Needs work" topics={weakest} />
          <TopicList title="Strongest" topics={strongest} />
        </div>
      )}
    </section>
  );
}
