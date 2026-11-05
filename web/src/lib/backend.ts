import { messagesFor, type Locale } from "../i18n/locale";
import { dateIn, MISSING, num } from "./format";

/** One row of /backend/users; "guest" and "unknown" are summary rows without an account. */
export type BackendUser = {
  user_id: string;
  /** short pseudonym ("#3f9a2c") that the search views show instead of the e-mail; null for guests */
  account?: string | null;
  email: string | null;
  status: "unbestätigt" | "aktiv" | "gesperrt" | "gast" | null;
  created_at?: string | null;
  last_sign_in_at?: string | null;
  searches: number;
};

export type SearchSummary = {
  request_id: string;
  ts: string;
  owner: string;
  account: string | null;
  message: string | null;
  intent: string | null;
  hits: number | null;
  fallback: boolean;
  tool_calls: number | null;
  tokens: number;
  cost_usd: number | null;
  duration_ms: number | null;
  error: string | null;
  detailed: boolean;
};

export type SearchPage = {
  items: SearchSummary[];
  total: number;
  sums: { count: number; cost_usd: number | null; avg_duration_ms: number | null };
};

export type DetailConstraint = { kind: string; min?: number | null; max?: number | null; required?: boolean | null; approx?: number | null };
export type DetailRequest = {
  intent?: string;
  activity?: string;
  start_text?: string | null;
  start?: { label?: string } | null;
  constraints?: DetailConstraint[];
  preferences?: { tag_id: string; mode: string; weight?: number }[];
  days?: number | null;
  day_km?: number | null;
  start_date?: string | null;
  start_time?: string | null;
  weather_wish?: string | null;
};
export type CandidateResult = { kind: string; ok: boolean | null; actual: number | boolean | null; bound?: unknown };
export type Candidate = {
  trail_id: string;
  name: string;
  status: "shown" | "fallback" | "near_miss" | "rejected";
  note: string | null;
  score: number;
  met: string[];
  missing: string[];
  avoided: string[];
  results: CandidateResult[];
};
export type DetailPlan = {
  trail_name: string;
  days: { day: number; walk_km?: number; length_km: number; stop: { name: string | null } | null }[];
};
export type LlmCall = {
  step: string;
  model: string | null;
  messages: { role: string; content: string; truncated?: boolean }[];
  output: unknown;
  output_truncated?: boolean;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
};
export type ToolCall = { name: string; args?: unknown; result?: unknown; truncated?: boolean; error?: string | null };

export type WeatherDaysLog = {
  wish: string;
  place: string;
  days: { date: string; match: boolean | null; code: number | null; t_min_c: number | null; t_max_c: number | null; precip_mm: number | null; precip_prob_pct: number | null; snowfall_cm: number | null }[];
  best_only: boolean;
  note?: string | null;
};

export type SearchDetail = {
  request_id: string;
  ts: string;
  owner: string;
  account: string | null;
  intent?: string | null;
  activity?: string | null;
  tool_calls?: number;
  input_tokens?: number;
  output_tokens?: number;
  cost_usd?: number;
  calls_without_cost?: number;
  grounding_unsupported?: number;
  grounding_unsupported_names?: number;
  unsat_claims_removed?: number;
  error?: string | null;
  message?: string | null;
  previous_messages?: string[];
  request?: DetailRequest | null;
  answer?: string | null;
  fallback_reason?: string | null;
  candidates?: Candidate[];
  plan?: DetailPlan | null;
  weather_days?: WeatherDaysLog | null;
  llm_calls?: LlmCall[];
  tools?: ToolCall[];
  duration_ms?: number | null;
};

/** Failure carries only the HTTP status (0 = no connection); texts come from the catalog via adminErrorText. */
export type AdminResult<T> = { ok: true; data: T } | { ok: false; status: number };

/** Calls the admin backend through the same-origin proxy; the HttpOnly session cookie rides
 * along, no Supabase token is ever sent there. */
async function call<T>(path: string, init: RequestInit = {}): Promise<AdminResult<T>> {
  let res: Response;
  try {
    res = await fetch("/api/backend" + path, { credentials: "same-origin", ...init });
  } catch {
    return { ok: false, status: 0 };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* no JSON body */
  }
  if (!res.ok) return { ok: false, status: res.status };
  return { ok: true, data: body as T };
}

const post = (body?: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const backendGet = <T>(path: string) => call<T>(path);
export const backendPost = <T>(path: string, body?: unknown) => call<T>(path, post(body));
export const backendLogin = (name: string, password: string) => call<{ name: string }>("/login", post({ name, password }));
export const backendLogout = () => call<{ ok: boolean }>("/logout", post());

/** Catalog text for a failed admin call. */
export function adminErrorText(status: number, locale: Locale): string {
  const a = messagesFor(locale).admin;
  if (status === 401) return a.signInPlease;
  if (status === 403) return a.noAccess;
  if (status === 503) return a.notSetUp;
  if (status === 429) return a.tooManyTries;
  if (status === 0) return a.unreachable;
  return a.error(status);
}

export const usd = (v: number | null | undefined, locale: Locale): string => (v == null ? MISSING : locale === "en" ? `$${num(v, locale, { min: 4 })}` : `${num(v, locale, { min: 4 })} $`);
export const ms = (v: number | null | undefined, locale: Locale): string => (v == null ? MISSING : `${num(v / 1000, locale, { min: 1 })} s`);

const dayFmt = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Berlin" }); // YYYY-MM-DD

export function when(ts: string, locale: Locale, now: Date = new Date()): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return MISSING;
  const a = messagesFor(locale).admin;
  const time = dateIn(d, locale, { timeZone: "Europe/Berlin", hour: "2-digit", minute: "2-digit" });
  const day = dayFmt.format(d);
  if (day === dayFmt.format(now)) return `${a.today} ${time}`;
  if (day === dayFmt.format(new Date(now.getTime() - 86_400_000))) return `${a.yesterday} ${time}`;
  return `${dateIn(d, locale, { timeZone: "Europe/Berlin", day: "2-digit", month: "2-digit" })} ${time}`;
}

/** Who made a search, without the e-mail address: the account's short label, else "Guests"/"Unknown". */
export const whoSearched = (owner: string, account: string | null | undefined, t: { guests: string; unknown: string }): string =>
  account ?? (owner === "guest" ? t.guests : t.unknown);
