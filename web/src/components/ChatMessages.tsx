"use client";

import Link from "next/link";
import { useState } from "react";
import type { CalendarLink, Constraint, GroupBrief, HikeRequest, Labels, SourceBrief, TourCard, VerifiedRace, WeatherDaysData } from "../lib/chat";
import { useLocale, useT } from "../i18n";
import { intlLocale, messagesFor, type Locale } from "../i18n/locale";
import ChatText from "./ChatText";
import EventCards from "./EventCards";
import GroupList from "./GroupList";
import WeatherDays from "./WeatherDays";

export type ChatItem =
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "understood"; text: string; request: HikeRequest; labels: Labels }
  | { kind: "clarify"; question: string; options: string[] }
  | { kind: "results"; cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels }
  | { kind: "plan"; summary: string }
  | { kind: "weather_days"; data: WeatherDaysData }
  | { kind: "groups"; groups: GroupBrief[]; note: string }
  | { kind: "events"; events: VerifiedRace[]; fallback: CalendarLink[]; note: string }
  | { kind: "sources"; sources: SourceBrief[] }
  | { kind: "notice"; text: string }
  | { kind: "error"; text: string }
  /** the guest limit: an ordinary assistant line with a sign-in link, not an error */
  | { kind: "signInHint"; text: string }
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
      const text = p.mode === "prefer" ? t.preference(name, p.weight) : t.avoid(name);
      return { text: p.saved ? t.fromSaved(text) : text };
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

// One visual language: light green (sense) marks only what you can act on next.
const text = "text-[15px] leading-relaxed";
const meta = "text-[13px] text-papier/80";
const focusRing =
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sense focus-visible:ring-offset-2 focus-visible:ring-offset-wald-dunkel";
const sensePill = `rounded-full border border-sense px-3.5 py-2 text-sm font-medium text-sense transition-colors hover:bg-sense hover:text-wald-dunkel ${focusRing} disabled:cursor-not-allowed disabled:opacity-50`;
// the app speaks without a bubble; bold and links in its text get the light accents
const voice = `border-l-2 border-white/25 pl-3 ${text} text-papier whitespace-pre-wrap [&_strong]:font-semibold [&_strong]:text-white [&_a]:underline [&_a]:decoration-sense/60 [&_a]:underline-offset-2 hover:[&_a]:decoration-sense`;
const alertBox = "rounded-2xl px-3.5 py-2 text-sm leading-relaxed";
const MAX_OPTIONS = 8;

/**
 * The first paragraph of an answer and the rest: next to cards or a plan the chat shows only
 * the lead, the rest (usually the list the cards already show) opens on demand. The lead ends
 * at the first blank line or before the first list line ("1.", "-", "•").
 */
export function splitLead(text: string): [string, string] {
  const lines = text.split("\n");
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "" || /^\s*(\d+[.)]|[-*•])\s/.test(lines[i])) {
      const lead = lines.slice(0, i).join("\n").trimEnd();
      const rest = lines.slice(i).join("\n").trim();
      return rest ? [lead, rest] : [text.trim(), ""];
    }
  }
  return [text.trim(), ""];
}

/** The turn of item i (since the last user message) shows cards (2+) or a plan next to the chat. */
function turnHasCards(items: ChatItem[], i: number): boolean {
  for (let j = i - 1; j >= 0; j--) {
    const it = items[j];
    if (it.kind === "user") return false;
    if (it.kind === "plan" || (it.kind === "results" && it.cards.length >= 2)) return true;
  }
  return false;
}

function Options({ question, options, onOption, disabled }: { question: string; options: string[]; onOption: (o: string) => void; disabled: boolean }) {
  const t = useT().chat;
  const [all, setAll] = useState(false);
  const shown = all || options.length <= MAX_OPTIONS ? options : options.slice(0, MAX_OPTIONS - 1);
  return (
    <div role="group" aria-label={question} className="flex flex-wrap gap-2 pl-3">
      {shown.map((o) => (
        <button key={o} type="button" disabled={disabled} onClick={() => onOption(o)} className={sensePill}>
          {o}
        </button>
      ))}
      {shown.length < options.length && (
        <button type="button" onClick={() => setAll(true)} className={sensePill}>
          {t.moreOptions(options.length - shown.length)}
        </button>
      )}
    </div>
  );
}

