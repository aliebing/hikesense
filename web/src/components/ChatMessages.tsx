import Link from "next/link";
import type { CalendarLink, Constraint, GroupBrief, HikeRequest, Labels, SourceBrief, TourCard, VerifiedRace } from "../lib/chat";
import { useLocale, useT } from "../i18n";
import { intlLocale, messagesFor, type Locale } from "../i18n/locale";
import ChatText from "./ChatText";
import EventCards from "./EventCards";
import GroupList from "./GroupList";

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "understood"; text: string; request: HikeRequest; labels: Labels }
  | { kind: "clarify"; question: string; options: string[] }
  | { kind: "results"; cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels }
  | { kind: "plan"; summary: string }
  | { kind: "groups"; groups: GroupBrief[]; note: string }
  | { kind: "events"; events: VerifiedRace[]; fallback: CalendarLink[]; note: string }
  | { kind: "sources"; sources: SourceBrief[] }
  | { kind: "notice"; text: string }
  | { kind: "error"; text: string }
  | { kind: "auth" };

const formatters = new Map<Locale, Intl.NumberFormat>();
const num = (n: number, locale: Locale) => {
  let f = formatters.get(locale);
  if (!f) formatters.set(locale, (f = new Intl.NumberFormat(intlLocale(locale), { maximumFractionDigits: 1 })));
  return f.format(n);
};

/** null when the constraint has no bound at all: nothing is invented. */
function range(label: string, unit: string, c: Constraint, locale: Locale): string | null {
  const about = c.approx != null ? ` (≈ ${num(c.approx, locale)} ${unit})` : "";
  if (c.min !== null && c.max !== null) return `${label} ${num(c.min, locale)}–${num(c.max, locale)} ${unit}${about}`;
  if (c.min !== null) return `${label} ≥ ${num(c.min, locale)} ${unit}`;
  if (c.max !== null) return `${label} ≤ ${num(c.max, locale)} ${unit}`;
  return null;
}

function constraintChip(c: Constraint, locale: Locale): string | null {
  const t = messagesFor(locale).chat;
  switch (c.kind) {
    case "roundtrip":
      return c.required === true ? t.roundWalk : c.required === false ? t.notRoundWalk : null;
    case "length_km":
      return range(t.length, "km", c, locale);
    case "ascent_m":
      return range(t.ascent, t.unitAscent, c, locale);
    case "duration_h":
      return range(t.duration, "h", c, locale);
    case "radius_km":
      return range(t.distance, "km", c, locale);
  }
}

/** The constraint chips of a request (shared with the saved-search title). */
export function constraintChips(r: HikeRequest, locale: Locale): string[] {
  return r.constraints.flatMap((c) => {
    const text = constraintChip(c, locale);
    return text ? [text] : [];
  });
}

export function chipsFor(r: HikeRequest, labels: Labels, locale: Locale): { text: string; warn?: boolean }[] {
  const t = messagesFor(locale).chat;
  return [
    ...constraintChips(r, locale).map((text) => ({ text })),
    ...r.preferences.map((p) => {
      const name = labels[p.tag_id] ?? p.tag_id;
      return { text: p.mode === "prefer" ? t.preference(name, p.weight) : t.avoid(name) };
    }),
    ...r.unmatched.map((u) => ({ text: t.notCheckable(u), warn: true })),
  ];
}

/** Real matches are counted as found; near misses are named separately. */
export function foundText(cards: { near_miss?: boolean }[], locale: Locale): string {
  const t = messagesFor(locale).chat;
  const near = cards.filter((c) => c.near_miss).length;
  const n = cards.length - near;
  if (n === 0 && near === 0) return t.noTour;
  const found = n === 0 ? "" : t.toursFound(n);
  return near === 0 ? found : n === 0 ? t.nearMisses(near) : `${found}, ${t.nearMisses(near)}`;
}

const bubble = "rounded-xl px-3 py-2 text-sm leading-relaxed";

/**
 * The backend starts the answer with the honest fallback sentence (the contract for the text);
 * the note on the results item (and on the home page) already shows it, so the bubble leaves it out (also while streaming).
 */
export function withoutFallback(items: ChatItem[], i: number, text: string): string {
  for (let j = i - 1; j >= 0; j--) {
    const it = items[j];
    if (it.kind === "user") break;
    if (it.kind !== "results") continue;
    if (!it.fallback) break;
    return stripFallback(text, it.fallback);
  }
  return text;
}

/** The answer text without its leading fallback sentence (also a partial one while streaming). */
export function stripFallback(text: string, fallback: string): string {
  const sentence = `${fallback}.`;
  if (text.startsWith(sentence)) return text.slice(sentence.length).trimStart();
  if (sentence.startsWith(text)) return "";
  return text;
}

export default function ChatMessages({
  items,
  onOption,
  disabled,
}: {
  items: ChatItem[];
  onOption: (text: string) => void;
  disabled: boolean;
}) {
  const t = useT();
  const { locale } = useLocale();
  return (
    <ol aria-label={t.chat.history} aria-live="polite" className="flex max-h-[50vh] flex-col gap-2 overflow-y-auto">
      {items.map((it, i) => (
        <li key={i} className="flex flex-col gap-1">
          {it.kind === "user" && (
            <p className={`${bubble} self-end rounded-tr-sm bg-wald text-papier`}>{it.text}</p>
          )}
          {it.kind === "assistant" && withoutFallback(items, i, it.text) && (
            <p className={`${bubble} rounded-tl-sm bg-papier/90 whitespace-pre-wrap text-wald-dunkel`}>
              <ChatText text={withoutFallback(items, i, it.text)} />
            </p>
          )}
          {it.kind === "understood" && (
            <div className="flex flex-col gap-1">
              <p className="text-xs text-papier/90">{it.text}</p>
              <ul aria-label={t.chat.understood} className="flex flex-wrap gap-1">
                {chipsFor(it.request, it.labels, locale).map((c, j) => (
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
              <p className="text-xs text-papier/90">{foundText(it.cards, locale)}</p>
            </div>
          )}
          {it.kind === "plan" && <p className="text-xs text-papier/90">{it.summary}</p>}
          {it.kind === "groups" && <GroupList groups={it.groups} note={it.note} />}
          {it.kind === "events" && <EventCards events={it.events} fallback={it.fallback} note={it.note} />}
          {it.kind === "sources" && (
            <ul aria-label={t.chat.sources} className="flex flex-col gap-0.5 text-xs text-papier/90">
              {it.sources.map((s) => (
                <li key={`${s.id}|${s.url ?? ""}`}>
                  {t.chat.source}{" "}
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer" className="underline">
                      {s.name ?? s.url}
                    </a>
                  ) : (
                    (s.name ?? `${s.id} (${t.chat.detailsMissing})`)
                  )}
                  {s.license ? ` · ${t.chat.licence} ${s.license}` : ""}
                  {s.status === "entwurf" && (
                    <span className="ml-1 rounded bg-amber-200 px-1 text-amber-950">{t.chat.draft}</span>
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
          {it.kind === "auth" && (
            <p role="alert" className={`${bubble} bg-red-100 text-red-900`}>
              {t.chat.sessionExpired}{" "}
              <Link href="/anmelden" className="underline">
                {t.chat.signIn}
              </Link>
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
