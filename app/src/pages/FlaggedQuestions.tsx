import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useFlaggedQuestions } from '../hooks/useFlaggedQuestions';
import { FullPageSpinner } from '../components/ui/Spinner';
import { ReviewCard } from '../components/results/ReviewCard';
import '../components/results/results.css';

type Filter = 'all' | 'correct' | 'incorrect';

export function FlaggedQuestions() {
  const { loading, items } = useFlaggedQuestions();
  const navigate = useNavigate();
  const [filter, setFilter] = useState<Filter>('all');

  if (loading) return <FullPageSpinner />;

  const counts: Record<Filter, number> = {
    all: items.length,
    correct: items.filter((i) => i.response.isCorrect).length,
    incorrect: items.filter((i) => !i.response.isCorrect).length,
  };

  const visible = items.filter((i) => {
    if (filter === 'correct') return i.response.isCorrect;
    if (filter === 'incorrect') return !i.response.isCorrect;
    return true;
  });

  return (
    <div className="res">
      <header>
        <h1>Flagged questions</h1>
        <p className="text-muted">
          Questions you marked to revisit. Review them, then drill the weak topics from your dashboard.
        </p>
      </header>

      {items.length === 0 ? (
        <div className="res-card res-empty">
          <p>You haven’t flagged any questions yet.</p>
          <p className="text-muted">Tap ☆ Flag during a session to save a question here.</p>
          <button className="btn btn-primary mt-4" onClick={() => navigate('/practice/setup')}>
            Start practice
          </button>
        </div>
      ) : (
        <>
          <div className="res-filters">
            {(['all', 'correct', 'incorrect'] as Filter[]).map((f) => (
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
              <p className="res-empty">No flagged questions in this filter.</p>
            ) : (
              visible.map((item, i) => (
                <ReviewCard
                  key={item.question.id}
                  question={item.question}
                  response={item.response}
                  number={i + 1}
                />
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}
