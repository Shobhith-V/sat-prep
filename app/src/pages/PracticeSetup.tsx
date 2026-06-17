import { useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type {
  PracticeConfig, PracticeMode, SectionFilter, DifficultyFilter,
} from '../types';
import { useQuestionBank } from '../hooks/useQuestionBank';
import { usePracticeProfile } from '../hooks/usePracticeProfile';
import { useSession } from '../context/SessionContext';
import {
  availableTopics, availableSubtopics, countAvailableQuestions,
  countUnseenQuestions, type SessionFilters,
} from '../lib/questionFilters';
import { READING_TOPICS, MATH_TOPICS, topicLabel, topicSection } from '../lib/taxonomy';
import { BAND_COLOR } from '../lib/stats';
import { SegmentedControl } from '../components/practice/SegmentedControl';
import { FullPageSpinner } from '../components/ui/Spinner';
import '../components/practice/practice.css';

const MODES: { value: PracticeMode; name: string; desc: string }[] = [
  { value: 'adaptive', name: 'Adaptive', desc: 'Focus on your weaker topics, chosen from your competency.' },
  { value: 'random', name: 'Random', desc: 'A random mix from your selected filters.' },
  { value: 'topic_drill', name: 'Topic Drill', desc: 'Practice one specific topic or subtopic.' },
];

const COUNT_PRESETS = [5, 10, 20, 40];
const MIN_COUNT = 1;
const MAX_COUNT = 100;

export function PracticeSetup() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setConfig } = useSession();
  const { bank, loading: bankLoading } = useQuestionBank();
  const { seenIds, weakest, loading: profileLoading } = usePracticeProfile();

  // Prefill from a dashboard "drill this topic" click or "Practice again".
  const prefill = (location.state as { prefill?: Partial<PracticeConfig> } | null)?.prefill;
  const prefillPreset = prefill?.count && COUNT_PRESETS.includes(prefill.count);

  const [mode, setMode] = useState<PracticeMode>(prefill?.mode ?? 'adaptive');
  const [section, setSection] = useState<SectionFilter>(prefill?.section ?? 'both');
  const [difficulty, setDifficulty] = useState<DifficultyFilter>(prefill?.difficulty ?? 'mixed');
  const [count, setCount] = useState<number>(prefillPreset ? prefill!.count! : 10);
  const [isCustom, setIsCustom] = useState<boolean>(Boolean(prefill?.count) && !prefillPreset);
  const [customCount, setCustomCount] = useState<number>(prefill?.count ?? 10);
  const [topic, setTopic] = useState<string>(prefill?.topic ?? '');
  const [subtopic, setSubtopic] = useState<string>(prefill?.subtopic ?? '');

  // Topic & subtopic option lists, derived from the bank (only what exists).
  const { readingOpts, mathOpts } = useMemo(() => {
    if (!bank.length) return { readingOpts: [] as string[], mathOpts: [] as string[] };
    const r = new Set(availableTopics(bank, 'reading'));
    const m = new Set(availableTopics(bank, 'math'));
    return {
      readingOpts: READING_TOPICS.filter((t) => r.has(t)),
      mathOpts: MATH_TOPICS.filter((t) => m.has(t)),
    };
  }, [bank]);

  const subtopicOpts = useMemo(
    () => (topic && bank.length ? availableSubtopics(bank, topic, topicSection(topic)) : []),
    [bank, topic],
  );

  // Effective filters for the current configuration.
  const effectiveSection: SectionFilter =
    mode === 'topic_drill' && topic ? topicSection(topic) : section;
  const filters: SessionFilters = {
    section: effectiveSection,
    difficulty,
    topic: mode === 'topic_drill' ? topic || undefined : undefined,
    subtopic: mode === 'topic_drill' ? subtopic || undefined : undefined,
  };

  const clampedCustom = Math.min(MAX_COUNT, Math.max(MIN_COUNT, customCount || 0));
  const requestedCount = isCustom ? clampedCustom : count;

  const available = bank.length ? countAvailableQuestions(bank, filters) : 0;
  const unseen = bank.length ? countUnseenQuestions(bank, filters, seenIds) : 0;

  const needsTopic = mode === 'topic_drill' && !topic;
  const customInvalid = isCustom && (customCount < MIN_COUNT || customCount > MAX_COUNT);
  const canStart = !bankLoading && available > 0 && !needsTopic && !customInvalid;

  function handleTopicChange(value: string) {
    setTopic(value);
    setSubtopic(''); // reset subtopic when topic changes
  }

  function handleStart() {
    if (!canStart) return;
    const config: PracticeConfig = {
      mode,
      section: effectiveSection,
      difficulty,
      count: Math.min(requestedCount, available),
      topic: mode === 'topic_drill' ? topic : undefined,
      subtopic: mode === 'topic_drill' ? subtopic || undefined : undefined,
    };
    setConfig(config);
    navigate('/practice/session');
  }

  if (bankLoading) return <FullPageSpinner />;

  return (
    <div className="ps">
      <header className="ps-head">
        <h1>Start a practice session</h1>
        <p>Pick a mode and filters. You can change these any time.</p>
      </header>

      <div className="ps-grid">
        {/* ── Left: configuration ─────────────────────────────────── */}
        <div className="ps-config">
          <div className="ps-field">
            <span className="ps-label">Mode</span>
            <div className="ps-modes">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  className={`ps-mode${mode === m.value ? ' is-active' : ''}`}
                  aria-pressed={mode === m.value}
                  onClick={() => setMode(m.value)}
                >
                  <div className="ps-mode-name">{m.name}</div>
                  <div className="ps-mode-desc">{m.desc}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Section is implied by the chosen topic in Topic Drill. */}
          {mode !== 'topic_drill' && (
            <SegmentedControl<SectionFilter>
              label="Section"
              value={section}
              onChange={setSection}
              options={[
                { value: 'both', label: 'Both' },
                { value: 'reading', label: 'Reading' },
                { value: 'math', label: 'Math' },
              ]}
            />
          )}

          {mode === 'topic_drill' && (
            <div className="ps-field">
              <span className="ps-label">Topic</span>
              <div className="ps-drill">
                <select
                  className="ps-select"
                  value={topic}
                  onChange={(e) => handleTopicChange(e.target.value)}
                >
                  <option value="">Choose a topic…</option>
                  <optgroup label="Reading & Writing">
                    {readingOpts.map((t) => (
                      <option key={`r-${t}`} value={t}>{topicLabel(t)}</option>
                    ))}
                  </optgroup>
                  <optgroup label="Math">
                    {mathOpts.map((t) => (
                      <option key={`m-${t}`} value={t}>{topicLabel(t)}</option>
                    ))}
                  </optgroup>
                </select>

                <select
                  className="ps-select"
                  value={subtopic}
                  onChange={(e) => setSubtopic(e.target.value)}
                  disabled={!topic || subtopicOpts.length === 0}
                >
                  <option value="">Any subtopic</option>
                  {subtopicOpts.map((s) => (
                    <option key={s} value={s}>{topicLabel(s)}</option>
                  ))}
                </select>
              </div>
            </div>
          )}

          <SegmentedControl<DifficultyFilter>
            label="Difficulty"
            value={difficulty}
            onChange={setDifficulty}
            options={[
              { value: 'mixed', label: 'Mixed' },
              { value: 'easy', label: 'Easy' },
              { value: 'medium', label: 'Medium' },
              { value: 'hard', label: 'Hard' },
            ]}
          />

          <div className="ps-field">
            <span className="ps-label">Questions</span>
            <div className="ps-chips">
              {COUNT_PRESETS.map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`ps-chip${!isCustom && count === n ? ' is-active' : ''}`}
                  onClick={() => { setIsCustom(false); setCount(n); }}
                >
                  {n}
                </button>
              ))}
              <button
                type="button"
                className={`ps-chip${isCustom ? ' is-active' : ''}`}
                onClick={() => setIsCustom(true)}
              >
                Custom
              </button>
              {isCustom && (
                <input
                  className="ps-select ps-custom"
                  type="number"
                  min={MIN_COUNT}
                  max={MAX_COUNT}
                  value={customCount}
                  onChange={(e) => setCustomCount(Number(e.target.value))}
                  aria-label="Custom question count"
                />
              )}
            </div>
            {customInvalid && (
              <span className="ps-avail-warn">Enter a number between {MIN_COUNT} and {MAX_COUNT}.</span>
            )}
          </div>
        </div>

        {/* ── Right: summary / preview ────────────────────────────── */}
        <aside className="ps-summary">
          <div className="ps-card">
            <div className={`ps-avail-count${available === 0 ? ' is-zero' : ''}`}>
              {available}
            </div>
            <div className="ps-avail-label">
              {available === 1 ? 'question available' : 'questions available'}
            </div>
            {available > 0 && (
              <div className="ps-avail-sub">{unseen} new · {available - unseen} seen</div>
            )}
            {needsTopic && (
              <p className="ps-avail-warn">Choose a topic to drill.</p>
            )}
            {!needsTopic && available === 0 && (
              <p className="ps-avail-warn">
                No questions match these filters. Try a broader difficulty or section.
              </p>
            )}
          </div>

          {mode === 'adaptive' && (
            <div className="ps-card">
              <div className="ps-preview-title">Adaptive focus</div>
              {profileLoading ? (
                <p className="ps-preview-note">Loading your profile…</p>
              ) : weakest.length > 0 ? (
                <>
                  <ul className="ps-focus-list">
                    {weakest.map((t) => (
                      <li key={t.topic} className="ps-focus-item">
                        <span className="ps-focus-dot" style={{ background: BAND_COLOR[t.band] }} />
                        {topicLabel(t.topic)} · {t.accuracy}%
                      </li>
                    ))}
                  </ul>
                  <p className="ps-preview-note">Based on your weakest topics.</p>
                </>
              ) : (
                <p className="ps-preview-note">
                  Adaptive practice will begin building your profile.
                </p>
              )}
            </div>
          )}

          <button
            className="btn btn-primary btn-block ps-start"
            onClick={handleStart}
            disabled={!canStart}
          >
            Start practice
          </button>
        </aside>
      </div>
    </div>
  );
}
