"use client";

import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { useEffect, useState } from "react";
import { messagesFor, type Locale } from "../i18n/locale";
import { browserSupabaseUrl } from "./supabase";

/**
 * Supabase Auth in the browser (anon key, session kept in localStorage by supabase-js).
 * The server-side client in supabase.ts stays session-less; this one is only for sign-in.
 */
let client: SupabaseClient | null = null;

export function getBrowserSupabase(): SupabaseClient {
  if (client) return client;
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!key) throw new Error("NEXT_PUBLIC_SUPABASE_ANON_KEY fehlt (siehe .env.example).");
  client = createClient(browserSupabaseUrl(), key, { auth: { persistSession: true, autoRefreshToken: true } });
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

/** Calls `cb` when the session ends (sign-out here or in another tab); returns the unsubscribe. Never throws. */
export function onSignedOut(cb: () => void): () => void {
  try {
    const { data } = getBrowserSupabase().auth.onAuthStateChange((event) => {
      if (event === "SIGNED_OUT") cb();
    });
    return () => data.subscription.unsubscribe();
  } catch {
    return () => {};
  }
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

export const MSG_CONFIRM_EMAIL = messagesFor("de").errors.auth.confirmEmail;

/** Maps a Supabase error message to the web app's own text in the given language. */
function localized(message: string | undefined, locale: Locale): string {
  const m = message ?? "";
  const e = messagesFor(locale).errors.auth;
  if (m.includes("Invalid login credentials")) return e.badCredentials;
  if (m.includes("Email not confirmed")) return e.confirmEmail;
  if (m.includes("already registered")) return e.alreadyRegistered;
  if (m.includes("at least")) return e.tooShort;
  if (m.includes("valid email") || m.includes("invalid format")) return e.invalidEmail;
  if (m.includes("rate limit")) return e.rateLimit;
  return e.generic;
}

/** `error` is a message in the active language or null; `notice` is a non-error hint (e.g. confirm the e-mail). */
export type AuthResult = { error: string | null; notice?: string };

async function run(call: () => Promise<{ error: { message: string } | null; session?: Session | null }>, locale: Locale): Promise<AuthResult> {
  try {
    const { error } = await call();
    return { error: error ? localized(error.message, locale) : null };
  } catch {
    return { error: messagesFor(locale).errors.auth.unreachable };
  }
}

export const signIn = (email: string, password: string, locale: Locale = "de"): Promise<AuthResult> =>
  run(() => getBrowserSupabase().auth.signInWithPassword({ email, password }), locale);

export async function signUp(email: string, password: string, locale: Locale = "de"): Promise<AuthResult> {
  try {
    const { data, error } = await getBrowserSupabase().auth.signUp({ email, password });
    if (error) return { error: localized(error.message, locale) };
    // with e-mail confirmation on, there is a user but no session until the link was clicked
    if (!data.session) return { error: null, notice: messagesFor(locale).errors.auth.confirmEmail };
    return { error: null };
  } catch {
    return { error: messagesFor(locale).errors.auth.unreachable };
  }
}

export const signOut = (): Promise<AuthResult> => run(() => getBrowserSupabase().auth.signOut(), "de");

/** A bare name without "@" signs in as <name>@hikeall.local (local admin: "admin"). */
export function loginEmail(input: string): string {
  const v = input.trim();
  return v.includes("@") ? v : `${v}@hikeall.local`;
}
