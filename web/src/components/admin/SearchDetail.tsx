import type { Candidate, DetailConstraint, DetailRequest, SearchDetail as Detail } from "../../lib/admin";
import { ms, usd, when } from "../../lib/admin";
import ChatText from "../ChatText";

const de0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const de1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const PREVIEW = 300;
const KIND: Record<string, string> = { length_km: "Länge", ascent_m: "Höhenmeter", roundtrip: "Rundweg", radius_km: "Entfernung", duration_h: "Dauer" };
const UNIT: Record<string, string> = { length_km: "km", ascent_m: "m", radius_km: "km", duration_h: "h" };
const STATUS: Record<string, string> = { shown: "gezeigt", fallback: "Ausweich", rejected: "verworfen" };

const json = (v: unknown) => (typeof v === "string" ? v : JSON.stringify(v, null, 0) ?? "");

function constraintText(c: DetailConstraint): string {
  if (c.kind === "roundtrip") return `Rundweg: ${c.required ? "ja" : "nein"}`;
  const name = KIND[c.kind] ?? c.kind;
  const u = UNIT[c.kind] ? ` ${UNIT[c.kind]}` : "";
  const parts: string[] = [];
  if (c.min != null && c.max != null) parts.push(`${name} ${de1.format(c.min)}–${de1.format(c.max)}${u}`);
  else if (c.max != null) parts.push(`${name} ≤ ${de1.format(c.max)}${u}`);
  else if (c.min != null) parts.push(`${name} ≥ ${de1.format(c.min)}${u}`);
  return parts.join("");
}

function understood(r: DetailRequest): string[] {
  const out: string[] = [];
  const place = r.start?.label ?? r.start_text;
  if (place) out.push(`Ort: ${place}`);
  for (const c of r.constraints ?? []) {
    const t = constraintText(c);
    if (t) out.push(t);
  }
  if (r.days != null) out.push(`Dauer: ${r.days} Tage`);
  if (r.day_km != null) out.push(`Tageslänge: ${de1.format(r.day_km)} km`);
  if (r.start_date) out.push(`Datum: ${r.start_date}`);
  const prefer = (r.preferences ?? []).filter((p) => p.mode !== "avoid").map((p) => p.tag_id);
  if (prefer.length) out.push(`Vorliebe: ${prefer.join(", ")}`);
  for (const p of (r.preferences ?? []).filter((p) => p.mode === "avoid")) out.push(`ohne ${p.tag_id}`);
  return out;
}

function cell(c: Candidate, kind: string): string {
  const r = c.results.find((x) => x.kind === kind);
  if (!r || r.ok === null || r.ok === undefined) return "?";
  const mark = r.ok ? "✓" : "✗";
  return typeof r.actual === "number" ? `${mark} ${de1.format(r.actual)}` : mark;
}

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-1">
      <h3 className="font-serif text-base">{title}</h3>
      {children}
    </section>
  );
}

