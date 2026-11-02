import { getBrowserSupabase } from "./auth";
import { constraintChips } from "../components/ChatMessages";
import { messagesFor, type Locale } from "../i18n/locale";
import type { ChatState, LastResults } from "./chatState";

export type PlanKind = "day_hike" | "multiday" | "search";

/** A remembered search: the messages, the answer text and the result tiles as they were. */
export type SavedSearch = { v: 1; messages: string[]; answer: string; results: LastResults };

/** Snapshot of the current results with the user messages that led to them; null if there are none. */
export function savedSearchOf(state: ChatState): SavedSearch | null {
  if (!state.last) return null;
  let end = -1;
  for (let i = state.items.length - 1; i >= 0; i--) {
    if (state.items[i].kind === "results") {
      end = i;
      break;
    }
  }
  if (end < 0) return null;
  // This search's own messages begin after the previous results or plan, or after an answer in between
  // (a knowledge question has an assistant reply but no results; a clarify question is not a boundary).
  let start = 0;
  for (let i = end - 1; i >= 0; i--) {
    const k = state.items[i].kind;
    if (k === "results" || k === "plan" || k === "assistant") {
      start = i + 1;
      break;
    }
  }
  const messages: string[] = [];
  for (const it of state.items.slice(start, end)) if (it.kind === "user") messages.push(it.text);
  let answer = "";
  for (const it of state.items.slice(end + 1)) {
    if (it.kind === "assistant") {
      answer = it.text;
      break;
    }
  }
  return { v: 1, messages, answer, results: state.last };
}

const cut = (t: string) => (t.length > 80 ? t.slice(0, 79) + "…" : t);

/** Title from the understood request (start, constraints, preferences); falls back to the messages. */
export function searchTitle(s: SavedSearch, locale: Locale): string {
  const m = messagesFor(locale).results;
  const req = s.results?.request;
  if (req && s.results.cards.length > 0) {
    const r = req.request;
    const labels = req.labels;
    const parts = [
      r.start?.label ?? r.start_text,
      ...constraintChips(r, locale),
      ...r.preferences.map((p) => {
        const name = labels[p.tag_id] ?? p.tag_id;
        return p.mode === "prefer" ? name : m.without(name);
      }),
    ].filter((x): x is string => !!x);
    if (parts.length > 0) return cut(parts.join(" · "));
  }
  const t = s.messages.join(" · ");
  return t ? cut(t) : m.savedSearch;
}

export function isSavedSearch(payload: unknown): payload is SavedSearch {
  if (typeof payload !== "object" || payload === null) return false;
  const p = payload as { v?: unknown; messages?: unknown; results?: { cards?: unknown } | null };
  return p.v === 1 && Array.isArray(p.messages) && Array.isArray(p.results?.cards);
}

export type SavedPlan = { id: string; kind: PlanKind; title: string; payload: unknown; created_at: string };

/** Failure codes of the plan storage calls; the UI translates them at render time. */
export type PlanError = "save" | "load" | "delete";

export const planErrorText = (code: PlanError, locale: Locale): string => messagesFor(locale).errors.plans[code];

/** Saves the payload exactly as received (TourCard / MultidayPlan); RLS ties the row to the signed-in user. */
export async function savePlan(kind: PlanKind, title: string, payload: unknown): Promise<{ error: PlanError | null }> {
  try {
    const { error } = await getBrowserSupabase().from("saved_plans").insert({ kind, title, payload });
    return { error: error ? "save" : null };
  } catch {
    return { error: "save" };
  }
}

/** Own plans, newest first (RLS hides everyone else's). */
export async function listPlans(): Promise<{ plans: SavedPlan[]; error: PlanError | null }> {
  try {
    const { data, error } = await getBrowserSupabase()
      .from("saved_plans")
      .select("id, kind, title, payload, created_at")
      .order("created_at", { ascending: false });
    if (error) return { plans: [], error: "load" };
    return { plans: (data ?? []) as SavedPlan[], error: null };
  } catch {
    return { plans: [], error: "load" };
  }
}

export async function deletePlan(id: string): Promise<{ error: PlanError | null }> {
  try {
    const { error } = await getBrowserSupabase().from("saved_plans").delete().eq("id", id);
    return { error: error ? "delete" : null };
  } catch {
    return { error: "delete" };
  }
}
