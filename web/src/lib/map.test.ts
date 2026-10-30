import type { LineString } from "geojson";
import type { LodgingOnTrail, TrailDetail } from "./data";
import { bboxOf, dayFeatures, daySections, BASEMAP_STYLE, lodgingsNearby, mapTrail, safeWebsite, trailToFeatures } from "./map";

const line = (...coords: [number, number][]): LineString => ({ type: "LineString", coordinates: coords });

function detailWithStages(n: number): TrailDetail {
  return {
    id: "w", name: "W", kind: "long_distance", length_km: 10 * n, ascent_m: null, descent_m: null,
    stage_count: n, center_lat: 48, cover: null, photos: [], sources: [],
    geom: line(...Array.from({ length: n + 1 }, (_, i) => [8, 48 - i * 0.1] as [number, number])),
    stages: Array.from({ length: n }, (_, i) => ({
      id: `w-${i + 1}`, seq: i + 1, name: `S${i} – S${i + 1}`, start_name: `S${i}`, end_name: `S${i + 1}`,
      length_km: 10, ascent_m: null, descent_m: null, photos: [],
      geom: line([8, 48 - i * 0.1], [8.05, 48 - i * 0.1 - 0.05], [8, 48 - (i + 1) * 0.1]),
    })),
  };
}

test("trailToFeatures makes one line per stage and boundary points", () => {
  const fc = trailToFeatures(detailWithStages(3));
  expect(fc.features.filter((f) => f.geometry.type === "LineString")).toHaveLength(3);
  expect(fc.features.filter((f) => f.geometry.type === "Point")).toHaveLength(4);
});

test("stage lines carry their seq, boundary points the place names in order", () => {
  const fc = trailToFeatures(detailWithStages(3));
  const lines = fc.features.filter((f) => f.geometry.type === "LineString");
  expect(lines.map((f) => f.properties?.seq)).toEqual([1, 2, 3]);
  const points = fc.features.filter((f) => f.geometry.type === "Point");
  expect(points.map((f) => f.properties?.name)).toEqual(["S0", "S1", "S2", "S3"]);
  expect(points.map((f) => (f.geometry as { coordinates: number[] }).coordinates)).toEqual([
    [8, 48], [8, 47.9], [8, 47.8], [8, 47.7],
  ]);
});

test("day hike without stages: the trail line plus start and end point", () => {
  const hike = { ...detailWithStages(0), kind: "day_hike" as const, geom: line([8, 48], [8.1, 48.1], [8.2, 48]) };
  const fc = trailToFeatures(hike);
  const lines = fc.features.filter((f) => f.geometry.type === "LineString");
  expect(lines).toHaveLength(1);
  expect(lines[0].geometry).toEqual(hike.geom);
  const points = fc.features.filter((f) => f.geometry.type === "Point");
  expect(points.map((f) => (f.geometry as { coordinates: number[] }).coordinates)).toEqual([[8, 48], [8.2, 48]]);
  expect(points.map((f) => f.properties?.name)).toEqual(["Start", "Ziel"]);
});

test("no geometry at all gives an empty collection", () => {
  expect(trailToFeatures({ ...detailWithStages(0), geom: null }).features).toEqual([]);
});

test("bboxOf", () => {
  expect(bboxOf({ type: "LineString", coordinates: [[8, 48], [8.2, 47.9]] })).toEqual([8, 47.9, 8.2, 48]);
});

test("bboxOf a feature collection spans all features; empty is null", () => {
  expect(bboxOf(trailToFeatures(detailWithStages(2)))).toEqual([8, 47.8, 8.05, 48]);
  expect(bboxOf({ type: "FeatureCollection", features: [] })).toBeNull();
});

test("mapTrail drops the trail line when every stage has its own", () => {
  expect(mapTrail(detailWithStages(2)).geom).toBeNull();
  const hike = { ...detailWithStages(0), geom: line([8, 48], [8.1, 48]) };
  expect(mapTrail(hike).geom).toEqual(hike.geom);
  expect(mapTrail(detailWithStages(2))).not.toHaveProperty("photos");
});

test("lodgingsNearby keeps lodgings up to 1 km from the trail, unknown distance excluded", () => {
  const l = (id: number, dist_m: number | null): LodgingOnTrail => ({
    id, name: `L${id}`, kind: "hotel", website: null, dist_m, along_km: null, lon: 8, lat: 48,
  });
  const kept = lodgingsNearby([l(1, 0), l(2, 1000), l(3, 1001), l(4, null), l(5, 450)]);
  expect(kept.map((x) => x.id)).toEqual([1, 2, 5]);
});

test("basemap.de style URL", () => {
  expect(BASEMAP_STYLE).toBe("https://sgx.geodatenzentrum.de/gdz_basemapde_vektor/styles/bm_web_col.json");
});

test("safeWebsite links only http(s) and adds a missing scheme", () => {
  expect(safeWebsite("https://a.de/x")).toBe("https://a.de/x");
  expect(safeWebsite("www.pension.de")).toBe("https://www.pension.de/");
  expect(safeWebsite("javascript:alert(1)")).toBeNull();
  expect(safeWebsite(null)).toBeNull();
});

describe("daySections", () => {
  // 0.1 degree of latitude is ~11.1 km
  const l: [number, number][] = [[8, 48], [8, 48.1], [8, 48.2], [8, 48.3]];
  it("cuts the line at the plan km, scaled to the trail length", () => {
    const secs = daySections(l, [
      { day: 1, start_km: 0, end_km: 15, stop: { name: "A" } },
      { day: 2, start_km: 15, end_km: 33.3, stop: null },
    ], 33.3);
    expect(secs.map((s) => s.day)).toEqual([1, 2]);
    const c1 = secs[0].geom.coordinates;
    expect(c1[0]).toEqual([8, 48]);
    expect(c1[c1.length - 1][1]).toBeCloseTo(48 + (15 / 33.3) * 0.3, 3);
    expect(secs[1].geom.coordinates[secs[1].geom.coordinates.length - 1][1]).toBeCloseTo(48.3, 3);
    expect(secs[0].end_name).toBe("A");
    expect(dayFeatures(secs).features.filter((f) => f.properties?.kind === "boundary")).toHaveLength(2);
  });
  it("draws nothing without a line", () => {
    expect(daySections([[8, 48]], [{ day: 1, start_km: 0, end_km: 1, stop: null }])).toEqual([]);
  });
});
