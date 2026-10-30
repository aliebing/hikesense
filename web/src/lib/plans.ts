import { getBrowserSupabase } from "./auth";

export type PlanKind = "day_hike" | "multiday";

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
