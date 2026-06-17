import { useEffect, useMemo, useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import {
  buildSessionSummary, prepareAttemptRows, prepareSessionRow,
  elapsedSeconds, formatDuration,
} from '../lib/results';
import { topicLabel } from '../lib/taxonomy';
import { BAND_COLOR, bandOf } from '../lib/stats';
import { ReviewCard } from '../components/results/ReviewCard';
import '../components/results/results.css';

type Filter = 'all' | 'correct' | 'incorrect' | 'flagged';
type SaveState = 'idle' | 'saving' | 'saved' | 'error';

export function Results() {
  const { state, config, markPersisted } = useSession();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [filter, setFilter] = useState<Filter>('all');
  const [saveState, setSaveState] = useState<SaveState>(state.persisted ? 'saved' : 'idle');
  const persistRef = useRef(false);

  const summary = useMemo(
    () => buildSessionSummary(state.questions, state.responses),
    [state.questions, state.responses],
  );

  // Persist exactly once (guarded by ref + context flag).
  useEffect(() => {
    if (state.status !== 'complete' || !config || !user) return;
    if (state.persisted || persistRef.current) return;
    if (!isSupabaseConfigured) { setSaveState('error'); return; }

    persistRef.current = true;
    setSaveState('saving');

    (async () => {
      const sessionRow = prepareSessionRow(
        config, summary.score, state.startedAt ?? '', state.completedAt ?? '',
      );
      const attemptRows = prepareAttemptRows(state.questions, state.responses);
      const { error } = await supabase.rpc('record_session', {
        p_session: sessionRow,
        p_attempts: attemptRows,
      });
      if (error) {
        setSaveState('error');
        persistRef.current = false; // allow a retry on re-render
      } else {
        markPersisted();
        setSaveState('saved');
      }
    })();
  }, [state, config, user, summary, markPersisted]);

  // No completed session in memory (e.g. after a refresh) → nothing to show.
  if (state.status !== 'complete' || state.questions.length === 0) {
    return <Navigate to="/dashboard" replace />;
  }

  const { score, band } = summary;
  const timeTaken = formatDuration(elapsedSeconds(state.startedAt, state.completedAt));
  const flaggedCount = state.questions.filter((q) => state.responses[q.id]?.flagged).length;

  const counts: Record<Filter, number> = {
    all: score.total,
    correct: score.correct,
    incorrect: score.incorrect,
    flagged: flaggedCount,
  };

  const visible = state.questions.filter((q) => {
    const r = state.responses[q.id];
    if (filter === 'correct') return r?.isCorrect;
    if (filter === 'incorrect') return !r?.isCorrect;
    if (filter === 'flagged') return r?.flagged;
    return true;
  });

  function practiceAgain() {
    if (config) navigate('/practice/setup', { state: { prefill: config } });
    else navigate('/practice/setup');
  }

  return (
    <div className="res">
      {/* ── Headline summary ─────────────────────────────────────── */}
      <section className="res-hero" style={{ background: band.color }}>
        <div className="res-band">{band.label}</div>
        <div className="res-accuracy">{score.accuracy}%</div>
        <div className="res-stats">
          <div>
            <div className="res-stat-label">Score</div>
            <div className="res-stat-value">{score.correct}/{score.total}</div>
          </div>
          <div>
            <div className="res-stat-label">Correct</div>
            <div className="res-stat-value">{score.correct}</div>
          </div>
          <div>
            <div className="res-stat-label">Incorrect</div>
            <div className="res-stat-value">{score.incorrect}</div>
          </div>
          <div>
            <div className="res-stat-label">Time</div>
            <div className="res-stat-value">{timeTaken}</div>
          </div>
          <div>
            <div className="res-stat-label">Completed</div>
            <div className="res-stat-value">{score.total}</div>
          </div>
        </div>
      </section>

      <div className={`res-save is-${saveState}`}>
        {saveState === 'saving' && 'Saving your results…'}
        {saveState === 'saved' && '✓ Results saved'}
        {saveState === 'error' && (isSupabaseConfigured
          ? 'Couldn’t save results. Your review is still available below.'
          : 'Results not saved (Supabase not configured).')}
      </div>

      {/* ── This-session summary ─────────────────────────────────── */}
      <section className="res-summary">
        <div className="res-card">
          <div className="res-card-title">Strongest this session</div>
          {summary.strongest.map((t) => (
            <div key={t.topic} className="res-topic-row">
              <span>{topicLabel(t.topic)}</span>
              <span className="res-topic-acc" style={{ color: BAND_COLOR[bandOf(t.accuracy, t.attempts)] }}>
                {t.accuracy}% ({t.correct}/{t.attempts})
              </span>
            </div>
          ))}
        </div>
        <div className="res-card">
          <div className="res-card-title">Weakest this session</div>
          {summary.weakest.map((t) => (
            <div key={t.topic} className="res-topic-row">
              <span>{topicLabel(t.topic)}</span>
              <span className="res-topic-acc" style={{ color: BAND_COLOR[bandOf(t.accuracy, t.attempts)] }}>
                {t.accuracy}% ({t.correct}/{t.attempts})
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* ── Review ───────────────────────────────────────────────── */}
      <section>
        <div className="res-filters">
          {(['all', 'correct', 'incorrect', 'flagged'] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              className={`res-filter${filter === f ? ' is-active' : ''}`}
              onClick={() => setFilter(f)}
            >
              {f[0].toUpperCase() + f.slice(1)} ({counts[f]})
            </button>
          ))}
        </div>

        <div className="res-reviews mt-4">
          {visible.length === 0 ? (
            <p className="res-empty">No questions in this filter.</p>
          ) : (
            visible.map((q) => (
              <ReviewCard
                key={q.id}
                question={q}
                response={state.responses[q.id]}
                number={state.questions.indexOf(q) + 1}
              />
            ))
          )}
        </div>
      </section>

      {/* ── Navigation ───────────────────────────────────────────── */}
      <div className="res-nav">
        <button className="btn btn-outline" onClick={() => navigate('/dashboard')}>
          Back to dashboard
        </button>
        <button className="btn btn-primary" onClick={practiceAgain}>
          Practice again
        </button>
      </div>
    </div>
  );
}
