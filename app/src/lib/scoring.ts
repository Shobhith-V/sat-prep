/**
 * scoring.ts — pure answer checking.
 *
 * Multiple choice: exact letter match.
 * Numeric response: the dataset stores one or more accepted forms
 *   (e.g. "9", or ["1/5", ".2"]). A student's typed answer is correct if it
 *   matches any accepted form either as a string or as an equal number — so
 *   ".2", "0.2", and "1/5" are all accepted for the same question.
 */
import type { Question } from '../types';

/** Parse a fraction ("a/b") or decimal/integer string into a number, else null. */
function toNumber(raw: string): number | null {
  const s = raw.trim();
  if (s === '') return null;
  const frac = s.match(/^(-?\d+(?:\.\d+)?)\s*\/\s*(-?\d+(?:\.\d+)?)$/);
  if (frac) {
    const denom = Number(frac[2]);
    return denom !== 0 ? Number(frac[1]) / denom : null;
  }
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
}

function numericEquals(a: string, b: string): boolean {
  if (a.trim() === b.trim()) return true;
  const na = toNumber(a);
  const nb = toNumber(b);
  return na !== null && nb !== null && Math.abs(na - nb) < 1e-6;
}

export function acceptedForms(q: Question): string[] {
  return Array.isArray(q.correct_answer) ? q.correct_answer : [q.correct_answer];
}

export function isCorrectAnswer(q: Question, answer: string): boolean {
  if (!answer || answer.trim() === '') return false;
  if (q.question_type === 'multiple_choice') {
    return answer.trim().toUpperCase() === String(q.correct_answer).trim().toUpperCase();
  }
  return acceptedForms(q).some((form) => numericEquals(form, answer));
}

/** Human-readable correct answer for the results screen. */
export function correctAnswerDisplay(q: Question): string {
  return acceptedForms(q).join(' or ');
}
