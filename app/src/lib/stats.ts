/**
 * stats.ts — pure dashboard aggregation.
 *
 * Every dashboard calculation lives here as a pure function (no React, no
 * Supabase). Components and the useDashboardData hook only call these.
 * This keeps the logic unit-testable and the components dumb.
 */
import type { AttemptRow, CompetencyRow, SessionRow } from './queries';
import { ALL_TOPICS, topicSection } from './taxonomy';
import type { Section } from '../types';

// ── Competency bands ────────────────────────────────────────────────────────

export type Band = 'none' | 'low' | 'mid' | 'high';

/** Single source of truth for the red/yellow/green/grey thresholds. */
export function bandOf(accuracy: number, attempts: number): Band {
  if (attempts <= 0) return 'none';
  if (accuracy < 50) return 'low';
  if (accuracy <= 75) return 'mid';
  return 'high';
}

export const BAND_COLOR: Record<Band, string> = {
  none: '#cbd5e1', // grey  — never attempted
  low: '#ef4444', // red   — < 50%
  mid: '#eab308', // yellow— 50–75%
  high: '#22c55e', // green — > 75%
};

export const BAND_LABEL: Record<Band, string> = {
  none: 'Unexplored',
  low: 'Needs work',
  mid: 'Developing',
  high: 'Strong',
};

export function pct(correct: number, attempts: number): number {
  return attempts > 0 ? Math.round((correct / attempts) * 100) : 0;
}

// ── Headline metrics ────────────────────────────────────────────────────────

export interface DashboardMetrics {
  totalAttempted: number;
  overallAccuracy: number;
  readingAccuracy: number;
  mathAccuracy: number;
  sessions: number;
  streak: number;
  flaggedCount: number;
}

function sectionAccuracy(attempts: AttemptRow[], section: Section): number {
  const rows = attempts.filter((a) => a.section === section);
  const correct = rows.filter((a) => a.is_correct).length;
  return pct(correct, rows.length);
}

export function computeMetrics(
  attempts: AttemptRow[],
  sessions: SessionRow[],
): DashboardMetrics {
  const correct = attempts.filter((a) => a.is_correct).length;
  const flaggedQuestionIds = new Set(
    attempts.filter((a) => a.flagged).map((a) => a.question_id),
  );
  return {
    totalAttempted: attempts.length,
    overallAccuracy: pct(correct, attempts.length),
    readingAccuracy: sectionAccuracy(attempts, 'reading'),
    mathAccuracy: sectionAccuracy(attempts, 'math'),
    sessions: sessions.length,
    streak: currentStreak(sessions.map((s) => s.started_at)),
    flaggedCount: flaggedQuestionIds.size,
  };
}

// ── Streak (consecutive practice days up to today) ──────────────────────────

