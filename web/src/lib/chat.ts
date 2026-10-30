/** Chat protocol: SSE parsing and streaming against POST /chat (backend/src/hikeall/api/chat.py). */

export type ConstraintKind = "roundtrip" | "length_km" | "ascent_m" | "duration_h" | "radius_km";

export type Constraint = {
  kind: ConstraintKind;
  min: number | null;
  max: number | null;
  required: boolean | null;
  /** a single value without bound word ("8 km"); min/max are the visible band around it */
  approx?: number | null;
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
  // multi-day (only values the user wrote; null otherwise)
  trail_id?: string | null;
  trail_assumed?: boolean;
  days?: number | null;
  day_km?: number | null;
  start_date?: string | null;
  start_time?: string | null;
  day_change?: { day: number; change: "shorter" | "longer" } | null;
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
  /** null: area start, the tour lies in the area */
  distance_km: number | null;
  cover_thumb_url: string | null;
  cover_author: string | null;
  cover_license: string | null;
  cover_license_url: string | null;
  cover_page_url: string | null;
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

/** Multi-day plan, as serialised by backend PlanEvent (agent/multiday.py, adapters/open_meteo.py). */
export type PlanStop = {
  lodging_id: number;
  name: string | null;
  kind: string | null;
  website: string | null;
  along_km: number;
  dist_m: number;
};

export type DayPlan = {
  day: number;
  /** ISO date; null: the user gave no date */
  date: string | null;
  start_km: number;
  end_km: number;
  walk_km: number;
  access_km: number;
  length_km: number;
  ascent_m: number;
  descent_m: number;
  duration_h: number;
  /** "09:00:00" */
  start_time: string;
  /** null: the day would end after midnight (see gap) */
  arrival: string | null;
  /** null: the day ends at the trail end */
  stop: PlanStop | null;
  gap: string | null;
  within_band: boolean;
};

export type MultidayPlan = {
  trail_id: string;
  trail_name: string;
  target_km: number;
  days: DayPlan[];
  notes: string[];
  source_ids: string[];
};

export type DayWeather = {
  date: string;
  code: number | null;
  text: string | null;
  t_min_c: number | null;
  t_max_c: number | null;
  precip_mm: number | null;
  precip_prob_pct: number | null;
  source_id: string;
};

export type NoForecast = { reason: string };

export type RainVariant = {
  station_name: string;
  walk_km: number;
  ascent_m: number;
  duration_h: number;
  note: string;
};

/** The plan event without its type (what is stored and saved with „Merken“). Keys of weather/rain: day number. */
export type PlanData = {
  plan: MultidayPlan;
  weather: Record<string, DayWeather | NoForecast>;
  rain: Record<string, RainVariant | null>;
  labels?: Labels;
  /** the start place of the request at that moment (added by the web app, not part of the event) */
  start_name?: string | null;
};

/** tag_id -> vocabulary label */
export type Labels = Record<string, string>;

export type ChatEvent =
  | { type: "understood"; text: string; request: HikeRequest; labels?: Labels }
  | { type: "clarify"; question: string; options: string[] }
  | { type: "results"; cards: TourCard[]; fallback_reason: string | null; labels?: Labels }
  | ({ type: "plan" } & PlanData)
  | { type: "token"; text: string }
  | { type: "sources"; sources: SourceBrief[] }
  | { type: "done"; usage: unknown; unsupported: number }
  | { type: "error"; message: string }
  /** 401 from /chat: no or expired session */
  | { type: "auth"; message: string };

export const ERROR_INTERRUPTED = "Die Antwort wurde unterbrochen. Bitte stelle die Frage noch einmal.";

export const ERROR_REJECTED =
  "Die Nachricht konnte nicht verarbeitet werden. Bitte formuliere sie neu oder kürzer.";

export const ERROR_AUTH = "Sitzung abgelaufen – bitte erneut anmelden";

export const ERROR_AUTH_UNAVAILABLE = "Anmeldung kann gerade nicht geprüft werden – bitte gleich noch einmal versuchen.";

export const ERROR_UNREACHABLE =
  "Der Planungs-Dienst ist gerade nicht erreichbar. Bitte versuche es gleich noch einmal.";

/**
 * Feeds a received text chunk into the SSE parser. `buffer` is the unfinished rest of the
 * previous call; returns the complete events and the new rest.
 */
export function parseSse(chunk: string, buffer: string): { events: ChatEvent[]; rest: string } {
  let text = buffer + chunk;
  // a trailing "\r" may be the first half of a CRLF split across chunks: carry it over
  const tail = text.endsWith("\r") ? "\r" : "";
  if (tail) text = text.slice(0, -1);
  const parts = text.replace(/\r\n?/g, "\n").split("\n\n");
  const rest = (parts.pop() ?? "") + tail;
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
  accessToken?: string | null,
): Promise<void> {
  try {
    const res = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ thread_id: threadId, message }),
      signal,
    });
    // no or expired session (JSON answer): the chat asks to sign in again; the JWKS being unreachable is not the user's fault
    if (res.status === 401) return onEvent({ type: "auth", message: ERROR_AUTH });
    if (res.status === 503) return onEvent({ type: "error", message: ERROR_AUTH_UNAVAILABLE });
    // a rejected request (e.g. 422, 413) answers with JSON, not with events
    const rejected = res.status >= 400 && res.status < 500 ? ERROR_REJECTED : ERROR_UNREACHABLE;
    if (!res.body) {
      onEvent({ type: "error", message: res.ok ? ERROR_UNREACHABLE : rejected });
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let rest = "";
    let finished = false; // saw "done" or "error"
    let got = false;
    const emit = (events: ChatEvent[]) => {
      for (const e of events) {
        got = true;
        if (e.type === "done" || e.type === "error") finished = true;
        onEvent(e);
      }
    };
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      const parsed = parseSse(decoder.decode(value, { stream: true }), rest);
      rest = parsed.rest;
      emit(parsed.events);
    }
    emit(parseSse("\n\n", rest).events); // an event the server did not terminate
    if (!finished) onEvent({ type: "error", message: got || res.ok ? ERROR_INTERRUPTED : rejected });
  } catch (e) {
    if (signal?.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
    onEvent({ type: "error", message: ERROR_UNREACHABLE });
  }
}
