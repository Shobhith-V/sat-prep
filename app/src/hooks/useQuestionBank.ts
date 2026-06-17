import { useEffect, useState } from 'react';
import type { Question } from '../types';
import { loadQuestionBank } from '../data';

/** Loads (and caches) the merged question bank. Returns [] while loading. */
export function useQuestionBank(): { bank: Question[]; loading: boolean } {
  const [bank, setBank] = useState<Question[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadQuestionBank().then((b) => {
      if (!cancelled) setBank(b);
    });
    return () => { cancelled = true; };
  }, []);

  return { bank: bank ?? [], loading: bank === null };
}
