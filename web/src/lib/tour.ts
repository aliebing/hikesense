import type { TrailPoi } from "./data";

/**
 * Text and labels for the trail page, built from data only (never from the model): every number
 * comes from the database, a missing value is left out instead of shown as 0.
 */

type PoiGroup = "einkehr" | "aussicht" | "wasserfall";

export const POI_KIND: Record<TrailPoi["kind"], { icon: string; label: string; group: PoiGroup }> = {
  food: { icon: "☕", label: "Einkehr", group: "einkehr" },
  hut: { icon: "🏠", label: "Hütte", group: "einkehr" },
  viewpoint: { icon: "👁", label: "Aussicht", group: "aussicht" },
  peak: { icon: "⛰", label: "Gipfel", group: "aussicht" },
  waterfall: { icon: "💧", label: "Wasserfall", group: "wasserfall" },
};

/** Labels of the controlled vocabulary (data/tags/features.yaml). */
export const TAG_LABEL: Record<string, string> = {
  "feature:aussicht": "Aussicht",
  "feature:gipfel": "Gipfel",
  "feature:wasserfall": "Wasserfall",
  "feature:einkehr": "Einkehr",
  "feature:bahnhof": "Bahnhof",
  "feature:rundweg": "Rundweg",
  "surface:wenig_asphalt": "Wenig Asphalt",
  "surface:naturweg": "Naturweg",
  "surface:gut_laufbar": "Gut laufbar",
};

export function tagLabels(tags: string[]): string[] {
  return tags.flatMap((t) => (TAG_LABEL[t] ? [TAG_LABEL[t]] : []));
}

const SURFACE_LABEL: Record<string, string> = { paved: "Asphalt", gravel: "Schotter", unpaved: "naturbelassen", unknown: "unbekannt" };
const MIN_SHARE_PCT = 5;

export function surfaceLine(shares: Record<string, number> | null): string | null {
  if (!shares) return null;
  const parts = Object.entries(shares)
    .map(([k, v]) => [SURFACE_LABEL[k] ?? k, Math.round(v * 100)] as const)
    .filter(([, pct]) => pct >= MIN_SHARE_PCT)
    .sort((a, b) => b[1] - a[1]);
  return parts.length ? `Belag: ${parts.map(([l, pct]) => `${pct} % ${l}`).join(" · ")}` : null;
}

const de1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const de0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

const NOUN: Record<PoiGroup, [string, string]> = {
  einkehr: ["Einkehrmöglichkeit", "Einkehrmöglichkeiten"],
  aussicht: ["Aussichtspunkt", "Aussichtspunkte"],
  wasserfall: ["Wasserfall", "Wasserfälle"],
};

function listDe(parts: string[]): string {
  return parts.length <= 1 ? parts.join("") : `${parts.slice(0, -1).join(", ")} und ${parts[parts.length - 1]}`;
}

export function describeTour(t: {
  roundtrip: boolean;
  length_km: number | null;
  ascent_m: number | null;
  time: string | null;
  pois: TrailPoi[];
}): string | null {
  if (t.length_km === null) return null;
  let first = `${t.roundtrip ? "Rundweg" : "Tour"}, ${de1.format(t.length_km)} km`;
  if (t.ascent_m !== null) first += ` mit ${de0.format(t.ascent_m)} m Aufstieg`;
  if (t.time) first += `, Gehzeit etwa ${t.time} nach DIN 33466`;
  const counts: Record<PoiGroup, number> = { einkehr: 0, aussicht: 0, wasserfall: 0 };
  for (const p of t.pois) counts[POI_KIND[p.kind].group]++;
  const stops = (Object.keys(NOUN) as PoiGroup[])
    .filter((g) => counts[g] > 0)
    .map((g) => `${counts[g]} ${NOUN[g][counts[g] === 1 ? 0 : 1]}`);
  return stops.length ? `${first}. Unterwegs ${listDe(stops)}.` : `${first}.`;
}
