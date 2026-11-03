import { messagesFor, type Locale } from "../i18n/locale";
import { isLandscape } from "./backdrop";
import type { PlanStop } from "./chat";
import type { Photo } from "./data";
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

/**
 * One photo per plan day: from the stage its midpoint lies on (stage km from the stage lengths
 * in order), landscapes first; if that stage has nothing left, the nearest stage that does.
 * No photo twice; rather none.
 */
export function dayPhotos(
  days: { start_km: number; end_km: number }[],
  stages: { length_km: number | null; photos: Photo[] }[],
): (Photo | null)[] {
  const ends: number[] = [];
  let km = 0;
  for (const s of stages) ends.push((km += s.length_km ?? 0));
  const used = new Set<string>();
  const free = (i: number) =>
    [...stages[i].photos].sort((a, b) => Number(isLandscape(b)) - Number(isLandscape(a))).find((p) => !used.has(p.url));
  return days.map((d) => {
    if (stages.length === 0) return null;
    const mid = (d.start_km + d.end_km) / 2;
    const found = ends.findIndex((e) => mid < e);
    const at = found === -1 ? stages.length - 1 : found; // beyond the last stage end: the last stage
    for (let off = 0; off < stages.length; off++) {
      for (const i of off === 0 ? [at] : [at + off, at - off]) {
        if (i < 0 || i >= stages.length) continue;
        const p = free(i);
        if (p) {
          used.add(p.url);
          return p;
        }
      }
    }
    return null;
  });
}
