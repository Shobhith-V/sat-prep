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

/**
 * Flagged attempts, for a future "Flagged Questions" page.
 * Designed now so that page can split flagged-correct vs flagged-incorrect.
 */
export async function fetchFlaggedAttempts(studentId: string): Promise<AttemptRow[]> {
  const { data, error } = await supabase
    .from('question_attempts')
    .select('question_id,topic,subtopic,section,difficulty,is_correct,flagged,attempted_at')
    .eq('student_id', studentId)
    .eq('flagged', true)
    .order('attempted_at', { ascending: false });
  if (error) throw error;
  return (data ?? []) as AttemptRow[];
}
