/**
 * results.ts — pure results aggregation + persistence-row preparation.
 *
 * No React, no Supabase calls. The Results page calls these to render the
 * summary and to build the payload for the record_session RPC.
 */
import type { Question, Response, PracticeConfig } from '../types';
import { acceptedForms } from './scoring';

// ── Score + band ────────────────────────────────────────────────────────────

export interface Score {
  correct: number;
  incorrect: number;
  total: number;
  accuracy: number; // 0..100
}

export function computeScore(
  questions: Question[],
  responses: Record<string, Response>,
): Score {
  const total = questions.length;
  const correct = questions.filter((q) => responses[q.id]?.isCorrect).length;
  return {
    correct,
    incorrect: total - correct,
    total,
    accuracy: total > 0 ? Math.round((correct / total) * 100) : 0,
  };
}

export type BandKey = 'excellent' | 'strong' | 'developing' | 'needs_practice';

export interface PerformanceBand {
  key: BandKey;
  label: string;
  color: string;
}

export function performanceBand(accuracy: number): PerformanceBand {
  if (accuracy >= 90) return { key: 'excellent', label: 'Excellent', color: '#22c55e' };
  if (accuracy >= 75) return { key: 'strong', label: 'Strong', color: '#16a34a' };
  if (accuracy >= 50) return { key: 'developing', label: 'Developing', color: '#eab308' };
  return { key: 'needs_practice', label: 'Needs Practice', color: '#ef4444' };
}

export function elapsedSeconds(startedAt: string | null, completedAt: string | null): number {
  if (!startedAt || !completedAt) return 0;
  return Math.max(0, Math.round((new Date(completedAt).getTime() - new Date(startedAt).getTime()) / 1000));
}

export function formatDuration(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// ── Per-topic performance (this session only) ───────────────────────────────

export interface TopicPerformance {
  topic: string;
  attempts: number;
  correct: number;
  accuracy: number;
}

export function computeTopicPerformance(
  questions: Question[],
  responses: Record<string, Response>,
): TopicPerformance[] {
  const byTopic = new Map<string, { attempts: number; correct: number }>();
  for (const q of questions) {
    const agg = byTopic.get(q.topic) ?? { attempts: 0, correct: 0 };
    agg.attempts += 1;
    if (responses[q.id]?.isCorrect) agg.correct += 1;
    byTopic.set(q.topic, agg);
  }
  return Array.from(byTopic.entries()).map(([topic, agg]) => ({
    topic,
    attempts: agg.attempts,
    correct: agg.correct,
    accuracy: Math.round((agg.correct / agg.attempts) * 100),
  }));
}

export interface SessionSummary {
  score: Score;
  band: PerformanceBand;
  topicPerformance: TopicPerformance[];
  strongest: TopicPerformance[]; // this session
  weakest: TopicPerformance[];   // this session
}

export function buildSessionSummary(
  questions: Question[],
  responses: Record<string, Response>,
): SessionSummary {
  const score = computeScore(questions, responses);
  const topicPerformance = computeTopicPerformance(questions, responses);
  const strongest = [...topicPerformance]
    .sort((a, b) => b.accuracy - a.accuracy || b.attempts - a.attempts)
    .slice(0, 3);
  const weakest = [...topicPerformance]
    .sort((a, b) => a.accuracy - b.accuracy || b.attempts - a.attempts)
    .slice(0, 3);
  return { score, band: performanceBand(score.accuracy), topicPerformance, strongest, weakest };
}

// ── Persistence rows (for record_session RPC) ───────────────────────────────

/** Canonical stored answer: MC letter, or first accepted numeric form. */
export function canonicalAnswer(q: Question): string {
  return Array.isArray(q.correct_answer) ? q.correct_answer[0] : q.correct_answer;
}

export interface AttemptInput {
  question_id: string;
  topic: string;
  subtopic: string;
  section: string;
  difficulty: string;
  student_answer: string;
  correct_answer: string;
  is_correct: boolean;
  flagged: boolean;
}

export interface SessionInput {
  section: string;
  total_questions: number;
  score: number;
  started_at: string;
  completed_at: string;
}

export function prepareAttemptRows(
  questions: Question[],
  responses: Record<string, Response>,
): AttemptInput[] {
  return questions.map((q) => {
    const r = responses[q.id];
    return {
      question_id: q.id,
      topic: q.topic,
      subtopic: q.subtopic,
      section: q.section,
      difficulty: q.difficulty,
      student_answer: r?.answer ?? '',
      correct_answer: canonicalAnswer(q),
      is_correct: r?.isCorrect ?? false,
      flagged: r?.flagged ?? false,
    };
  });
}

export function prepareSessionRow(
  config: PracticeConfig,
  score: Score,
  startedAt: string,
  completedAt: string,
): SessionInput {
  return {
    section: config.section,
    total_questions: score.total,
    score: score.correct,
    started_at: startedAt,
    completed_at: completedAt,
  };
}

/** Display string for a question's correct answer (review UI). */
export function correctAnswerLabel(q: Question): string {
  if (q.question_type === 'multiple_choice') {
    const letter = String(q.correct_answer);
    const text = q.choices?.[letter as keyof typeof q.choices];
    return text ? `${letter} · ${text.replace(/\s+/g, ' ').trim()}` : letter;
  }
  return acceptedForms(q).join(' or ');
}

/** Display string for the student's answer (review UI). */
export function studentAnswerLabel(q: Question, response?: Response): string {
  if (!response || response.answer.trim() === '') return 'No answer';
  if (q.question_type === 'multiple_choice') {
    const letter = response.answer;
    const text = q.choices?.[letter as keyof typeof q.choices];
    return text ? `${letter} · ${text.replace(/\s+/g, ' ').trim()}` : letter;
  }
  return response.answer;
}
