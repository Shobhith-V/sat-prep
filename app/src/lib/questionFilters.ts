/**
 * questionFilters.ts — pure question-bank filtering and availability counts.
 *
 * No React, no Supabase. The Practice Setup page (and the adaptive engine in
 * the next phase) compose these to decide what a session can contain.
 */
import type { Question, SectionFilter, DifficultyFilter } from '../types';

export interface SessionFilters {
  section: SectionFilter;       // 'reading' | 'math' | 'both'
  difficulty: DifficultyFilter; // 'easy' | 'medium' | 'hard' | 'mixed'
  topic?: string;
  subtopic?: string;
}

export function filterBySection(qs: Question[], section: SectionFilter): Question[] {
  return section === 'both' ? qs : qs.filter((q) => q.section === section);
}

export function filterByDifficulty(qs: Question[], difficulty: DifficultyFilter): Question[] {
  return difficulty === 'mixed' ? qs : qs.filter((q) => q.difficulty === difficulty);
}

export function filterByTopic(qs: Question[], topic?: string): Question[] {
  return topic ? qs.filter((q) => q.topic === topic) : qs;
}

export function filterBySubtopic(qs: Question[], subtopic?: string): Question[] {
  return subtopic ? qs.filter((q) => q.subtopic === subtopic) : qs;
}

/** Apply all active filters in sequence. */
export function applyFilters(qs: Question[], f: SessionFilters): Question[] {
  let r = filterBySection(qs, f.section);
  r = filterByDifficulty(r, f.difficulty);
  r = filterByTopic(r, f.topic);
  r = filterBySubtopic(r, f.subtopic);
  return r;
}

/** Total questions matching the filters. */
export function countAvailableQuestions(qs: Question[], f: SessionFilters): number {
  return applyFilters(qs, f).length;
}

/** Matching questions the student has NOT attempted yet. */
export function countUnseenQuestions(
  qs: Question[],
  f: SessionFilters,
  seenIds: Set<string>,
): number {
  return applyFilters(qs, f).filter((q) => !seenIds.has(q.id)).length;
}

/** Distinct topics present for a section (for the Topic Drill dropdown). */
export function availableTopics(qs: Question[], section: SectionFilter): string[] {
  const pool = filterBySection(qs, section);
  return Array.from(new Set(pool.map((q) => q.topic)));
}

/** Distinct subtopics present for a topic (optionally within a section). */
export function availableSubtopics(
  qs: Question[],
  topic: string,
  section: SectionFilter = 'both',
): string[] {
  const pool = filterByTopic(filterBySection(qs, section), topic);
  return Array.from(new Set(pool.map((q) => q.subtopic))).sort();
}
