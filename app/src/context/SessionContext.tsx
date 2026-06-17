/**
 * SessionContext — the active practice session in memory (never localStorage).
 *
 * Carries the PracticeConfig from Setup → Session, then the live run state:
 * the selected questions, the student's responses (answer + correctness + flag),
 * the current index, and status. Persistence to Supabase happens later, at the
 * Results/persistence phase — this context is purely client-side session memory.
 */
import {
  createContext, useContext, useReducer, useMemo, useCallback,
  type ReactNode,
} from 'react';
import type { PracticeConfig, Question, Response } from '../types';

type Status = 'idle' | 'configured' | 'active' | 'complete';

interface SessionState {
  config: PracticeConfig | null;
  questions: Question[];
  responses: Record<string, Response>;
  index: number;
  status: Status;
  startedAt: string | null;
  completedAt: string | null;
  persisted: boolean; // results written to Supabase?
}

const initialState: SessionState = {
  config: null,
  questions: [],
  responses: {},
  index: 0,
  status: 'idle',
  startedAt: null,
  completedAt: null,
  persisted: false,
};

type Action =
  | { type: 'SET_CONFIG'; config: PracticeConfig }
  | { type: 'START'; questions: Question[] }
  | { type: 'ANSWER'; questionId: string; answer: string; isCorrect: boolean }
  | { type: 'TOGGLE_FLAG'; questionId: string }
  | { type: 'NEXT' }
  | { type: 'COMPLETE' }
  | { type: 'MARK_PERSISTED' }
  | { type: 'CLEAR' };

function emptyResponse(questionId: string): Response {
  return { questionId, answer: '', isCorrect: false, flagged: false };
}

function reducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case 'SET_CONFIG':
      return { ...initialState, config: action.config, status: 'configured' };

    case 'START':
      return {
        ...state,
        questions: action.questions,
        responses: {},
        index: 0,
        status: 'active',
        startedAt: new Date().toISOString(),
      };

    case 'ANSWER': {
      const prev = state.responses[action.questionId] ?? emptyResponse(action.questionId);
      return {
        ...state,
        responses: {
          ...state.responses,
          [action.questionId]: {
            ...prev,
            answer: action.answer,
            isCorrect: action.isCorrect,
          },
        },
      };
    }

    case 'TOGGLE_FLAG': {
      const prev = state.responses[action.questionId] ?? emptyResponse(action.questionId);
      return {
        ...state,
        responses: {
          ...state.responses,
          [action.questionId]: { ...prev, flagged: !prev.flagged },
        },
      };
    }

    case 'NEXT':
      return { ...state, index: Math.min(state.index + 1, state.questions.length - 1) };

    case 'COMPLETE':
      return { ...state, status: 'complete', completedAt: new Date().toISOString() };

    case 'MARK_PERSISTED':
      return { ...state, persisted: true };

    case 'CLEAR':
      return initialState;

    default:
      return state;
  }
}

interface SessionContextValue {
  state: SessionState;
  config: PracticeConfig | null;
  setConfig: (config: PracticeConfig) => void;
  start: (questions: Question[]) => void;
  answer: (questionId: string, answer: string, isCorrect: boolean) => void;
  toggleFlag: (questionId: string) => void;
  next: () => void;
  complete: () => void;
  markPersisted: () => void;
  clearSession: () => void;
}

const SessionContext = createContext<SessionContextValue | undefined>(undefined);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState);

  const setConfig = useCallback((config: PracticeConfig) => dispatch({ type: 'SET_CONFIG', config }), []);
  const start = useCallback((questions: Question[]) => dispatch({ type: 'START', questions }), []);
  const answer = useCallback(
    (questionId: string, ans: string, isCorrect: boolean) =>
      dispatch({ type: 'ANSWER', questionId, answer: ans, isCorrect }),
    [],
  );
  const toggleFlag = useCallback((questionId: string) => dispatch({ type: 'TOGGLE_FLAG', questionId }), []);
  const next = useCallback(() => dispatch({ type: 'NEXT' }), []);
  const complete = useCallback(() => dispatch({ type: 'COMPLETE' }), []);
  const markPersisted = useCallback(() => dispatch({ type: 'MARK_PERSISTED' }), []);
  const clearSession = useCallback(() => dispatch({ type: 'CLEAR' }), []);

  const value = useMemo<SessionContextValue>(
    () => ({
      state, config: state.config,
      setConfig, start, answer, toggleFlag, next, complete, markPersisted, clearSession,
    }),
    [state, setConfig, start, answer, toggleFlag, next, complete, markPersisted, clearSession],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error('useSession must be used within a SessionProvider');
  return ctx;
}
