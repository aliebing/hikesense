import type { Candidate, DetailConstraint, DetailRequest, SearchDetail as Detail } from "../../lib/admin";
import { messagesFor, type Locale } from "../../i18n/locale";
import { useLocale, useT } from "../../i18n";
import { ms, usd, when } from "../../lib/admin";
import { dateIn, dayLabel, MISSING, num } from "../../lib/format";
import ChatText from "../ChatText";

const PREVIEW = 300;
const UNIT: Record<string, string> = { length_km: "km", ascent_m: "m", radius_km: "km", duration_h: "h" };
const one = (n: number, locale: Locale) => num(n, locale, { min: 1 });
const kindName = (kind: string, locale: Locale): string => (messagesFor(locale).admin.kinds as Record<string, string>)[kind] ?? kind;

const json = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v, null, 0) ?? "");

function constraintText(c: DetailConstraint, locale: Locale): string {
  if (c.kind === "roundtrip") return messagesFor(locale).admin.roundWalk(!!c.required);
  const name = kindName(c.kind, locale);
  const fmt1 = { format: (n: number) => one(n, locale) };
  const u = UNIT[c.kind] ? ` ${UNIT[c.kind]}` : "";
  const parts: string[] = [];
  if (c.min != null && c.max != null) parts.push(`${name} ${fmt1.format(c.min)}–${fmt1.format(c.max)}${u}`);
  else if (c.max != null) parts.push(`${name} ≤ ${fmt1.format(c.max)}${u}`);
  else if (c.min != null) parts.push(`${name} ≥ ${fmt1.format(c.min)}${u}`);
  return parts.join("");
}

function understood(r: DetailRequest, locale: Locale): string[] {
  const t = messagesFor(locale).admin;
  const out: string[] = [];
  const place = r.start?.label ?? r.start_text;
  if (place) out.push(t.place(place));
  for (const c of r.constraints ?? []) {
    const t = constraintText(c, locale);
    if (t) out.push(t);
  }
  if (r.days != null) out.push(t.days(r.days));
  if (r.day_km != null) out.push(t.dayLength(one(r.day_km, locale)));
  if (r.start_date) out.push(t.date(r.start_date));
  if (r.weather_wish) {
    const w = messagesFor(locale).weather;
    out.push(`${w.title}: ${(w.wishes as Record<string, string>)[r.weather_wish] ?? r.weather_wish}`);
  }
  const prefer = (r.preferences ?? []).filter((p) => p.mode !== "avoid").map((p) => p.tag_id);
  if (prefer.length) out.push(t.prefer(prefer.join(", ")));
  for (const p of (r.preferences ?? []).filter((p) => p.mode === "avoid")) out.push(t.without(p.tag_id));
  return out;
}

function cell(c: Candidate, kind: string, locale: Locale): string {
  const r = c.results.find((x) => x.kind === kind);
  if (!r || r.ok === null || r.ok === undefined) return "?";
  const mark = r.ok ? "✓" : "✗";
  return typeof r.actual === "number" ? `${mark} ${one(r.actual, locale)}` : mark;
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-serif text-base">{title}</h3>
      {children}
    </section>
  );
}

function WeatherFinder({ w }: { w: NonNullable<Detail["weather_days"]> }) {
  const { locale } = useLocale();
  const t = useT().weather;
  const n0 = (n: number | null) => (n === null ? MISSING : num(n, locale, { max: 0 }));
  const n1 = (n: number | null) => (n === null ? MISSING : num(n, locale, { max: 1 }));
  const mark = (m: boolean | null) => (m === null ? "?" : m ? "✓" : "✗");
  return (
    <>
      <p>{t.adminLine((t.wishes as Record<string, string>)[w.wish] ?? w.wish, w.place, w.best_only)}</p>
      {w.note && <p className="text-xs">{w.note}</p>}
      <ul className="text-xs">
        {w.days.map((d) => (
          <li key={d.date}>
            {`${mark(d.match)} ${dayLabel(d.date, locale)} · ${n0(d.t_min_c)} / ${n0(d.t_max_c)} °C · ${n0(d.precip_prob_pct)}% / ${n1(d.precip_mm)} mm · ${n1(d.snowfall_cm)} cm`}
          </li>
        ))}
      </ul>
    </>
  );
}