function Answer({ body, short }: { body: string; short: boolean }) {
  const t = useT().chat;
  const [lead, rest] = short ? splitLead(body) : [body, ""];
  return (
    <div className={voice}>
      <ChatText text={lead} />
      {rest && (
        <details className="group mt-1">
          <summary className={`w-fit cursor-pointer list-none rounded text-[13px] font-medium text-sense hover:underline ${focusRing}`}>
            <span className="group-open:hidden">{t.fullAnswer}</span>
            <span className="hidden group-open:inline">{t.lessAnswer}</span>
          </summary>
          <div className="mt-2">
            <ChatText text={rest} />
          </div>
        </details>
      )}
    </div>
  );
}

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
  const lastUser = items.map((it) => it.kind).lastIndexOf("user");
  const firstUser = items.findIndex((it) => it.kind === "user");
  return (
    <>
      {/* no live region on the whole list (it re-read every streamed word): the status lines
          (question, tours found, plan) announce themselves */}
      <ol aria-label={t.chat.history} className="flex flex-col gap-3">
        {items.map((it, i) => (
          <li
            key={i}
            data-turn={it.kind === "user" ? "" : undefined}
            className={`flex flex-col gap-1.5 ${i < lastUser ? "opacity-80" : ""} ${
              it.kind === "user" && i !== firstUser ? "mt-3 border-t border-white/10 pt-3" : ""
            }`}
          >
            {it.kind === "user" && (
              <p className={`max-w-[85%] self-end rounded-md bg-papier px-3.5 py-2 ${text} text-tinte shadow-sm`}>
                {it.text}
              </p>
            )}
            {it.kind === "assistant" && withoutFallback(items, i, it.text) && (
              <Answer body={withoutFallback(items, i, it.text)} short={turnHasCards(items, i)} />
            )}
            {it.kind === "understood" && (
              <div className="flex flex-col gap-1.5">
                {/* the recognised wishes as tags, always visible; the full sentence opens on demand */}
                <ul aria-label={t.chat.understood} className="flex flex-wrap gap-1.5">
                  {chipsFor(it.request, it.labels, locale)
                    .filter((c) => !c.warn)
                    .map((c, j) => (
                      <li key={j} className="rounded-md bg-white/12 px-2 py-0.5 text-[13px] text-papier ring-1 ring-white/10">
                        {c.text}
                      </li>
                    ))}
                </ul>
                <details className="group">
                  <summary className={`flex w-fit cursor-pointer list-none items-baseline gap-2 rounded text-[13px] ${focusRing}`}>
                    <span className="font-semibold text-sense">{t.chat.understoodShort}</span>
                    <span className="line-clamp-1 text-papier/75 group-open:line-clamp-none">
                      {it.text.replace(/^(Understood|Verstanden)\s*:\s*/i, "")}
                    </span>
                    <span aria-hidden="true" className="text-papier/60 transition-transform group-open:rotate-90">
                      ›
                    </span>
                  </summary>
                </details>
                {/* what cannot be checked never hides */}
                {chipsFor(it.request, it.labels, locale)
                  .filter((c) => c.warn)
                  .map((c, j) => (
                    <p key={j} className="w-fit rounded-md bg-amber-200 px-2 py-0.5 text-[13px] text-amber-950">
                      {c.text}
                    </p>
                  ))}
              </div>
            )}
            {it.kind === "clarify" && (
              <div className="flex flex-col gap-2">
                <p role="status" className={`${voice} font-medium`}>
                  {it.question}
                </p>
                {/* answered (a reply follows): the options go, the reply shows the choice */}
                {!items.slice(i + 1).some((x) => x.kind === "user") && it.options.length > 0 && (
                  <Options question={it.question} options={it.options} onOption={onOption} disabled={disabled} />
                )}
              </div>
            )}
            {it.kind === "results" && (
              <div className="flex flex-col gap-2">
                {it.fallback && (
                  <p role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-[13px] font-medium text-amber-950">
                    {it.fallback}
                  </p>
                )}
                <p role="status" className="flex items-center gap-2 text-sm font-semibold text-papier">
                  <span aria-hidden="true" className="text-sense">
                    ✓
                  </span>
                  <span>{foundText(it.cards, locale)}</span>
                  {it.cards.length >= 2 && <span className="hidden font-normal text-papier/70 md:inline">{t.chat.seeCards}</span>}
                </p>
              </div>
            )}
            {it.kind === "plan" && (
              <p role="status" className="flex items-center gap-2 text-sm font-semibold text-papier">
                <span aria-hidden="true" className="text-sense">
                  ✓
                </span>
                <span>{it.summary}</span>
              </p>
            )}
            {it.kind === "weather_days" && <WeatherDays data={it.data} />}
            {it.kind === "groups" && <GroupList groups={it.groups} note={it.note} />}
            {it.kind === "events" && <EventCards events={it.events} fallback={it.fallback} note={it.note} />}
            {it.kind === "sources" && (
              <details className="text-[13px] text-papier/75">
                <summary className={`w-fit cursor-pointer list-none rounded hover:text-papier ${focusRing}`}>
                  <span aria-hidden="true">ⓘ </span>
                  {t.chat.sourcesCount(it.sources.length)}
                  {it.sources.some((s) => s.status === "entwurf") && (
                    <span className="ml-1 rounded bg-amber-200 px-1 text-amber-950">{t.chat.draft}</span>
                  )}
                </summary>
                <ul aria-label={t.chat.sources} className="mt-1 flex flex-col gap-1 pl-4">
                  {it.sources.map((s) => (
                    <li key={`${s.id}|${s.url ?? ""}`}>
                      {t.chat.source}{" "}
                      {s.url ? (
                        <a href={s.url} target="_blank" rel="noreferrer" className="underline decoration-papier/40 underline-offset-2">
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
              </details>
            )}
            {it.kind === "notice" && <p className={meta}>{it.text}</p>}
            {it.kind === "error" && (
              <p role="alert" className={`${alertBox} bg-red-100 text-red-900`}>
                {it.text}
              </p>
            )}
            {it.kind === "signInHint" && (
              <p className="text-sm leading-relaxed">
                {it.text}{" "}
                <Link href="/anmelden" className="font-semibold text-sense underline underline-offset-2">
                  {t.chat.signIn}
                </Link>
              </p>
            )}
            {it.kind === "auth" && (
              <p role="alert" className={`${alertBox} bg-red-100 text-red-900`}>
                {t.chat.sessionExpired}{" "}
                <Link href="/anmelden" className="underline">
                  {t.chat.signIn}
                </Link>
              </p>
            )}
          </li>
        ))}
      </ol>
    </>
  );
}
