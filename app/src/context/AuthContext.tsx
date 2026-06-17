/**
 * AuthContext — wraps Supabase auth session state.
 *
 * Foundational infrastructure: the router's ProtectedRoute depends on it.
 * The sign-up / sign-in / sign-out methods are thin Supabase wrappers; the
 * Login / SignUp page UIs that call them are built in a later phase.
 */
import {
  createContext, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';
import type { Session, User } from '@supabase/supabase-js';
import { supabase, isSupabaseConfigured } from '../lib/supabase';
import type { Profile } from '../types';

interface AuthResult {
  error: string | null;
}

interface SignUpResult extends AuthResult {
  /** True when the project requires email confirmation (no session yet). */
  needsConfirmation: boolean;
}

interface AuthContextValue {
  user: User | null;
  session: Session | null;
  profile: Profile | null;
  loading: boolean;
  configured: boolean;
  signUp: (name: string, email: string, password: string) => Promise<SignUpResult>;
  signIn: (email: string, password: string) => Promise<AuthResult>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isSupabaseConfigured) {
      setLoading(false);
      return;
    }

    supabase.auth
      .getSession()
      .then(({ data }) => {
        setSession(data.session);
        setUser(data.session?.user ?? null);
      })
      .catch(() => {
        setSession(null);
        setUser(null);
      })
      .finally(() => setLoading(false));

    const { data: sub } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);
    });

    return () => sub.subscription.unsubscribe();
  }, []);

  // Load the profile row whenever the user changes.
  useEffect(() => {
    if (!user) {
      setProfile(null);
      return;
    }
    supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .maybeSingle()
      .then(({ data }) => setProfile((data as Profile) ?? null));
  }, [user]);

  async function signUp(name: string, email: string, password: string): Promise<SignUpResult> {
    if (!isSupabaseConfigured) {
      return { error: 'Supabase is not configured. Set VITE_SUPABASE_* in .env.', needsConfirmation: false };
    }
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { name } }, // consumed by the handle_new_user() trigger
    });
    return {
      error: error?.message ?? null,
      // When email confirmation is enabled, signUp returns a user but no session.
      needsConfirmation: !error && !data.session,
    };
  }

  async function signIn(email: string, password: string): Promise<AuthResult> {
    if (!isSupabaseConfigured) {
      return { error: 'Supabase is not configured. Set VITE_SUPABASE_* in .env.' };
    }
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error?.message ?? null };
  }

  async function signOut(): Promise<void> {
    await supabase.auth.signOut();
  }

  const value = useMemo<AuthContextValue>(
    () => ({
      user, session, profile, loading,
      configured: isSupabaseConfigured,
      signUp, signIn, signOut,
    }),
    [user, session, profile, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