function Candidates({ rows }: { rows: Candidate[] }) {
  const { locale } = useLocale();
  const t = useT().admin;
  const kinds = [...new Set(rows.flatMap((c) => c.results.map((r) => r.kind)))];
  return (
    <table className="w-full border-collapse text-left text-xs">
      <thead>
        <tr className="border-b border-wald-dunkel/20">
          <th className="py-1 pr-2">{t.tour}</th>
          {kinds.map((k) => (
            <th key={k} className="pr-2">
              {kindName(k, locale)}
            </th>
          ))}
          <th className="pr-2">{t.prefs}</th>
          <th className="pr-2">{t.score}</th>
          <th className="pr-2">{t.status}</th>
          <th>{t.note}</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr key={c.trail_id + c.status} className={`border-b border-wald-dunkel/10 ${c.status === "rejected" ? "opacity-60" : c.status === "near_miss" ? "bg-amber-50" : ""}`}>
            <td className="py-1 pr-2 font-medium">{c.name}</td>
            {kinds.map((k) => (
              <td key={k} className="pr-2">
                {cell(c, k, locale)}
              </td>
            ))}
            <td className="pr-2">
              {[...c.met.map((x) => `${x} ✓`), ...c.missing.map((x) => `${x} ✗`), ...c.avoided.map((x) => `${t.without(x)} ✗`)].join(" · ") || MISSING}
            </td>
            <td className="pr-2">{one(c.score, locale)}</td>
            <td className="pr-2">{(t.statuses as Record<string, string>)[c.status] ?? c.status}</td>
            <td>{c.note ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function SearchDetail({ d }: { d: Detail }) {
  const { locale } = useLocale();
  const t = useT().admin;
  const wt = useT().weather;
  const detailed = d.llm_calls !== undefined; // present in every new log line, even error lines
  const calls = d.llm_calls ?? [];
  const cost = d.calls_without_cost && d.cost_usd === 0 ? null : (d.cost_usd ?? null);
  const hasTours = (d.candidates?.length ?? 0) > 0;
  const heard = d.request ? understood(d.request, locale) : [];
  const tools = d.tools ?? [];

  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex flex-col gap-1">
        <p className="text-xs text-wald-dunkel/70">
          {t.meta(d.email ?? (d.owner === "unknown" ? t.unknown : d.owner), when(d.ts, locale), d.intent ?? MISSING, d.activity ?? MISSING)}
        </p>
        {detailed && d.message && <p className="font-bold">{d.message}</p>}
        {(d.previous_messages?.length ?? 0) > 0 && (
          <div className="text-xs text-wald-dunkel/80">
            <p>{t.earlier}</p>
            <ul className="list-disc pl-5">
              {d.previous_messages!.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {d.error && <p className="text-xs text-red-800">{t.errorLabel} {d.error}</p>}
      </div>

      {!detailed && <p className="rounded-lg bg-wald-dunkel/10 px-3 py-2">{t.olderNote}</p>}

      {heard.length > 0 && (
        <Block title={t.understood}>
          <p>{heard.join(" · ")}</p>
        </Block>
      )}

      {detailed && d.answer && (
        <Block title={t.answer}>
          <p className="whitespace-pre-wrap">
            <ChatText text={d.answer} />
          </p>
          <p className="text-xs text-wald-dunkel/80">{t.grounding(d.grounding_unsupported ?? 0, d.grounding_unsupported_names ?? 0, d.unsat_claims_removed ?? 0)}</p>
          {d.fallback_reason && <p className="rounded-lg border-l-4 border-amber-500 bg-amber-100 px-3 py-1 text-xs text-amber-950">{d.fallback_reason}</p>}
        </Block>
      )}

      {hasTours ? (
        <Block title={t.why}>
          <Candidates rows={d.candidates!} />
        </Block>
      ) : (
        d.plan && (
          <Block title={t.why}>
            <p className="font-medium">{d.plan.trail_name}</p>
            <ul>
              {d.plan.days.map((day) => (
                <li key={day.day}>{t.planDay(day.day, one(day.length_km, locale), day.stop?.name ?? t.trailEnd)}</li>
              ))}
            </ul>
          </Block>
        )
      )}

      {d.weather_days && (
        <Block title={wt.finder}>
          <WeatherFinder w={d.weather_days} />
        </Block>
      )}

      {detailed && (
        <Block title={t.toolCalls(tools.length)}>
          <ol className="flex flex-col gap-2">
            {tools.map((tc, i) => {
              const full = tc.result === undefined || tc.result === null ? "" : json(tc.result);
              return (
                <li key={i} className="text-xs">
                  <span className="mr-1">{i + 1}.</span>
                  <span className="font-medium">{tc.name}</span> <code>{json(tc.args ?? {})}</code>
                  {tc.error && <span className="ml-2 text-red-800">{t.errorLabel} {tc.error}</span>}
                  {full && (
                    <>
                      <p data-testid="preview" className="break-all text-wald-dunkel/80">
                        {full.slice(0, PREVIEW)}
                      </p>
                      {full.length > PREVIEW && (
                        <details>
                          <summary className="cursor-pointer">{t.fullResult}</summary>
                          <pre className="whitespace-pre-wrap break-all">{full}</pre>
                        </details>
                      )}
                    </>
                  )}
                  {tc.truncated && <span className="text-amber-800">{t.truncated}</span>}
                </li>
              );
            })}
          </ol>
        </Block>
      )}

      <Block title={t.modelTitle}>
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-wald-dunkel/20">
              <th className="py-1">{t.step}</th>
              <th>{t.model}</th>
              <th>{t.inOut}</th>
              <th>{t.cols.cost}</th>
              <th>{t.cols.duration}</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((c, i) => (
              <tr key={i} className="border-b border-wald-dunkel/10">
                <td className="py-1">{c.step}</td>
                <td>{c.model ?? MISSING}</td>
                <td>{`${num(c.input_tokens ?? 0, locale)} / ${num(c.output_tokens ?? 0, locale)}`}</td>
                <td>{usd(c.cost_usd, locale)}</td>
                <td>{ms(c.duration_ms, locale)}</td>
              </tr>
            ))}
            <tr className="font-medium">
              <td className="py-1">{t.total}</td>
              <td />
              <td>{`${num(d.input_tokens ?? 0, locale)} / ${num(d.output_tokens ?? 0, locale)}`}</td>
              <td>{usd(cost, locale)}</td>
              <td>{ms(d.duration_ms ?? null, locale)}</td>
            </tr>
          </tbody>
        </table>
      </Block>

      {calls.length > 0 && (
        <Block title={t.prompts}>
          {calls.map((c, i) => (
            <details key={i} className="rounded-lg border border-wald-dunkel/15 px-2 py-1">
              <summary className="cursor-pointer">{t.prompt(c.step)}</summary>
              {c.messages.map((m, j) => (
                <div key={j} className="mt-1">
                  <h4 className="text-xs font-bold">{m.role}</h4>
                  <pre className="whitespace-pre-wrap text-xs">{m.content}</pre>
                  {m.truncated && <span className="text-xs text-amber-800">{t.truncated}</span>}
                </div>
              ))}
              <div className="mt-1">
                <h4 className="text-xs font-bold">{t.output}</h4>
                <pre className="whitespace-pre-wrap text-xs">{typeof c.output === "string" ? c.output : JSON.stringify(c.output, null, 2)}</pre>
                {c.output_truncated && <span className="text-xs text-amber-800">{t.truncated}</span>}
              </div>
            </details>
          ))}
        </Block>
      )}
    </div>
  );
}