function dayKey(d: Date): string {
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

/**
 * Number of consecutive calendar days, ending today or yesterday, that have at
 * least one practice. A gap of more than one day breaks the streak (returns 0
 * if the most recent practice is older than yesterday).
 */
export function currentStreak(dates: string[], today: Date = new Date()): number {
  if (dates.length === 0) return 0;

  const days = new Set(dates.map((iso) => dayKey(new Date(iso))));

  // Walk backward from today; if today is empty but yesterday isn't, start there.
  const cursor = new Date(today);
  if (!days.has(dayKey(cursor))) {
    cursor.setDate(cursor.getDate() - 1);
    if (!days.has(dayKey(cursor))) return 0; // last practice older than yesterday
  }

  let streak = 0;
  while (days.has(dayKey(cursor))) {
    streak += 1;
    cursor.setDate(cursor.getDate() - 1);
  }
  return streak;
}

// ── Section & difficulty accuracy (for charts) ──────────────────────────────

export interface NamedAccuracy {
  key: string;
  label: string;
  accuracy: number;
  attempts: number;
  correct: number;
}

export function sectionBreakdown(attempts: AttemptRow[]): NamedAccuracy[] {
  return (['reading', 'math'] as Section[]).map((section) => {
    const rows = attempts.filter((a) => a.section === section);
    const correct = rows.filter((a) => a.is_correct).length;
    return {
      key: section,
      label: section === 'reading' ? 'Reading & Writing' : 'Math',
      accuracy: pct(correct, rows.length),
      attempts: rows.length,
      correct,
    };
  });
}

export function difficultyBreakdown(attempts: AttemptRow[]): NamedAccuracy[] {
  const order = ['easy', 'medium', 'hard'] as const;
  return order.map((difficulty) => {
    const rows = attempts.filter((a) => a.difficulty === difficulty);
    const correct = rows.filter((a) => a.is_correct).length;
    return {
      key: difficulty,
      label: difficulty[0].toUpperCase() + difficulty.slice(1),
      accuracy: pct(correct, rows.length),
      attempts: rows.length,
      correct,
    };
  });
}

// ── Topic competency (cards, charts, weak/strong) ───────────────────────────

export interface TopicStat {
  topic: string;
  section: Section | 'both';
  attempts: number;
  correct: number;
  accuracy: number;
  band: Band;
}

/**
 * Aggregate competency rows up to the topic level and merge with the full
 * taxonomy so never-attempted topics appear as grey/unexplored.
 */
export function topicStats(competency: CompetencyRow[]): TopicStat[] {
  const byTopic = new Map<string, { attempts: number; correct: number }>();
  for (const row of competency) {
    const acc = byTopic.get(row.topic) ?? { attempts: 0, correct: 0 };
    acc.attempts += row.attempts;
    acc.correct += row.correct;
    byTopic.set(row.topic, acc);
  }

  return ALL_TOPICS.map((topic) => {
    const agg = byTopic.get(topic) ?? { attempts: 0, correct: 0 };
    const accuracy = pct(agg.correct, agg.attempts);
    return {
      topic,
      section: topicSection(topic),
      attempts: agg.attempts,
      correct: agg.correct,
      accuracy,
      band: bandOf(accuracy, agg.attempts),
    };
  });
}

/**
 * Order for the skill-map grid:
 *   1. weakest attempted first (red+yellow, ascending accuracy)
 *   2. then unexplored (grey)
 *   3. then strongest attempted last (green, descending accuracy)
 */
export function sortForGrid(stats: TopicStat[]): TopicStat[] {
  const rank = (s: TopicStat) => (s.band === 'none' ? 1 : s.band === 'high' ? 2 : 0);
  return [...stats].sort((a, b) => {
    const ra = rank(a);
    const rb = rank(b);
    if (ra !== rb) return ra - rb;
    if (ra === 2) return b.accuracy - a.accuracy; // strongest: high → higher
    if (ra === 0) return a.accuracy - b.accuracy; // weakest: low → lowest first
    return b.attempts - a.attempts; // unexplored tie-break (all 0): stable
  });
}

export function weakestTopics(stats: TopicStat[], n = 5): TopicStat[] {
  return stats
    .filter((s) => s.attempts > 0)
    .sort((a, b) => a.accuracy - b.accuracy || b.attempts - a.attempts)
    .slice(0, n);
}

export function strongestTopics(stats: TopicStat[], n = 5): TopicStat[] {
  return stats
    .filter((s) => s.attempts > 0)
    .sort((a, b) => b.accuracy - a.accuracy || b.attempts - a.attempts)
    .slice(0, n);
}

/** Attempted topics only, for the topic accuracy bar chart. */
export function topicChartData(stats: TopicStat[]): TopicStat[] {
  return stats
    .filter((s) => s.attempts > 0)
    .sort((a, b) => a.accuracy - b.accuracy);
}

// ── Mastery distribution (hero signature strip) ─────────────────────────────

export interface MasterySegment {
  band: Band;
  count: number;
}

export function masteryDistribution(stats: TopicStat[]): MasterySegment[] {
  const counts: Record<Band, number> = { none: 0, low: 0, mid: 0, high: 0 };
  for (const s of stats) counts[s.band] += 1;
  // High → low for a "mastered first" reading of the strip.
  return (['high', 'mid', 'low', 'none'] as Band[]).map((band) => ({
    band,
    count: counts[band],
  }));
}

// ── Top-level composition ───────────────────────────────────────────────────

export interface DashboardData {
  metrics: DashboardMetrics;
  sections: NamedAccuracy[];
  difficulties: NamedAccuracy[];
  topics: TopicStat[];        // full, grid-sorted
  topicChart: TopicStat[];    // attempted only
  weakest: TopicStat[];
  strongest: TopicStat[];
  mastery: MasterySegment[];
  isEmpty: boolean;           // no attempts yet
}

export function buildDashboard(
  attempts: AttemptRow[],
  competency: CompetencyRow[],
  sessions: SessionRow[],
): DashboardData {
  const stats = topicStats(competency);
  const metrics = computeMetrics(attempts, sessions);
  return {
    metrics,
    sections: sectionBreakdown(attempts),
    difficulties: difficultyBreakdown(attempts),
    topics: sortForGrid(stats),
    topicChart: topicChartData(stats),
    weakest: weakestTopics(stats),
    strongest: strongestTopics(stats),
    mastery: masteryDistribution(stats),
    isEmpty: metrics.totalAttempted === 0,
  };
}
