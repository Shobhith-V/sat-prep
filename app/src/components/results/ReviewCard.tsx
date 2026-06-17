import { Fragment } from 'react';
import type { Question, Response } from '../../types';
import { correctAnswerLabel, studentAnswerLabel } from '../../lib/results';
import { topicLabel } from '../../lib/taxonomy';

function renderWithBlanks(text: string) {
  const parts = text.split('[BLANK]');
  return parts.map((part, i) => (
    <Fragment key={i}>
      {part}
      {i < parts.length - 1 && <span className="q-blank">______</span>}
    </Fragment>
  ));
}

export function ReviewCard({
  question,
  response,
  number,
}: {
  question: Question;
  response?: Response;
  number: number;
}) {
  const correct = response?.isCorrect ?? false;
  const flagged = response?.flagged ?? false;
  const mark = correct ? 'var(--color-success)' : 'var(--color-error)';

  return (
    <article className="res-review" style={{ ['--mark' as string]: mark }}>
      <div className="res-review-head">
        <span className="res-qnum">Q{number}</span>
        <span className="res-status">{correct ? 'Correct' : 'Incorrect'}</span>
        <span className="sess-tag">{topicLabel(question.topic)}</span>
        <span className={`badge badge-${question.difficulty}`}>{question.difficulty}</span>
        {flagged && <span className="res-flag-badge">★ Flagged</span>}
      </div>

      <p className="res-q-text">{renderWithBlanks(question.question)}</p>

      <div className="res-answers">
        <div className={`res-answer-line ${correct ? 'correct' : 'incorrect'}`}>
          <span className="k">Your answer</span>
          <span className="v">{studentAnswerLabel(question, response)}</span>
        </div>
        {!correct && (
          <div className="res-answer-line correct">
            <span className="k">Correct answer</span>
            <span className="v">{correctAnswerLabel(question)}</span>
          </div>
        )}
      </div>

      {question.explanation && (
        <div className="res-explanation">{question.explanation}</div>
      )}
    </article>
  );
}
