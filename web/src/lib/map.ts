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
