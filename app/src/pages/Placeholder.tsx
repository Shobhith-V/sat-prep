/**
 * Temporary placeholder pages for routes not yet implemented.
 * Replaced with real implementations in later phases:
 *   - PracticeSetup/Session → Practice phase
 *   - Results               → Results phase
 */
import { Link } from 'react-router-dom';

function Stub({ title, note }: { title: string; note: string }) {
  return (
    <div className="container-narrow stack">
      <h1>{title}</h1>
      <p className="text-muted">{note}</p>
      <div className="flex gap-4 mt-4">
        <Link className="btn btn-outline" to="/dashboard">Dashboard</Link>
        <Link className="btn btn-outline" to="/practice/setup">Practice</Link>
      </div>
    </div>
  );
}

export const PracticeSetup = () => <Stub title="Practice Setup" note="Mode, section, difficulty, and count selection — coming in the Practice phase." />;
export const PracticeSession = () => <Stub title="Practice Session" note="One-question-at-a-time flow — coming in the Practice phase." />;
export const Results = () => <Stub title="Results" note="Score breakdown and explanations — coming in the Results phase." />;
