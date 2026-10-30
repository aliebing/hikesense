import type { Feature, FeatureCollection, Geometry, LineString, Position } from "geojson";
import type { LodgingOnTrail, Stage, TrailDetail } from "./data";

/** Vector basemap of the BKG (basemap.de), colour variant. */
export const BASEMAP_STYLE = "https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/styles/bm_web_col.json";

export const ATTRIBUTION = ["© BKG (basemap.de) CC BY 4.0", "© OpenStreetMap-Mitwirkende, ODbL"] as const;

/** Fallback when the basemap.de style cannot be loaded: OSM raster tiles. */
export const OSM_RASTER_STYLE = {
  version: 8 as const,
  sources: {
    osm: {
      type: "raster" as const,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      maxzoom: 19,
    },
  },
  layers: [{ id: "osm", type: "raster" as const, source: "osm" }],
};

/** Lodgings shown on the map: at most this far from the trail (trail_lodgings.dist_m). */
export const LODGING_MAX_DIST_M = 1000;

/** Just what the map needs from a trail (keeps photos etc. out of the client props). */
export type MapTrail = {
  name: string;
  geom: LineString | null;
  stages: Pick<Stage, "seq" | "start_name" | "end_name" | "geom">[];
};

export function mapTrail(detail: TrailDetail): MapTrail {
  const stages = detail.stages.map(({ seq, start_name, end_name, geom }) => ({ seq, start_name, end_name, geom }));
  const allStagesHaveGeom = stages.length > 0 && stages.every((s) => s.geom);
  // The trail line is only needed when stages cannot draw it (day hikes).
  return { name: detail.name, geom: allStagesHaveGeom ? null : detail.geom, stages };
}

/** Lines (`kind: "stage"`, with `seq`) and boundary points (`kind: "boundary"`, with `name`). */
export type TrailFeatureProps = { kind: "stage" | "boundary"; seq?: number; name?: string };

const point = (coordinates: Position, name: string): Feature<Geometry, TrailFeatureProps> => ({
  type: "Feature",
  geometry: { type: "Point", coordinates },
  properties: { kind: "boundary", name },
});

/**
 * One line per stage (with `seq`, for alternating colours) and points at the
 * stage boundaries (start of every stage plus the end of the last). Without
 * stage geometries (day hikes) the trail line is used, with start and end.
 */
export function trailToFeatures(trail: Pick<MapTrail, "geom" | "stages">): FeatureCollection<Geometry, TrailFeatureProps> {
  const stages = [...trail.stages].filter((s) => s.geom && s.geom.coordinates.length > 0).sort((a, b) => a.seq - b.seq);
  const features: Feature<Geometry, TrailFeatureProps>[] = [];
  if (stages.length > 0) {
    for (const s of stages) features.push({ type: "Feature", geometry: s.geom!, properties: { kind: "stage", seq: s.seq } });
    for (const s of stages) features.push(point(s.geom!.coordinates[0], s.start_name));
    const last = stages[stages.length - 1];
    features.push(point(last.geom!.coordinates[last.geom!.coordinates.length - 1], last.end_name));
  } else if (trail.geom && trail.geom.coordinates.length > 0) {
    const c = trail.geom.coordinates;
    features.push({ type: "Feature", geometry: trail.geom, properties: { kind: "stage", seq: 1 } });
    features.push(point(c[0], "Start"), point(c[c.length - 1], "Ziel"));
  }
  return { type: "FeatureCollection", features };
}

type Bbox = [number, number, number, number];

function positions(g: Geometry | FeatureCollection): Position[] {
  switch (g.type) {
    case "FeatureCollection":
      return g.features.flatMap((f) => (f.geometry ? positions(f.geometry) : []));
    case "GeometryCollection":
      return g.geometries.flatMap(positions);
    case "Point":
      return [g.coordinates];
    case "LineString":
    case "MultiPoint":
      return g.coordinates;
    case "Polygon":
    case "MultiLineString":
      return g.coordinates.flat();
    case "MultiPolygon":
      return g.coordinates.flat(2);
  }
}

/** [west, south, east, north]; null when there are no coordinates. */
export function bboxOf(geom: Geometry | FeatureCollection): Bbox | null {
  const ps = positions(geom);
  if (ps.length === 0) return null;
  let [w, s, e, n] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const [x, y] of ps) {
    if (x < w) w = x;
    if (x > e) e = x;
    if (y < s) s = y;
    if (y > n) n = y;
  }
  return [w, s, e, n];
}

/** Lodgings within LODGING_MAX_DIST_M of the trail; unknown distance is not shown. */
export function lodgingsNearby(lodgings: LodgingOnTrail[], maxM = LODGING_MAX_DIST_M): LodgingOnTrail[] {
  return lodgings.filter((l) => l.dist_m !== null && l.dist_m <= maxM);
}

