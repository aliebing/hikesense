import type { PlanStop } from "./chat";
import { safeWebsite } from "./map";

/** Shown for a number that is missing (never 0 or a guess). */
export const UNKNOWN = "unbekannt";

/** A finite number formatted, else „unbekannt“. */
export function numOr(v: number | null | undefined, fmt: (n: number) => string): string {
  return typeof v === "number" && Number.isFinite(v) ? fmt(v) : UNKNOWN;
}

/**
 * The one place for the web search used when a lodging has no website: DuckDuckGo, query „<Name> <Ort>“.
 * The plan carries no place name per lodging, so the region stands in for the place.
 */
export function searchLink(name: string, place = "Schwarzwald"): string {
  return `https://duckduckgo.com/?q=${encodeURIComponent(`${name} ${place}`)}`;
}

/** Website if it is a safe http(s) link, else a search for the name; null without a name. */
export function lodgingLink(stop: Pick<PlanStop, "name" | "website">): { href: string; label: string } | null {
  const site = safeWebsite(stop.website);
  if (site) return { href: site, label: "Website" };
  return stop.name ? { href: searchLink(stop.name), label: "Suchen" } : null;
}
