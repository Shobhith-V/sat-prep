import { Link } from 'react-router-dom';
import { BAND_COLOR, BAND_LABEL, type MasterySegment } from '../../lib/stats';

/**
 * Hero = the page's thesis. Instead of a vanity number, it leads with the
 * mastery strip: the proportion of the SAT skill map in each competency band.
 * For a new user this is fully "unexplored" — which doubles as the invitation.
 */
export function DashboardHero({
  name,
  mastery,
  isEmpty,
}: {
  name: string;
  mastery: MasterySegment[];
  isEmpty: boolean;
}) {
  const total = mastery.reduce((sum, s) => sum + s.count, 0) || 1;

  return (
    <section className="dash-hero">
      <div className="dash-hero-top">
        <div>
          <h1 className="dash-hello">
            {isEmpty ? `Welcome, ${name}` : `Welcome back, ${name}`}
          </h1>
          <p className="dash-hero-sub">
            {isEmpty
              ? 'Take your first session to start mapping your strengths.'
              : 'Here’s where you stand across the SAT skill map.'}
          </p>
        </div>
        <Link to="/practice/setup" className="dash-cta">
          Start practice →
        </Link>
      </div>

      <div className="dash-mastery">
        <div className="dash-mastery-bar" role="img" aria-label="Mastery distribution across topics">
          {mastery.map((seg) => (
            seg.count > 0 && (
              <div
                key={seg.band}
                className="dash-mastery-seg"
                style={{ width: `${(seg.count / total) * 100}%`, background: BAND_COLOR[seg.band] }}
                title={`${BAND_LABEL[seg.band]}: ${seg.count}`}
              />
            )
          ))}
        </div>
        <div className="dash-mastery-legend">
          {mastery.map((seg) => (
            <span key={seg.band} className="dash-legend-item">
              <span className="dash-legend-dot" style={{ background: BAND_COLOR[seg.band] }} />
              {BAND_LABEL[seg.band]} · {seg.count}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