const KIND_LABEL: Record<string, string> = {
  hotel: "Hotel",
  guest_house: "Pension",
  apartment: "Ferienwohnung",
  chalet: "Ferienhaus",
  hostel: "Hostel",
  camp_site: "Campingplatz",
  alpine_hut: "Berghütte",
  wilderness_hut: "Schutzhütte",
};

export function lodgingKind(kind: string | null): string {
  return (kind && KIND_LABEL[kind]) ?? "Unterkunft";
}

/** Only http(s) links from OSM are rendered as links. */
export function safeWebsite(url: string | null): string | null {
  if (!url) return null;
  const u = /^https?:\/\//i.test(url) ? url : `https://${url}`;
  try {
    const parsed = new URL(u);
    return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : null;
  } catch {
    return null;
  }
}

/** One plan day on the map: its slice of the trail and where it ends. */
export type DaySection = {
  day: number;
  geom: LineString;
  end_name: string | null;
  /** the stop's lodging position (marker); null: the day ends at the trail end or the lodging is not on the map */
  end: Position | null;
  /** the day has a lodging stop that could not be placed on the map */
  lodging_missing: boolean;
};

/** The whole trail as one line: the trail geometry, else the stage lines in order. */
export function trailLine(trail: Pick<MapTrail, "geom" | "stages">): Position[] {
  if (trail.geom && trail.geom.coordinates.length > 1) return trail.geom.coordinates;
  return [...trail.stages].sort((a, b) => a.seq - b.seq).flatMap((s) => s.geom?.coordinates ?? []);
}

/**
 * Cuts the trail line at the plan's km marks with the backend's own measure: along_km is
 * ST_LineLocatePoint(line, point) × length_km, a fraction of the line's planar (lon/lat degree) length,
 * so km / totalKm is that fraction here. Without the trail's length nothing can be placed: no sections.
 * `lodgingAt` gives the lodging position of a stop (marker); a stop without one is flagged, not hidden.
 */
export function daySections(
  line: Position[],
  days: { day: number; start_km: number; end_km: number; stop: { lodging_id: number; name: string | null } | null }[],
  totalKm: number | null | undefined,
  lodgingAt: (id: number) => Position | null = () => null,
): DaySection[] {
  if (line.length < 2 || !totalKm || totalKm <= 0) return [];
  const cum = [0];
  for (let i = 1; i < line.length; i++) cum.push(cum[i - 1] + Math.hypot(line[i][0] - line[i - 1][0], line[i][1] - line[i - 1][1]));
  const total = cum[cum.length - 1];
  if (total <= 0) return [];
  const at = (km: number): Position => {
    const d = (Math.min(Math.max(km, 0), totalKm) / totalKm) * total;
    let i = 1;
    while (i < cum.length - 1 && cum[i] < d) i++;
    const span = cum[i] - cum[i - 1];
    const t = span > 0 ? (d - cum[i - 1]) / span : 0;
    return [line[i - 1][0] + (line[i][0] - line[i - 1][0]) * t, line[i - 1][1] + (line[i][1] - line[i - 1][1]) * t];
  };
  const out: DaySection[] = [];
  for (const d of days) {
    const a = (Math.min(d.start_km, d.end_km) / totalKm) * total;
    const b = (Math.max(d.start_km, d.end_km) / totalKm) * total;
    const coords: Position[] = [at(d.start_km)];
    for (let i = 0; i < line.length; i++) if (cum[i] > a && cum[i] < b) coords.push(line[i]);
    coords.push(at(d.end_km));
    const end = d.stop ? lodgingAt(d.stop.lodging_id) : null;
    if (coords.length >= 2) {
      out.push({ day: d.day, geom: { type: "LineString", coordinates: coords }, end_name: d.stop?.name ?? null, end, lodging_missing: !!d.stop && !end });
    }
  }
  return out;
}

/** Day sections as map features: lines (`seq` = day, for alternating colours) and a point at every day end. */
export function dayFeatures(days: DaySection[]): FeatureCollection<Geometry, TrailFeatureProps> {
  const features: Feature<Geometry, TrailFeatureProps>[] = [];
  for (const d of days) features.push({ type: "Feature", geometry: d.geom, properties: { kind: "stage", seq: d.day } });
  for (const d of days) {
    const c = d.geom.coordinates;
    features.push(point(d.end ?? c[c.length - 1], d.end_name ? `Tag ${d.day}: ${d.end_name}` : `Ende Tag ${d.day}`));
  }
  return { type: "FeatureCollection", features };
}
