/** Chat protocol: SSE parsing and streaming against POST /chat (backend/src/hikesense/api/chat.py). */

import { messagesFor, type Locale } from "../i18n/locale";

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
  /** large version of the cover (page backdrop); missing in cards saved before it existed */
  cover_url?: string | null;
  /** the cover is from the nearest photographed tour (this one has none) */
  cover_nearby?: boolean;
  results: ConstraintResult[];
  deviation_text: string | null;
  /** misses exactly one hard condition by a little (deviation_text says which); absent in older saved cards */
  near_miss?: boolean;
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
  /** language of notes and gaps; absent in plans saved before it existed (German) */
  lang?: "de" | "en";
};

export type DayWeather = {
  date: string;
  code: number | null;
  text: string | null;
  t_min_c: number | null;
  t_max_c: number | null;
  precip_mm: number | null;
  precip_prob_pct: number | null;
  /** only the weather day finder asks for it; plan weather has none */
  snowfall_cm?: number | null;
  source_id: string;
};

/** The weather wish of a day search. */
export type WeatherWish = "fine" | "dry" | "snow";
/** One day of the weather day finder: `match` null = a value needed for the decision is missing. */
export type WeatherDayEntry = { date: string; match: boolean | null; weather: DayWeather };
/** Days that fit a weather wish at a place; `best_only`: none fits, these are the closest; `note`: why the forecast is missing or partial. */
export type WeatherDaysData = { wish: WeatherWish; place: string; days: WeatherDayEntry[]; best_only: boolean; note: string | null };

/** Why there is no forecast. `reason` is the text in the reply language; the web checks `code`. */
export type NoForecastCode = "not_yet" | "past" | "unavailable" | "missing" | "no_place";
/** `code` is absent in plans saved before it existed. */
export type NoForecast = { reason: string; code?: NoForecastCode };

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
  /** the plan's start place (backend PlanEvent; payloads saved before it: added by the web app) */
  start_name?: string | null;
};

/** A group of the curated list (no persons, no event dates); `checked_at` is an ISO date. */
export type GroupBrief = {
  name: string;
  kind: string;
  place: string;
  url: string;
  checked_at: string;
  stale: boolean;
  dist_km: number;
  /** "geprüft": confirmed by hand; "vorschlag" (or missing, older payloads): page and name fetched automatically */
  status?: string;
};

/** One race field: the value and the verbatim quote from the source page; value null = „nicht angegeben“. */
export type RaceField = { value: string | null; quote: string | null };

/** A race found live on the web: every field with a value is quoted on `source_url` (ISO dates). */
export type VerifiedRace = {
  name: RaceField;
  date: RaceField;
  place: RaceField;
  distances: RaceField;
  registration_url: RaceField;
  registration_deadline: RaceField;
  fee: RaceField;
  source_url: string;
  day: string;
};

/** A running calendar to search yourself (shown when no race is verified). */
export type CalendarLink = { name: string; url: string };

/** tag_id -> vocabulary label */
export type Labels = Record<string, string>;

export type ChatEvent =
  | { type: "understood"; text: string; request: HikeRequest; labels?: Labels }
  | { type: "clarify"; question: string; options: string[] }
  | { type: "results"; cards: TourCard[]; fallback_reason: string | null; labels?: Labels }
  | ({ type: "plan" } & PlanData)
  | ({ type: "weather_days" } & WeatherDaysData)
  | { type: "groups"; groups: GroupBrief[]; checked_note: string }
  | { type: "events"; events: VerifiedRace[]; fallback: CalendarLink[]; note: string }
  | { type: "token"; text: string }
  | { type: "sources"; sources: SourceBrief[] }
  | {
      type: "done";
      usage: unknown;
      unsupported: number;
      unsupported_names?: string[];
      unsat_claims_removed?: number;
    }
  /** `code` "guest_limit": a guest used up the requests without an account */
  | { type: "error"; message: string; code?: string | null }
  /** 401 from /chat: no or expired session */
  | { type: "auth"; message: string }
  /** 403 from /chat: the signed-in account is blocked */
  | { type: "blocked" };

type ChatErrorKey = keyof ReturnType<typeof messagesFor>["errors"]["chat"];

/** The web app's own error texts (not the backend's) in the given language. */
export const chatError = (key: ChatErrorKey, lang: Locale): string => messagesFor(lang).errors.chat[key];

/** True for the "sign-in cannot be checked" message in either language. */
export const isAuthUnavailable = (message: string): boolean => message === chatError("authUnavailable", "de") || message === chatError("authUnavailable", "en");

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
  signal: AbortSignal | undefined,
  accessToken: string | null | undefined,
  lang: Locale,
): Promise<void> {
  try {
    const res = await fetch(`${apiUrl}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: JSON.stringify({ thread_id: threadId, message, lang }),
      signal,
    });
    // no or expired session (JSON answer): the chat asks to sign in again; the JWKS being unreachable is not the user's fault
    if (res.status === 401) return onEvent({ type: "auth", message: chatError("sessionExpired", lang) });
    if (res.status === 503) return onEvent({ type: "error", message: chatError("authUnavailable", lang) });
    if (res.status === 403) {
      const body = (await res.json().catch(() => null)) as { detail?: string } | null;
      if (body?.detail === "account_blocked") return onEvent({ type: "blocked" });
    }
    // a rejected request (e.g. 422, 413) answers with JSON, not with events
    const rejected = res.status >= 400 && res.status < 500 ? chatError("rejected", lang) : chatError("unreachable", lang);
    if (!res.body) {
      onEvent({ type: "error", message: res.ok ? chatError("unreachable", lang) : rejected });
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
    if (!finished) onEvent({ type: "error", message: got || res.ok ? chatError("interrupted", lang) : rejected });
  } catch (e) {
    if (signal?.aborted || (e instanceof DOMException && e.name === "AbortError")) return;
    onEvent({ type: "error", message: chatError("unreachable", lang) });
  }
}
