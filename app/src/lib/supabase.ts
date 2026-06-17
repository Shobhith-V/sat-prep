import { createClient } from '@supabase/supabase-js';

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const isSupabaseConfigured = Boolean(url && anonKey);

if (!isSupabaseConfigured) {
  // Non-fatal: lets the app scaffold/build before credentials are set.
  // Auth and data calls will fail until VITE_SUPABASE_* are provided.
  console.warn(
    '[supabase] VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY not set — '
    + 'auth and data are disabled until you add them to .env',
  );
}

// Fall back to harmless placeholders so createClient does not throw at import time.
export const supabase = createClient(
  url || 'https://placeholder.supabase.co',
  anonKey || 'placeholder-anon-key',
);
