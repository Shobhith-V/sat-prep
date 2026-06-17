import { useEffect, useRef, useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSession } from '../context/SessionContext';
import { useQuestionBank } from '../hooks/useQuestionBank';
import { fetchCompetency, fetchAttemptedQuestionIds } from '../lib/queries';
import { selectQuestions } from '../lib/adaptive';
import { isCorrectAnswer } from '../lib/scoring';
import { topicLabel } from '../lib/taxonomy';
import { FullPageSpinner } from '../components/ui/Spinner';
import { QuestionView } from '../components/practice/QuestionView';
import { SessionTimer } from '../components/practice/SessionTimer';
import '../components/practice/session.css';

export function PracticeSession() {
  const { config, state, start, answer, toggleFlag, next, complete } = useSession();
  const { user } = useAuth();
  const { bank, loading: bankLoading } = useQuestionBank();
  const navigate = useNavigate();

  const [draft, setDraft] = useState('');
  const building = useRef(false);

  // Build the session once the bank + user are ready (runs once per session).
  useEffect(() => {
    if (!config || !user || bankLoading) return;
    if (state.status === 'active' || state.status === 'complete') return;
    if (building.current) return;
    building.current = true;
    (async () => {
      try {
        const [competency, ids] = await Promise.all([
          fetchCompetency(user.id),
          fetchAttemptedQuestionIds(user.id),
        ]);
        const questions = selectQuestions({
          bank, config, competency, seenIds: new Set(ids),
        });
        start(questions);
      } catch {
        const questions = selectQuestions({ bank, config });
        start(questions);
      } finally {
        building.current = false;
      }
    })();
  }, [config, user, bankLoading, state.status, bank, start]);

  // Reset the answer draft whenever the question changes.
  useEffect(() => { setDraft(''); }, [state.index]);

  if (!config) return <Navigate to="/practice/setup" replace />;
  if (state.status === 'complete') return <Navigate to="/practice/results" replace />;
  if (bankLoading || state.status !== 'active') return <FullPageSpinner />;

  if (state.questions.length === 0) {
    return (
      <div className="container-narrow stack">
        <h1>No questions matched</h1>
        <p className="text-muted">Try different filters for this session.</p>
        <button className="btn btn-primary" onClick={() => navigate('/practice/setup')}>
          Back to setup
        </button>
      </div>
    );
  }

  const total = state.questions.length;
  const q = state.questions[state.index];
  const isLast = state.index === total - 1;
  const flagged = state.responses[q.id]?.flagged ?? false;
  const canProceed = draft.trim().length > 0;

  function handleNext() {
    if (!canProceed) return;
    answer(q.id, draft, isCorrectAnswer(q, draft));
    if (isLast) {
      complete();
      navigate('/practice/results');
    } else {
      next();
    }
  }

  return (
    <div className="sess">
      <div className="sess-bar">
        <span className="sess-counter">Question {state.index + 1} of {total}</span>
        <div className="sess-progress" aria-hidden>
          <div className="sess-progress-fill" style={{ width: `${((state.index) / total) * 100}%` }} />
        </div>
        {state.startedAt && <SessionTimer startedAt={state.startedAt} />}
      </div>

      <div className="sess-card">
        <div className="sess-card-head">
          <div className="sess-tags">
            <span className="sess-tag">{q.section === 'reading' ? 'Reading & Writing' : 'Math'}</span>
            <span className="sess-tag-sep">·</span>
            <span className="sess-tag">{topicLabel(q.topic)}</span>
            <span className="sess-tag-sep">·</span>
            <span className={`badge badge-${q.difficulty}`}>{q.difficulty}</span>
          </div>
          <button
            type="button"
            className={`sess-flag${flagged ? ' is-flagged' : ''}`}
            aria-pressed={flagged}
            onClick={() => toggleFlag(q.id)}
          >
            {flagged ? '★ Flagged' : '☆ Flag'}
          </button>
        </div>

        <QuestionView question={q} draft={draft} onChange={setDraft} />

        <div className="sess-footer">
          <button className="btn btn-primary sess-next" onClick={handleNext} disabled={!canProceed}>
            {isLast ? 'Finish' : 'Next'}
          </button>
        </div>
      </div>
    </div>
  );
}
