/**
 * The three dashboard charts (Recharts). Each is presentational: it receives
 * already-aggregated data from stats.ts and renders bars colored by competency
 * band where meaningful.
 */
import {
  BarChart, Bar, XAxis, YAxis, Cell, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';
import { BAND_COLOR, bandOf, type NamedAccuracy, type TopicStat } from '../../lib/stats';
import { topicLabel } from '../../lib/taxonomy';

const AXIS = { fontSize: 12, fill: '#64748b' };

function AccuracyTooltip({ active, payload }: {
  active?: boolean;
  payload?: Array<{ payload: { label: string; accuracy: number; attempts: number } }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div style={{
      background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8,
      padding: '6px 10px', fontSize: 12, boxShadow: '0 4px 14px rgba(15,23,42,.08)',
    }}>
      <strong>{d.label}</strong><br />
      {d.accuracy}% · {d.attempts} attempted
    </div>
  );
}

/** Topic accuracy — horizontal bars (handles many long labels), colored by band. */
export function TopicBarChart({ data }: { data: TopicStat[] }) {
  const rows = data.map((t) => ({
    label: topicLabel(t.topic),
    accuracy: t.accuracy,
    attempts: t.attempts,
    band: t.band,
  }));
  return (
    <ResponsiveContainer width="100%" height={Math.max(180, rows.length * 30)}>
      <BarChart layout="vertical" data={rows} margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid horizontal={false} stroke="#f1f5f9" />
        <XAxis type="number" domain={[0, 100]} tick={AXIS} unit="%" />
        <YAxis type="category" dataKey="label" width={128} tick={AXIS} />
        <Tooltip content={<AccuracyTooltip />} cursor={{ fill: '#f8fafc' }} />
        <Bar dataKey="accuracy" radius={[0, 4, 4, 0]} barSize={16}>
          {rows.map((r) => <Cell key={r.label} fill={BAND_COLOR[r.band]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Generic vertical bar chart for section / difficulty breakdowns. */
export function AccuracyBarChart({ data }: { data: NamedAccuracy[] }) {
  const rows = data.filter((d) => d.attempts > 0);
  return (
    <ResponsiveContainer width="100%" height={200}>
      <BarChart data={rows} margin={{ left: -16, right: 8, top: 8, bottom: 4 }}>
        <CartesianGrid vertical={false} stroke="#f1f5f9" />
        <XAxis dataKey="label" tick={AXIS} />
        <YAxis domain={[0, 100]} tick={AXIS} unit="%" />
        <Tooltip content={<AccuracyTooltip />} cursor={{ fill: '#f8fafc' }} />
        <Bar dataKey="accuracy" radius={[4, 4, 0, 0]} barSize={48}>
          {rows.map((r) => <Cell key={r.key} fill={BAND_COLOR[bandOf(r.accuracy, r.attempts)]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
