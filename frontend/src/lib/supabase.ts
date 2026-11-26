import { AuthClient } from '@supabase/auth-js';

// Only Supabase *Auth* is used in the browser (all data goes through our API), so we
// ship the auth client alone instead of supabase-js, which also bundles the realtime,
// storage, functions and PostgREST clients (~85 kB minified we never call).
const supabaseUrl: string = import.meta.env.VITE_SUPABASE_URL || 'http://localhost:54321';
const supabaseAnonKey: string = import.meta.env.VITE_SUPABASE_ANON_KEY || 'dummy_anon_key';

// Same storage key supabase-js derives, so sessions saved before this change stay valid.
const projectRef = new URL(supabaseUrl).hostname.split('.')[0];

const auth = new AuthClient({
  url: `${supabaseUrl.replace(/\/$/, '')}/auth/v1`,
  headers: { apikey: supabaseAnonKey, Authorization: `Bearer ${supabaseAnonKey}` },
  storageKey: `sb-${projectRef}-auth-token`,
  autoRefreshToken: true,
  persistSession: true,
  detectSessionInUrl: true,
});

export const supabase = { auth };
