/** Chat protocol: SSE parsing and streaming against POST /chat (backend/src/hikeall/api/chat.py). */

export type ConstraintKind = "roundtrip" | "length_km" | "ascent_m" | "duration_h" | "radius_km";

export type Constraint = {
  kind: ConstraintKind;
  min: number | null;
  max: number | null;
  required: boolean | null;
};

export type Preference = { tag_id: string; mode: "prefer" | "avoid"; weight: number };

export type HikeRequest = {
  intent: string;
  activity: "hike" | "run";
  start_text: string | null;
  start: { label: string } | null;
  constraints: Constraint[];
  preferences: Preference[];
  pace_min_per_km: number | null;
  unmatched: string[];
  question: string | null;
};

export type ConstraintResult = {
  kind: string;
  ok: boolean | null;
  actual: number | boolean | null;
  bound: string;
  deviation_rel: number;
  bound_value: number | null;
};

export type PreferenceMatch = { score: number; met: string[]; missing: string[]; avoided_hit: string[] };

export type TourCard = {
  trail_id: string;
  name: string;
  length_km: number | null;
  ascent_m: number | null;
  duration_h: number | null;
  distance_km: number;
  cover_thumb_url: string | null;
  results: ConstraintResult[];
  deviation_text: string | null;
  preference: PreferenceMatch;
};

export type SourceBrief = {
  id: string;
  name: string | null;
  url: string | null;
  license: string | null;
  status: string | null;
};

export type ChatEvent =
  | { type: "understood"; text: string; request: HikeRequest }
  | { type: "clarify"; question: string; options: string[] }
  | { type: "results"; cards: TourCard[]; fallback_reason: string | null }
  | { type: "token"; text: string }
  | { type: "sources"; sources: SourceBrief[] }
  | { type: "done"; usage: unknown; unsupported: number }
  | { type: "error"; message: string };

export const ERROR_UNREACHABLE =
  "Der Planungs-Dienst ist gerade nicht erreichbar. Bitte versuche es gleich noch einmal.";

/**
 * Feeds a received text chunk into the SSE parser. `buffer` is the unfinished rest of the
 * previous call; returns the complete events and the new rest.
 */
export function parseSse(chunk: string, buffer: string): { events: ChatEvent[]; rest: string } {
  const parts = (buffer + chunk).replace(/\r\n?/g, "\n").split("\n\n");
  const rest = parts.pop() ?? "";
  const events: ChatEvent[] = [];
  for (const block of parts) {
    const data = block
      .split("\n")
      .filter((l) => l.startsWith("data:"))
      .map((l) => l.slice(5).replace(/^ /, ""))
      .join("\n");
    if (!data) continue; // comment / ping
    try {
      const parsed = JSON.parse(data) as ChatEvent;
      if (parsed && typeof parsed.type === "string") events.push(parsed);
    } catch {
      // ignore a malformed block rather than breaking the stream
    }
  }
  return { events, rest };
}

/** Sends one message and calls onEvent for each event; failures arrive as an "error" event. */
export async function streamChat(
  apiUrl: string,
  threadId: string,
  message: string,
  onEvent: (e: ChatEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  try {
    const res = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ thread_id: threadId, message }),
      signal,
    });
    if (!res.body) {
      onEvent({ type: "error", message: ERROR_UNREACHABLE });
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let rest = "";
    let got = false;
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const parsed = parseSse(decoder.decode(value, { stream: true }), rest);
      rest = parsed.rest;
      for (const e of parsed.events) {
        got = true;
        onEvent(e);
      }
    }
    if (!got && !res.ok) onEvent({ type: "error", message: ERROR_UNREACHABLE });
  } catch (e) {
    if (signal?.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
    onEvent({ type: "error", message: ERROR_UNREACHABLE });
  }
}
