import type { NavigateFunction } from 'react-router-dom';
import type { TopicStat } from '../../lib/stats';
import type { PracticeConfig } from '../../types';

/**
 * Navigate to Practice Setup pre-seeded for a Topic Drill on `topic`.
 * The setup page (next phase) reads this from router location.state and
 * pre-fills mode + topic + section. Defined once so the competency cards and
 * the weak/strong lists share identical behavior.
 */
export function startTopicDrill(navigate: NavigateFunction, t: TopicStat): void {
  const prefill: Partial<PracticeConfig> = {
    mode: 'topic_drill',
    topic: t.topic,
    section: t.section === 'both' ? 'reading' : t.section,
  };
  navigate('/practice/setup', { state: { prefill } });
}
