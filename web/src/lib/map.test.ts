import type { LineString } from "geojson";
import type { LodgingOnTrail, TrailDetail } from "./data";
import { haversineKm } from "./geo";
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
  const fc = trailToFeatures(detailWithStages(3), "de");
  expect(fc.features.filter((f) => f.geometry.type === "LineString")).toHaveLength(3);
  expect(fc.features.filter((f) => f.geometry.type === "Point")).toHaveLength(4);
});

test("stage lines carry their seq, boundary points the place names in order", () => {
  const fc = trailToFeatures(detailWithStages(3), "de");
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
  const fc = trailToFeatures(hike, "de");
  const lines = fc.features.filter((f) => f.geometry.type === "LineString");
  expect(lines).toHaveLength(1);
  expect(lines[0].geometry).toEqual(hike.geom);
  const points = fc.features.filter((f) => f.geometry.type === "Point");
  expect(points.map((f) => (f.geometry as { coordinates: number[] }).coordinates)).toEqual([[8, 48], [8.2, 48]]);
  expect(points.map((f) => f.properties?.name)).toEqual(["Start", "Ziel"]);
});

test("no geometry at all gives an empty collection", () => {
  expect(trailToFeatures({ ...detailWithStages(0), geom: null }, "de").features).toEqual([]);
});

test("bboxOf", () => {
  expect(bboxOf({ type: "LineString", coordinates: [[8, 48], [8.2, 47.9]] })).toEqual([8, 47.9, 8.2, 48]);
});

test("bboxOf a feature collection spans all features; empty is null", () => {
  expect(bboxOf(trailToFeatures(detailWithStages(2), "de"))).toEqual([8, 47.8, 8.05, 48]);
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
  const days = (stops: { id: number; km: number }[]) =>
    stops.map((st, i) => ({ day: i + 1, start_km: i ? stops[i - 1].km : 0, end_km: st.km, stop: { lodging_id: st.id, name: `L${st.id}` } }));

  it("cuts at the backend's along_km: fraction of the metric (geodesic) line length", () => {
    // L-shaped line: north leg 0.2° lat ≈ 22.2 km, east leg 0.2° lon at 48.2° N ≈ 14.8 km.
    // Planar degree shares are 50/50 there, metric ones ≈ 60/40 — the cut must follow the metric share.
    const line: [number, number][] = [[8, 48], [8, 48.2], [8.2, 48.2]];
    const north = haversineKm([48, 8], [48.2, 8]);
    const east = haversineKm([48.2, 8], [48.2, 8.2]);
    const length = 40; // trails.length_km; along_km = metric fraction × length_km
    const along = 0.75 * length;
    const secs = daySections(line, days([{ id: 1, km: along }, { id: 2, km: length }]), length);
    const c = secs[0].geom.coordinates;
    const expectedLon = 8 + 0.2 * ((0.75 * (north + east) - north) / east); // ≈ 8.075, planar would give 8.1
    expect(c[0]).toEqual([8, 48]);
    expect(c[c.length - 1][0]).toBeCloseTo(expectedLon, 6);
    expect(c[c.length - 1][0]).toBeLessThan(8.08);
    expect(c[c.length - 1][1]).toBeCloseTo(48.2, 9);
    expect(c).toContainEqual([8, 48.2]); // the vertex before the cut stays
    expect(secs[1].geom.coordinates[0][0]).toBeCloseTo(expectedLon, 6);
  });

  it("half the length lies on the longer north leg, not at the corner", () => {
    const line: [number, number][] = [[8, 48], [8, 48.2], [8.2, 48.2]];
    const secs = daySections(line, days([{ id: 1, km: 20 }, { id: 2, km: 40 }]), 40);
    const end = secs[0].geom.coordinates[secs[0].geom.coordinates.length - 1];
    expect(end[0]).toBeCloseTo(8, 9);
    expect(end[1]).toBeGreaterThan(48.15);
    expect(end[1]).toBeLessThan(48.18);
  });

  it("puts the day-end marker at the lodging, flags a stop that is not loaded", () => {
    const line: [number, number][] = [[8, 48], [8, 48.2], [8.2, 48.2]];
    const secs = daySections(line, days([{ id: 1, km: 25 }, { id: 2, km: 40 }]), 40, (id) => (id === 1 ? [8.05, 48.21] : null));
    expect(secs.map((s) => s.lodging_missing)).toEqual([false, true]);
    const ends = dayFeatures(secs, "de").features.filter((f) => f.properties?.kind === "boundary");
    expect((ends[0].geometry as { coordinates: number[] }).coordinates).toEqual([8.05, 48.21]);
  });

  it("labels day ends and start/finish in the requested language", () => {
    const line: [number, number][] = [[8, 48], [8, 48.2], [8.2, 48.2]];
    const secs = daySections(line, days([{ id: 1, km: 25 }, { id: 2, km: 40 }]), 40);
    const named = secs.map((x, i) => ({ ...x, end_name: i === 0 ? "Hut" : null }));
    const names = (l: "de" | "en") => dayFeatures(named, l).features.filter((f) => f.properties?.kind === "boundary").map((f) => f.properties?.name);
    expect(names("en")).toEqual(["Day 1: Hut", "End of day 2"]);
    expect(names("de")).toEqual(["Tag 1: Hut", "Ende Tag 2"]);
    const hike = { ...detailWithStages(0), geom: line as never };
    const hikeLine = { type: "LineString" as const, coordinates: line };
    expect(trailToFeatures({ ...hike, geom: hikeLine }, "en").features.filter((f) => f.geometry.type === "Point").map((f) => f.properties?.name)).toEqual(["Start", "Finish"]);
  });

  it("draws nothing without a line or the trail length", () => {
    expect(daySections([[8, 48]], days([{ id: 1, km: 1 }]), 1)).toEqual([]);
    expect(daySections([[8, 48], [8, 49]], days([{ id: 1, km: 1 }]), null)).toEqual([]);
  });
});
