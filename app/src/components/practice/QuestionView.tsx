import { Fragment, useState } from 'react';
import type { Question, ChoiceKey } from '../../types';

const CHOICE_KEYS: ChoiceKey[] = ['A', 'B', 'C', 'D'];

/** Renders question text, preserving line breaks and styling the [BLANK] marker. */
function QuestionText({ text }: { text: string }) {
  const parts = text.split('[BLANK]');
  return (
    <p className="q-text">
      {parts.map((part, i) => (
        <Fragment key={i}>
          {part}
          {i < parts.length - 1 && <span className="q-blank" aria-label="blank">______</span>}
        </Fragment>
      ))}
    </p>
  );
}

/** Expandable full-page source scan (graphs / tables / figures). */
function AssetPanel({ assets }: { assets: Question['assets'] }) {
  const [open, setOpen] = useState(false);
  const base = import.meta.env.BASE_URL;
  return (
    <div className="q-asset">
      <button type="button" className="q-asset-toggle" onClick={() => setOpen((o) => !o)}>
        {open ? 'Hide' : 'View'} source page
      </button>
      {open && (
        <div className="q-asset-images">
          {assets.map((a) => (
            <img key={a.src} src={`${base}${a.src}`} alt="Original test page with the figure or table" loading="lazy" />
          ))}
        </div>
      )}
    </div>
  );
}

export function QuestionView({
  question,
  draft,
  onChange,
}: {
  question: Question;
  draft: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="q-body">
      <QuestionText text={question.question} />

      {question.assets.length > 0 && <AssetPanel assets={question.assets} />}

      {question.question_type === 'multiple_choice' && question.choices ? (
        <div className="q-choices" role="radiogroup" aria-label="Answer choices">
          {CHOICE_KEYS.map((key) => {
            const text = question.choices?.[key];
            if (!text) return null;
            const selected = draft === key;
            return (
              <button
                key={key}
                type="button"
                role="radio"
                aria-checked={selected}
                className={`q-choice${selected ? ' is-selected' : ''}`}
                onClick={() => onChange(key)}
              >
                <span className="q-choice-key">{key}</span>
                <span className="q-choice-text">{text}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="q-numeric">
          <label htmlFor="numeric-answer" className="ps-label">Your answer</label>
          <input
            id="numeric-answer"
            className="ps-select"
            type="text"
            inputMode="text"
            autoComplete="off"
            placeholder="e.g. 9 or 1/5"
            value={draft}
            onChange={(e) => onChange(e.target.value)}
          />
        </div>
      )}
    </div>
  );
}
