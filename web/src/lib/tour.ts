import { messagesFor, type Locale } from "../i18n/locale";
import type { TrailPoi } from "./data";
import { num } from "./format";

/**
 * Text and labels for the trail page, built from data only (never from the model): every number
 * comes from the database, a missing value is left out instead of shown as 0.
 */

export type PoiGroup = "einkehr" | "aussicht" | "wasserfall";

export const POI_KIND: Record<TrailPoi["kind"], { icon: string; group: PoiGroup }> = {
  food: { icon: "☕", group: "einkehr" },
  hut: { icon: "🏠", group: "einkehr" },
  viewpoint: { icon: "👁", group: "aussicht" },
  peak: { icon: "⛰", group: "aussicht" },
  waterfall: { icon: "💧", group: "wasserfall" },
};

/** Name of a POI kind in the UI language. */
export function poiKindLabel(kind: TrailPoi["kind"], locale: Locale = "de"): string {
  return messagesFor(locale).tour.poiKinds[kind];
}

/** Labels of the controlled vocabulary (data/tags/features.yaml), keyed by tag_id in the catalog; unknown tags are left out. */
export function tagLabels(tags: string[], locale: Locale = "de"): string[] {
  const labels = messagesFor(locale).tour.tags as Record<string, string>;
  return tags.flatMap((t) => (labels[t] ? [labels[t]] : []));
}

const MIN_SHARE_PCT = 5;

export function surfaceLine(shares: Record<string, number> | null, locale: Locale = "de"): string | null {
  if (!shares) return null;
  const t = messagesFor(locale).tour;
  const kinds = t.surfaceKinds as Record<string, string>;
  const parts = Object.entries(shares)
    .map(([k, v]) => [kinds[k] ?? k, Math.round(v * 100)] as const)
    .filter(([, pct]) => pct >= MIN_SHARE_PCT)
    .sort((a, b) => b[1] - a[1]);
  return parts.length ? t.surfaceLine(parts.map(([l, pct]) => t.surfaceShare(pct, l)).join(" · ")) : null;
}

export function describeTour(
  t: {
    roundtrip: boolean;
    length_km: number | null;
    ascent_m: number | null;
    time: string | null;
    pois: TrailPoi[];
  },
  locale: Locale = "de",
): string | null {
  if (t.length_km === null) return null;
  const m = messagesFor(locale).tour;
  let first = `${t.roundtrip ? m.roundWalk : m.walk}, ${num(t.length_km, locale, { min: 1 })} km`;
  if (t.ascent_m !== null) first += m.withAscent(num(t.ascent_m, locale, { max: 0 }));
  if (t.time) first += m.walkingTimeAbout(t.time);
  const counts: Record<PoiGroup, number> = { einkehr: 0, aussicht: 0, wasserfall: 0 };
  for (const p of t.pois) counts[POI_KIND[p.kind].group]++;
  const stops = (Object.keys(m.poiNouns) as PoiGroup[])
    .filter((g) => counts[g] > 0)
    .map((g) => `${counts[g]} ${counts[g] === 1 ? m.poiNouns[g].one : m.poiNouns[g].other}`);
  const list = stops.length <= 1 ? stops.join("") : `${stops.slice(0, -1).join(", ")} ${m.and} ${stops[stops.length - 1]}`;
  return stops.length ? `${first}. ${m.alongTheWay(list)}` : `${first}.`;
}
