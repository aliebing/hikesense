import { getBrowserSupabase } from "./auth";
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
  const messages: string[] = [];
  for (const it of state.items.slice(0, end)) if (it.kind === "user") messages.push(it.text);
  let answer = "";
  for (const it of state.items.slice(end + 1)) {
    if (it.kind === "assistant") {
      answer = it.text;
      break;
    }
  }
  return { v: 1, messages, answer, results: state.last };
}

export function searchTitle(s: SavedSearch): string {
  const t = s.messages.join(" · ");
  if (!t) return "Gemerkte Suche";
  return t.length > 80 ? t.slice(0, 79) + "…" : t;
}

export function isSavedSearch(payload: unknown): payload is SavedSearch {
  if (typeof payload !== "object" || payload === null) return false;
  const p = payload as { v?: unknown; messages?: unknown; results?: { cards?: unknown } | null };
  return p.v === 1 && Array.isArray(p.messages) && Array.isArray(p.results?.cards);
}

export type SavedPlan = { id: string; kind: PlanKind; title: string; payload: unknown; created_at: string };

const MSG_FAILED = "Das Merken hat nicht geklappt – bitte versuche es noch einmal";

/** Saves the payload exactly as received (TourCard / MultidayPlan); RLS ties the row to the signed-in user. */
export async function savePlan(kind: PlanKind, title: string, payload: unknown): Promise<{ error: string | null }> {
  try {
    const { error } = await getBrowserSupabase().from("saved_plans").insert({ kind, title, payload });
    return { error: error ? MSG_FAILED : null };
  } catch {
    return { error: MSG_FAILED };
  }
}

/** Own plans, newest first (RLS hides everyone else's). */
export async function listPlans(): Promise<{ plans: SavedPlan[]; error: string | null }> {
  try {
    const { data, error } = await getBrowserSupabase()
      .from("saved_plans")
      .select("id, kind, title, payload, created_at")
      .order("created_at", { ascending: false });
    if (error) return { plans: [], error: "Die Pläne konnten nicht geladen werden" };
    return { plans: (data ?? []) as SavedPlan[], error: null };
  } catch {
    return { plans: [], error: "Die Pläne konnten nicht geladen werden" };
  }
}

export async function deletePlan(id: string): Promise<{ error: string | null }> {
  try {
    const { error } = await getBrowserSupabase().from("saved_plans").delete().eq("id", id);
    return { error: error ? "Das Löschen hat nicht geklappt" : null };
  } catch {
    return { error: "Das Löschen hat nicht geklappt" };
  }
}
