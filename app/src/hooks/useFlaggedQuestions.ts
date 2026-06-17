import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useQuestionBank } from './useQuestionBank';
import { fetchFlaggedAttempts, type FlaggedAttemptRow } from '../lib/queries';
import type { Question, Response } from '../types';

export interface FlaggedItem {
  question: Question;
  response: Response;
}

/**
 * Loads the student's flagged attempts and joins them with the question bank.
 * Deduplicates by question (keeping the most recent flagged attempt) so a
 * question flagged across several sessions appears once.
 */
export function useFlaggedQuestions(): { loading: boolean; items: FlaggedItem[] } {
  const { user } = useAuth();
  const { bank, loading: bankLoading } = useQuestionBank();
  const [rows, setRows] = useState<FlaggedAttemptRow[] | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    fetchFlaggedAttempts(user.id)
      .then((r) => { if (!cancelled) setRows(r); })
      .catch(() => { if (!cancelled) setRows([]); });
    return () => { cancelled = true; };
  }, [user]);

  const items = useMemo<FlaggedItem[]>(() => {
    if (!rows) return [];
    const byId = new Map(bank.map((q) => [q.id, q]));
    const seen = new Set<string>();
    const out: FlaggedItem[] = [];
    for (const r of rows) { // already ordered newest-first
      if (seen.has(r.question_id)) continue;
      seen.add(r.question_id);
      const question = byId.get(r.question_id);
      if (!question) continue;
      out.push({
        question,
        response: {
          questionId: r.question_id,
          answer: r.student_answer,
          isCorrect: r.is_correct,
          flagged: true,
        },
      });
    }
    return out;
  }, [rows, bank]);

  return { loading: bankLoading || rows === null, items };
}
