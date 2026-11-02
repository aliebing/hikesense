import { messagesFor, type Locale } from "../i18n/locale";
import type { PlanStop } from "./chat";
import { safeWebsite } from "./map";

/** A finite number formatted, else „unbekannt“ / "unknown". */
export function numOr(v: number | null | undefined, fmt: (n: number) => string, locale: Locale): string {
  return typeof v === "number" && Number.isFinite(v) ? fmt(v) : messagesFor(locale).plan.unknown;
}

/**
 * The one place for the web search used when a lodging has no website: DuckDuckGo, query „<Name> <Ort>“.
 * The plan carries no place name per lodging, so the caller passes the plan's start place
 * (else the trail name); without any place only the name is searched – never a fixed region.
 */
export function searchLink(name: string, place?: string | null): string {
  return `https://duckduckgo.com/?q=${encodeURIComponent(place ? `${name} ${place}` : name)}`;
}

/** Website if it is a safe http(s) link, else a search for the name; null without a name. */
export function lodgingLink(stop: Pick<PlanStop, "name" | "website">, place: string | null | undefined, locale: Locale): { href: string; label: string } | null {
  const t = messagesFor(locale).tour;
  const site = safeWebsite(stop.website);
  if (site) return { href: site, label: t.website };
  return stop.name ? { href: searchLink(stop.name, place), label: t.search } : null;
}
