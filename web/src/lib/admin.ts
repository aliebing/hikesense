import { getAccessToken } from "./auth";

export type AdminUser = { user_id: string; email: string | null; role: string | null; searches: number };

export type SearchSummary = {
  request_id: string;
  ts: string;
  owner: string;
  email: string | null;
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
  sums: { count: number; cost_usd: number; avg_duration_ms: number | null };
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
};
export type CandidateResult = { kind: string; ok: boolean | null; actual: number | boolean | null; bound?: unknown };
export type Candidate = {
  trail_id: string;
  name: string;
  status: "shown" | "fallback" | "rejected";
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
  messages: { role: string; content: string }[];
  output: unknown;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
  duration_ms: number | null;
};
export type ToolCall = { name: string; args?: unknown; result?: unknown; truncated?: boolean; error?: string | null };

export type SearchDetail = {
  request_id: string;
  ts: string;
  owner: string;
  email: string | null;
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
  llm_calls?: LlmCall[];
  tools?: ToolCall[];
  duration_ms?: number | null;
};

export type AdminResult<T> = { ok: true; data: T } | { ok: false; status: number; message: string };

export async function adminGet<T>(path: string): Promise<AdminResult<T>> {
  const token = await getAccessToken();
  if (!token) return { ok: false, status: 401, message: "Bitte anmelden." };
  let res: Response;
  try {
    res = await fetch("/api/admin" + path, { headers: { Authorization: `Bearer ${token}` } });
  } catch {
    return { ok: false, status: 0, message: "Backend nicht erreichbar" };
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* no JSON body */
  }
  if (!res.ok) {
    const d = (body as { detail?: unknown } | null)?.detail;
    return { ok: false, status: res.status, message: typeof d === "string" ? d : `Fehler ${res.status}` };
  }
  return { ok: true, data: body as T };
}

const usdFmt = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const secFmt = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

export const usd = (v: number | null | undefined): string => (v == null ? "–" : `${usdFmt.format(v)} $`);
export const ms = (v: number | null | undefined): string => (v == null ? "–" : `${secFmt.format(v / 1000)} s`);

const dayFmt = new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Berlin" }); // YYYY-MM-DD
const timeFmt = new Intl.DateTimeFormat("de-DE", { timeZone: "Europe/Berlin", hour: "2-digit", minute: "2-digit" });
const dateFmt = new Intl.DateTimeFormat("de-DE", { timeZone: "Europe/Berlin", day: "2-digit", month: "2-digit" }); // "31.10."

export function when(ts: string, now: Date = new Date()): string {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return "–";
  const day = dayFmt.format(d);
  if (day === dayFmt.format(now)) return `heute ${timeFmt.format(d)}`;
  if (day === dayFmt.format(new Date(now.getTime() - 86_400_000))) return `gestern ${timeFmt.format(d)}`;
  return `${dateFmt.format(d)} ${timeFmt.format(d)}`;
}
