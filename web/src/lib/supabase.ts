import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Server-side Supabase client (anon key, read-only via RLS).
 *
 * URL resolution: SUPABASE_URL first — inside docker compose this is
 * http://host.docker.internal:54321, which only the server can resolve —
 * then NEXT_PUBLIC_SUPABASE_URL (the browser-reachable URL, e.g.
 * http://127.0.0.1:54321). All data loading in this app happens in server
 * components, so the browser never talks to Supabase directly (yet).
 */
export class MissingConfigError extends Error {}

export function getSupabase(): SupabaseClient {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) {
    throw new MissingConfigError(
      "SUPABASE_URL und SUPABASE_ANON_KEY fehlen (siehe .env.example; Schlüssel aus `npx supabase status`).",
    );
  }
  return createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }) },
  });
}
