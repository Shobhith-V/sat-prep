/**
 * Supabase read queries for the dashboard.
 *
 * Each function selects only the columns the dashboard needs and is scoped to
 * one student (RLS also enforces this server-side). Aggregation happens in
 * stats.ts — these functions only fetch.
 */
import { supabase } from './supabase';
import type {
  QuestionAttempt, TopicCompetency, PracticeSession,
} from '../types';

/** Slim attempt row — only the fields used by dashboard aggregation. */
export type AttemptRow = Pick<
  QuestionAttempt,
  'question_id' | 'topic' | 'subtopic' | 'section' | 'difficulty'
  | 'is_correct' | 'flagged' | 'attempted_at'
>;

export type CompetencyRow = Pick<
  TopicCompetency,
  'topic' | 'subtopic' | 'attempts' | 'correct' | 'accuracy'
>;

export type SessionRow = Pick<
  PracticeSession,
  'started_at' | 'section' | 'total_questions' | 'score'
>;

export async function fetchAttempts(studentId: string): Promise<AttemptRow[]> {
  const { data, error } = await supabase
    .from('question_attempts')
    .select('question_id,topic,subtopic,section,difficulty,is_correct,flagged,attempted_at')
    .eq('student_id', studentId);
  if (error) throw error;
  return (data ?? []) as AttemptRow[];
}

export async function fetchCompetency(studentId: string): Promise<CompetencyRow[]> {
  const { data, error } = await supabase
    .from('topic_competency')
    .select('topic,subtopic,attempts,correct,accuracy')
    .eq('student_id', studentId);
  if (error) throw error;
  return (data ?? []) as CompetencyRow[];
}

export async function fetchSessions(studentId: string): Promise<SessionRow[]> {
  const { data, error } = await supabase
    .from('practice_sessions')
    .select('started_at,section,total_questions,score')
    .eq('student_id', studentId)
    .order('started_at', { ascending: false });
  if (error) throw error;
  return (data ?? []) as SessionRow[];
}

/** Just the question_ids the student has attempted (for unseen-count + adaptive exclusion). */
export async function fetchAttemptedQuestionIds(studentId: string): Promise<string[]> {
  const { data, error } = await supabase
    .from('question_attempts')
    .select('question_id')
    .eq('student_id', studentId);
  if (error) throw error;
  return (data ?? []).map((r) => (r as { question_id: string }).question_id);
}

/** Flagged attempt row — includes the student's answer for the review page. */
export type FlaggedAttemptRow = AttemptRow & { student_answer: string };

/**
 * Flagged attempts, most recent first, for the Flagged Questions page.
 * Includes student_answer so the page can render the full review and split
 * flagged-correct vs flagged-incorrect.
 */
export async function fetchFlaggedAttempts(studentId: string): Promise<FlaggedAttemptRow[]> {
  const { data, error } = await supabase
    .from('question_attempts')
    .select('question_id,topic,subtopic,section,difficulty,is_correct,flagged,student_answer,attempted_at')
    .eq('student_id', studentId)
    .eq('flagged', true)
    .order('attempted_at', { ascending: false });
  if (error) throw error;
  return (data ?? []) as FlaggedAttemptRow[];
}