function Candidates({ rows }: { rows: Candidate[] }) {
  const kinds = [...new Set(rows.flatMap((c) => c.results.map((r) => r.kind)))];
  return (
    <table className="w-full border-collapse text-left text-xs">
      <thead>
        <tr className="border-b border-wald-dunkel/20">
          <th className="py-1 pr-2">Tour</th>
          {kinds.map((k) => (
            <th key={k} className="pr-2">
              {KIND[k] ?? k}
            </th>
          ))}
          <th className="pr-2">Vorlieben</th>
          <th className="pr-2">Punkte</th>
          <th className="pr-2">Status</th>
          <th>Hinweis</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((c) => (
          <tr key={c.trail_id + c.status} className={`border-b border-wald-dunkel/10 ${c.status === "rejected" ? "opacity-60" : ""}`}>
            <td className="py-1 pr-2 font-medium">{c.name}</td>
            {kinds.map((k) => (
              <td key={k} className="pr-2">
                {cell(c, k)}
              </td>
            ))}
            <td className="pr-2">
              {[...c.met.map((t) => `${t} ✓`), ...c.missing.map((t) => `${t} ✗`), ...c.avoided.map((t) => `ohne ${t} ✗`)].join(" · ") || "–"}
            </td>
            <td className="pr-2">{de1.format(c.score).replace(/,0$/, ",0")}</td>
            <td className="pr-2">{STATUS[c.status] ?? c.status}</td>
            <td>{c.note ?? ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function SearchDetail({ d }: { d: Detail }) {
  const detailed = d.llm_calls !== undefined; // present in every new log line, even error lines
  const calls = d.llm_calls ?? [];
  const cost = d.calls_without_cost && d.cost_usd === 0 ? null : (d.cost_usd ?? null);
  const hasTours = (d.candidates?.length ?? 0) > 0;
  const heard = d.request ? understood(d.request) : [];
  const tools = d.tools ?? [];

  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex flex-col gap-1">
        <p className="text-xs text-wald-dunkel/70">
          {d.email ?? (d.owner === "unknown" ? "Unbekannt" : d.owner)} · {when(d.ts)} · Intent {d.intent ?? "–"} · Aktivität {d.activity ?? "–"}
        </p>
        {detailed && d.message && <p className="font-bold">{d.message}</p>}
        {(d.previous_messages?.length ?? 0) > 0 && (
          <div className="text-xs text-wald-dunkel/80">
            <p>Vorher in dieser Unterhaltung</p>
            <ul className="list-disc pl-5">
              {d.previous_messages!.map((m, i) => (
                <li key={i}>{m}</li>
              ))}
            </ul>
          </div>
        )}
        {d.error && <p className="text-xs text-red-800">Fehler: {d.error}</p>}
      </div>

      {!detailed && <p className="rounded-lg bg-wald-dunkel/10 px-3 py-2">Ältere Suche – nur Kennzahlen gespeichert</p>}

      {heard.length > 0 && (
        <Block title="So verstanden">
          <p>{heard.join(" · ")}</p>
        </Block>
      )}

      {detailed && d.answer && (
        <Block title="Antwort">
          <p className="whitespace-pre-wrap">
            <ChatText text={d.answer} />
          </p>
          <p className="text-xs text-wald-dunkel/80">{`Zahlenprüfung: ${d.grounding_unsupported ?? 0} Zahlen ersetzt · ${d.grounding_unsupported_names ?? 0} Namen markiert · ${d.unsat_claims_removed ?? 0} Aussagen entfernt`}</p>
          {d.fallback_reason && <p className="rounded-lg border-l-4 border-amber-500 bg-amber-100 px-3 py-1 text-xs text-amber-950">{d.fallback_reason}</p>}
        </Block>
      )}

      {hasTours ? (
        <Block title="Warum diese Touren?">
          <Candidates rows={d.candidates!} />
        </Block>
      ) : (
        d.plan && (
          <Block title="Warum diese Touren?">
            <p className="font-medium">{d.plan.trail_name}</p>
            <ul>
              {d.plan.days.map((day) => (
                <li key={day.day}>{`Tag ${day.day} · ${de1.format(day.length_km)} km · ${day.stop?.name ?? "Wegende"}`}</li>
              ))}
            </ul>
          </Block>
        )
      )}

      {detailed && (
        <Block title={`Tool-Aufrufe (${tools.length})`}>
          <ol className="flex flex-col gap-2">
            {tools.map((t, i) => {
              const full = t.result === undefined || t.result === null ? "" : json(t.result);
              return (
                <li key={i} className="text-xs">
                  <span className="mr-1">{i + 1}.</span>
                  <span className="font-medium">{t.name}</span> <code>{json(t.args ?? {})}</code>
                  {t.error && <span className="ml-2 text-red-800">Fehler: {t.error}</span>}
                  {full && (
                    <>
                      <p data-testid="preview" className="break-all text-wald-dunkel/80">
                        {full.slice(0, PREVIEW)}
                      </p>
                      {full.length > PREVIEW && (
                        <details>
                          <summary className="cursor-pointer">Ganzes Ergebnis</summary>
                          <pre className="whitespace-pre-wrap break-all">{full}</pre>
                        </details>
                      )}
                    </>
                  )}
                  {t.truncated && <span className="text-amber-800">gekürzt</span>}
                </li>
              );
            })}
          </ol>
        </Block>
      )}

      <Block title="Modell · Tokens · Kosten · Dauer">
        <table className="w-full border-collapse text-left text-xs">
          <thead>
            <tr className="border-b border-wald-dunkel/20">
              <th className="py-1">Schritt</th>
              <th>Modell</th>
              <th>ein / aus</th>
              <th>Kosten</th>
              <th>Dauer</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((c, i) => (
              <tr key={i} className="border-b border-wald-dunkel/10">
                <td className="py-1">{c.step}</td>
                <td>{c.model ?? "–"}</td>
                <td>{`${de0.format(c.input_tokens ?? 0)} / ${de0.format(c.output_tokens ?? 0)}`}</td>
                <td>{usd(c.cost_usd)}</td>
                <td>{ms(c.duration_ms)}</td>
              </tr>
            ))}
            <tr className="font-medium">
              <td className="py-1">Summe</td>
              <td />
              <td>{`${de0.format(d.input_tokens ?? 0)} / ${de0.format(d.output_tokens ?? 0)}`}</td>
              <td>{usd(cost)}</td>
              <td>{ms(d.duration_ms ?? null)}</td>
            </tr>
          </tbody>
        </table>
      </Block>

      {calls.length > 0 && (
        <Block title="Prompts">
          {calls.map((c, i) => (
            <details key={i} className="rounded-lg border border-wald-dunkel/15 px-2 py-1">
              <summary className="cursor-pointer">{`Prompt: ${c.step}`}</summary>
              {c.messages.map((m, j) => (
                <div key={j} className="mt-1">
                  <h4 className="text-xs font-bold">{m.role}</h4>
                  <pre className="whitespace-pre-wrap text-xs">{m.content}</pre>
                  {m.truncated && <span className="text-xs text-amber-800">gekürzt</span>}
                </div>
              ))}
              <div className="mt-1">
                <h4 className="text-xs font-bold">Ausgabe</h4>
                <pre className="whitespace-pre-wrap text-xs">{typeof c.output === "string" ? c.output : JSON.stringify(c.output, null, 2)}</pre>
                {c.output_truncated && <span className="text-xs text-amber-800">gekürzt</span>}
              </div>
            </details>
          ))}
        </Block>
      )}
    </div>
  );
}
