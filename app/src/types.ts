/**
 * Shared domain types for the SAT Prep app.
 *
 * `Question` mirrors the schema produced by the extraction pipeline
 * (output/test{N}.json). The Supabase row types mirror supabase/migrations/0001_init.sql.
 */

export type Section = 'reading' | 'math';
export type Difficulty = 'easy' | 'medium' | 'hard';
export type QuestionType = 'multiple_choice' | 'numeric_response';
export type ChoiceKey = 'A' | 'B' | 'C' | 'D';

export interface Asset {
  type: 'image';
  src: string; // e.g. "assets/test4/page_010.png"
}

export type Choices = Record<ChoiceKey, string>;

/** A single SAT question from the generated dataset. */
export interface Question {
  id: string;
  test: number;
  section: Section;
  module: number;
  question_number: number;
  topic: string;
  subtopic: string;
  difficulty: Difficulty;
  question_type: QuestionType;
  question: string;
  choices: Choices | null;
  /** "A" for MC; "9" or ["1/5", ".2"] for numeric (multiple accepted forms). */
  correct_answer: string | string[];
  explanation: string | null;
  page: number;
  assets: Asset[];
}

// ── Practice session (in-memory) ────────────────────────────────────────────

export type PracticeMode = 'adaptive' | 'random' | 'topic_drill';
export type SectionFilter = Section | 'both';
export type DifficultyFilter = Difficulty | 'mixed';

export interface PracticeConfig {
  mode: PracticeMode;
  section: SectionFilter;
  difficulty: DifficultyFilter;
  count: number;
  /** Topic Drill only */
  topic?: string;
  subtopic?: string;
}

/** A student's answer to one question during a live session. */
export interface Response {
  questionId: string;
  answer: string; // chosen letter ("A") or typed numeric value
  isCorrect: boolean;
  flagged: boolean;
}

// ── Supabase row types ──────────────────────────────────────────────────────

export interface Profile {
  id: string;
  name: string;
  created_at: string;
}

export interface QuestionAttempt {
  id: string;
  student_id: string;
  question_id: string;
  topic: string;
  subtopic: string;
  section: Section;
  difficulty: Difficulty;
  student_answer: string;
  correct_answer: string;
  is_correct: boolean;
  flagged: boolean;
  attempted_at: string;
}

export interface TopicCompetency {
  id: string;
  student_id: string;
  topic: string;
  subtopic: string;
  attempts: number;
  correct: number;
  accuracy: number; // 0..100
  last_updated: string;
}

export interface PracticeSession {
  id: string;
  student_id: string;
  started_at: string;
  completed_at: string | null;
  section: SectionFilter;
  total_questions: number;
  score: number;
}
