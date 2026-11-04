import { getBrowserSupabase } from "./auth";

/** The nine feature tags of data/tags/features.yaml, in the order the settings page lists them. */
export const PREFERENCE_TAGS = [
  "feature:aussicht",
  "feature:gipfel",
  "feature:wasserfall",
  "feature:einkehr",
  "feature:bahnhof",
  "feature:rundweg",
  "surface:wenig_asphalt",
  "surface:naturweg",
  "surface:gut_laufbar",
] as const;
export type PreferenceTag = (typeof PREFERENCE_TAGS)[number];

/** Saved weights stay at most 3, the weight of a plain chat wish: whatever the chat says
 * ("wichtig" 4, "unbedingt" 5) can always outweigh a standing preference. */
export const SAVED_WEIGHTS = [1, 2, 3] as const;
export type SavedPreference = { tag_id: PreferenceTag; mode: "prefer" | "avoid"; weight: number };

export type PreferenceError = "load" | "save";

/** Own preferences (RLS hides everyone else's). */
export async function loadPreferences(): Promise<{ prefs: SavedPreference[]; error: PreferenceError | null }> {
  try {
    const { data, error } = await getBrowserSupabase().from("user_preferences").select("tag_id, mode, weight");
    if (error) return { prefs: [], error: "load" };
    return { prefs: (data ?? []) as SavedPreference[], error: null };
  } catch {
    return { prefs: [], error: "load" };
  }
}

/** Sets one tag: prefer/avoid with a weight, or null for "no preference" (the row is deleted).
 * RLS refuses silently for a blocked account: a write that touched no row counts as failed. */
export async function setPreference(tag: PreferenceTag, value: { mode: "prefer" | "avoid"; weight: number } | null): Promise<{ error: PreferenceError | null }> {
  try {
    const table = getBrowserSupabase().from("user_preferences");
    if (value === null) {
      const { error } = await table.delete().eq("tag_id", tag);
      return { error: error ? "save" : null };
    }
    const { data, error } = await table
      .upsert({ tag_id: tag, mode: value.mode, weight: value.weight, updated_at: new Date().toISOString() }, { onConflict: "user_id,tag_id" })
      .select("tag_id");
    return { error: error || !data?.length ? "save" : null };
  } catch {
    return { error: "save" };
  }
}
