/**
 * Canonical SAT topic taxonomy (mirrors the extraction pipeline).
 * Used to render the full "skill map" — including topics the student has
 * never attempted (shown as grey/unexplored) — without loading the dataset.
 */
import type { Section } from '../types';

export const READING_TOPICS = [
  'words_in_context',
  'central_ideas',
  'inferences',
  'command_of_evidence',
  'text_structure',
  'rhetorical_synthesis',
  'transitions',
  'grammar',
  'boundaries',
  'form_structure_sense',
  'data_interpretation',
] as const;

export const MATH_TOPICS = [
  'linear_equations',
  'systems',
  'functions',
  'quadratics',
  'exponents',
  'geometry',
  'circles',
  'trigonometry',
  'statistics',
  'probability',
  'data_interpretation',
] as const;

/** De-duplicated master list (data_interpretation appears in both sections). */
export const ALL_TOPICS: string[] = Array.from(
  new Set<string>([...READING_TOPICS, ...MATH_TOPICS]),
);

const TOPIC_LABELS: Record<string, string> = {
  words_in_context: 'Words in Context',
  central_ideas: 'Central Ideas',
  inferences: 'Inferences',
  command_of_evidence: 'Command of Evidence',
  text_structure: 'Text Structure',
  rhetorical_synthesis: 'Rhetorical Synthesis',
  transitions: 'Transitions',
  grammar: 'Grammar',
  boundaries: 'Sentence Boundaries',
  form_structure_sense: 'Form, Structure & Sense',
  data_interpretation: 'Data Interpretation',
  linear_equations: 'Linear Equations',
  systems: 'Systems of Equations',
  functions: 'Functions',
  quadratics: 'Quadratics',
  exponents: 'Exponents',
  geometry: 'Geometry',
  circles: 'Circles',
  trigonometry: 'Trigonometry',
  statistics: 'Statistics',
  probability: 'Probability',
};

/** Human-readable label for a snake_case topic key. */
export function topicLabel(topic: string): string {
  return (
    TOPIC_LABELS[topic]
    ?? topic.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  );
}

/** Which section a topic belongs to (drives Topic Drill defaults). */
export function topicSection(topic: string): Section | 'both' {
  const inReading = (READING_TOPICS as readonly string[]).includes(topic);
  const inMath = (MATH_TOPICS as readonly string[]).includes(topic);
  if (inReading && inMath) return 'both';
  return inMath ? 'math' : 'reading';
}
