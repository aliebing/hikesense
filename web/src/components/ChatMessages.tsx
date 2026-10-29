import type { Constraint, HikeRequest, Labels, SourceBrief, TourCard } from "../lib/chat";
import TourResultCard from "./TourResultCard";

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "understood"; text: string; request: HikeRequest; labels: Labels }
  | { kind: "clarify"; question: string; options: string[] }
  | { kind: "results"; cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels }
  | { kind: "sources"; sources: SourceBrief[] }
  | { kind: "notice"; text: string }
  | { kind: "error"; text: string };

const num = (n: number) => new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 }).format(n);

/** null when the constraint has no bound at all: nothing is invented. */
function range(label: string, unit: string, c: Constraint): string | null {
  if (c.min !== null && c.max !== null) return `${label} ${num(c.min)}–${num(c.max)} ${unit}`;
  if (c.min !== null) return `${label} ≥ ${num(c.min)} ${unit}`;
  if (c.max !== null) return `${label} ≤ ${num(c.max)} ${unit}`;
  return null;
}

function constraintChip(c: Constraint): string | null {
  switch (c.kind) {
    case "roundtrip":
      return c.required === true ? "Rundweg" : c.required === false ? "kein Rundweg" : null;
    case "length_km":
      return range("Länge", "km", c);
    case "ascent_m":
      return range("Höhenmeter", "m", c);
    case "duration_h":
      return range("Dauer", "h", c);
    case "radius_km":
      return range("Entfernung", "km", c);
  }
}

export function chipsFor(r: HikeRequest, labels: Labels): { text: string; warn?: boolean }[] {
  const constraints = r.constraints.flatMap((c) => {
    const text = constraintChip(c);
    return text ? [{ text }] : [];
  });
  return [
    ...constraints,
    ...r.preferences.map((p) => {
      const name = labels[p.tag_id] ?? p.tag_id;
      return { text: p.mode === "prefer" ? `Vorliebe: ${name} (Gewicht ${p.weight})` : `Vermeiden: ${name}` };
    }),
    ...r.unmatched.map((u) => ({ text: `nicht prüfbar: ${u}`, warn: true })),
  ];
}

const bubble = "rounded-xl px-3 py-2 text-sm leading-relaxed";

export default function ChatMessages({
  items,
  onOption,
  disabled,
}: {
  items: ChatItem[];
  onOption: (text: string) => void;
  disabled: boolean;
}) {
  return (
    <ol aria-label="Verlauf" aria-live="polite" className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
      {items.map((it, i) => (
        <li key={i} className="flex flex-col gap-1">
          {it.kind === "user" && (
            <p className={`${bubble} self-end rounded-tr-sm bg-wald text-papier`}>{it.text}</p>
          )}
          {it.kind === "assistant" && (
            <p className={`${bubble} rounded-tl-sm bg-papier/90 whitespace-pre-wrap text-wald-dunkel`}>{it.text}</p>
          )}
          {it.kind === "understood" && (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-papier/90">{it.text}</p>
              <ul aria-label="Erkannte Wünsche" className="flex flex-wrap gap-1">
                {chipsFor(it.request, it.labels).map((c, j) => (
                  <li
                    key={j}
                    className={`rounded-full px-2 py-0.5 text-xs ${c.warn ? "bg-amber-200 text-amber-950" : "bg-papier/85 text-wald-dunkel"}`}
                  >
                    {c.text}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {it.kind === "clarify" && (
            <div className="flex flex-col gap-1">
              <p className={`${bubble} rounded-tl-sm bg-papier/90 text-wald-dunkel`}>{it.question}</p>
              <div className="flex flex-wrap gap-1">
                {it.options.map((o) => (
                  <button
                    key={o}
                    type="button"
                    disabled={disabled}
                    onClick={() => onOption(o)}
                    className="rounded-full bg-wald px-3 py-1 text-xs text-papier hover:bg-wald-dunkel disabled:opacity-60"
                  >
                    {o}
                  </button>
                ))}
              </div>
            </div>
          )}
          {it.kind === "results" && (
            <div className="flex flex-col gap-2">
              {it.fallback && (
                <p role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-950">
                  {it.fallback}
                </p>
              )}
              {it.cards.map((c) => (
                <TourResultCard key={c.trail_id} card={c} runWithoutPace={it.runWithoutPace} labels={it.labels} />
              ))}
            </div>
          )}
          {it.kind === "sources" && (
            <ul aria-label="Quellen" className="flex flex-col gap-0.5 text-xs text-papier/90">
              {it.sources.map((s) => (
                <li key={s.id}>
                  Quelle:{" "}
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline">
                      {s.name ?? s.url}
                    </a>
                  ) : (
                    (s.name ?? "unbekannt")
                  )}
                  {s.license ? ` · Lizenz: ${s.license}` : ""}
                  {s.status === "entwurf" && (
                    <span className="ml-1 rounded bg-amber-200 px-1 text-amber-950">Entwurf</span>
                  )}
                </li>
              ))}
            </ul>
          )}
          {it.kind === "notice" && <p className="text-xs text-papier/90">{it.text}</p>}
          {it.kind === "error" && (
            <p role="alert" className={`${bubble} bg-red-100 text-red-900`}>
              {it.text}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
