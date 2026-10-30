import { createClient, type SupabaseClient } from "@supabase/supabase-js";

/**
 * Server-side Supabase client (anon key, read-only via RLS).
 *
 * URL resolution on the server: SUPABASE_URL first — inside docker compose this
 * is http://host.docker.internal:54321, which only the server can resolve —
 * then NEXT_PUBLIC_SUPABASE_URL. In the browser (client pages such as
 * /unterwegs and /plan load trails too): see browserSupabaseUrl.
 */
export class MissingConfigError extends Error {}

/**
 * Supabase as the browser reaches it: NEXT_PUBLIC_SUPABASE_URL when set, otherwise the
 * same origin under /sb, which next.config.ts proxies to SUPABASE_URL — so a single
 * HTTPS tunnel to :3000 serves auth, data and signed photo URLs on the phone.
 */
export function browserSupabaseUrl(): string {
  return process.env.NEXT_PUBLIC_SUPABASE_URL || `${window.location.origin}/sb`;
}

export function getSupabase(): SupabaseClient {
  const url =
    typeof window === "undefined" ? process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL : browserSupabaseUrl();
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
