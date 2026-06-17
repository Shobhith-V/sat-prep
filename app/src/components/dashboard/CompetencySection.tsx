import { useNavigate } from 'react-router-dom';
import { BAND_COLOR, BAND_LABEL, type TopicStat } from '../../lib/stats';
import { topicLabel } from '../../lib/taxonomy';
import { startTopicDrill } from './startTopicDrill';

function CompetencyCard({ stat }: { stat: TopicStat }) {
  const navigate = useNavigate();
  const attempted = stat.attempts > 0;
  const color = BAND_COLOR[stat.band];

  return (
    <button
      className="dash-comp"
      style={{ ['--band' as string]: color, ['--band-text' as string]: attempted ? color : undefined }}
      onClick={() => startTopicDrill(navigate, stat)}
      title={`Drill ${topicLabel(stat.topic)}`}
    >
      <div className="dash-comp-topic">{topicLabel(stat.topic)}</div>
      <div className="dash-comp-row">
        <span className="dash-comp-acc">{attempted ? `${stat.accuracy}%` : '—'}</span>
        <span className="dash-comp-meta">
          {attempted ? `${stat.correct}/${stat.attempts}` : BAND_LABEL.none}
        </span>
      </div>
      <div className="dash-comp-track">
        <div
          className="dash-comp-fill"
          style={{ width: `${attempted ? stat.accuracy : 0}%`, background: color }}
        />
      </div>
    </button>
  );
}

export function CompetencySection({ topics }: { topics: TopicStat[] }) {
  return (
    <section>
      <div className="dash-section-head">
        <div>
          <div className="dash-eyebrow">Skill map</div>
          <h2 className="dash-section-title">Competency by topic</h2>
        </div>
        <span className="dash-list-meta">Tap a topic to drill it</span>
      </div>
      <div className="dash-grid">
        {topics.map((stat) => <CompetencyCard key={stat.topic} stat={stat} />)}
      </div>
    </section>
  );
}
