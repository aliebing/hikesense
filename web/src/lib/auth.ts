"use client";

import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { useEffect, useState } from "react";

/**
 * Supabase Auth in the browser (anon key, session kept in localStorage by supabase-js).
 * The server-side client in supabase.ts stays session-less; this one is only for sign-in.
 */
let client: SupabaseClient | null = null;

export function getBrowserSupabase(): SupabaseClient {
  if (client) return client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("NEXT_PUBLIC_SUPABASE_URL und NEXT_PUBLIC_SUPABASE_ANON_KEY fehlen (siehe .env.example).");
  client = createClient(url, key, { auth: { persistSession: true, autoRefreshToken: true } });
  return client;
}

/** Current session; `loading` until the stored one is read. Without configuration: no session, never throws. */
export function useSession(): { session: Session | null; loading: boolean } {
  const [state, setState] = useState<{ session: Session | null; loading: boolean }>({ session: null, loading: true });
  useEffect(() => {
    let sb: SupabaseClient;
    try {
      sb = getBrowserSupabase();
    } catch {
      setState({ session: null, loading: false });
      return;
    }
    let live = true;
    sb.auth
      .getSession()
      .then(({ data }) => live && setState({ session: data.session, loading: false }))
      .catch(() => live && setState({ session: null, loading: false }));
    const { data } = sb.auth.onAuthStateChange((_event, session) => setState({ session, loading: false }));
    return () => {
      live = false;
      data.subscription.unsubscribe();
    };
  }, []);
  return state;
}

/** A fresh access token (supabase-js refreshes an expired one); null without session. Never throws. */
export async function getAccessToken(): Promise<string | null> {
  try {
    const { data } = await getBrowserSupabase().auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}

export const MSG_CONFIRM_EMAIL = "Bitte bestätige deine E-Mail-Adresse";

function german(message: string | undefined): string {
  const m = message ?? "";
  if (m.includes("Invalid login credentials")) return "E-Mail oder Passwort falsch";
  if (m.includes("Email not confirmed")) return MSG_CONFIRM_EMAIL;
  if (m.includes("already registered")) return "Diese E-Mail-Adresse ist schon registriert";
  if (m.includes("at least")) return "Das Passwort ist zu kurz (mindestens 6 Zeichen)";
  if (m.includes("valid email") || m.includes("invalid format")) return "Bitte gib eine gültige E-Mail-Adresse ein";
  if (m.includes("rate limit")) return "Zu viele Versuche – bitte warte einen Moment";
  return "Das hat nicht geklappt – bitte versuche es noch einmal";
}

/** `error` is a German message or null; `notice` is a non-error hint (e.g. confirm the e-mail). */
export type AuthResult = { error: string | null; notice?: string };

async function run(call: () => Promise<{ error: { message: string } | null; session?: Session | null }>): Promise<AuthResult> {
  try {
    const { error } = await call();
    return { error: error ? german(error.message) : null };
  } catch {
    return { error: "Die Anmeldung ist gerade nicht erreichbar – bitte versuche es gleich noch einmal" };
  }
}

export const signIn = (email: string, password: string): Promise<AuthResult> =>
  run(() => getBrowserSupabase().auth.signInWithPassword({ email, password }));

export async function signUp(email: string, password: string): Promise<AuthResult> {
  try {
    const { data, error } = await getBrowserSupabase().auth.signUp({ email, password });
    if (error) return { error: german(error.message) };
    // with e-mail confirmation on, there is a user but no session until the link was clicked
    if (!data.session) return { error: null, notice: MSG_CONFIRM_EMAIL };
    return { error: null };
  } catch {
    return { error: "Die Anmeldung ist gerade nicht erreichbar – bitte versuche es gleich noch einmal" };
  }
}

export const signOut = (): Promise<AuthResult> => run(() => getBrowserSupabase().auth.signOut());
