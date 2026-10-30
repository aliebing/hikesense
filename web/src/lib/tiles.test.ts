import { describe, expect, it } from "vitest";
import { arrangeTiles } from "./tiles";
import type { TrailSummary } from "./data";
import type { TourCard } from "./chat";

const trail = (n: number): TrailSummary => ({
  id: `t${n}`,
  name: `Tour ${n}`,
  kind: "day_hike",
  length_km: 10,
  ascent_m: 100,
  descent_m: 100,
  stage_count: 1,
  center_lat: 48,
  cover: { url: `/p${n}.jpg`, thumb_url: `/t${n}.jpg`, author: "A", license: "CC", license_url: null, page_url: null },
});
const pool = (n: number) => Array.from({ length: n }, (_, i) => trail(i));
const card = (id: string, over: Partial<TourCard> = {}): TourCard => ({
  trail_id: id,
  name: `Name ${id}`,
  length_km: 10,
  ascent_m: 100,
  duration_h: 3,
  distance_km: null,
  cover_thumb_url: "/c.jpg",
  cover_author: "Autor",
  cover_license: "CC BY",
  cover_license_url: null,
  cover_page_url: null,
  results: [],
  deviation_text: null,
  preference: { score: 0, met: [], missing: [], avoided_hit: [] },
  ...over,
});

describe("arrangeTiles", () => {
  it("fills rows without duplicates", () => {
    const rows = arrangeTiles(pool(30), [], 3, 8);
    expect(rows.map((r) => r.length)).toEqual([8, 8, 8]);
    expect(new Set(rows.flat().map((t) => t.id)).size).toBe(24);
    expect(rows.flat().every((t) => t.match === null)).toBe(true);
  });

  it("small pool", () => {
    const rows = arrangeTiles(pool(5), [], 3, 8);
    const ids = rows.flat().map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
    expect(ids.length).toBe(5);
    expect(rows.every((r) => r.length > 0)).toBe(true);
  });

  it("matches become clear in place", () => {
    const rows = arrangeTiles(pool(30), [card("t3")], 3, 8);
    const hits = rows.flat().filter((t) => t.id === "t3");
    expect(hits).toHaveLength(1);
    expect(hits[0].match).not.toBeNull();
    expect(rows[0][3]).toBe(hits[0]);
  });

  it("inserts a match that is not in the pool", () => {
    const rows = arrangeTiles(pool(30), [card("neu")], 3, 8);
    expect(rows.flat()).toHaveLength(24);
    expect(rows.flat().filter((t) => t.id === "neu")).toHaveLength(1);
  });

  it("pool matches keep their place regardless of card order", () => {
    const rows = arrangeTiles(pool(30), [card("neu"), card("t1")], 3, 8);
    expect(rows[0][1].id).toBe("t1");
    expect(rows[0][1].match).not.toBeNull();
    expect(rows.flat().filter((t) => t.id === "neu")).toHaveLength(1);
    expect(rows.flat().filter((t) => t.id === "t1")).toHaveLength(1);
  });

  it("spreads matches one per row first", () => {
    const rows = arrangeTiles(pool(30), [card("x1"), card("x2"), card("x3")], 3, 8);
    expect(rows.map((r) => r.filter((t) => t.match).length)).toEqual([1, 1, 1]);
  });

  it("match without photo", () => {
    const [[t]] = arrangeTiles([], [card("neu", { cover_author: null })], 3, 8);
    expect(t.photo).toBeNull();
    expect(t.match).not.toBeNull();
  });

  it("at most five matches", () => {
    const cards = Array.from({ length: 7 }, (_, i) => card(`m${i}`));
    const tiles = arrangeTiles(pool(30), cards, 3, 8).flat().filter((t) => t.match);
    expect(tiles.map((t) => t.id).sort()).toEqual(["m0", "m1", "m2", "m3", "m4"]);
  });

  it("fallback carries the deviation", () => {
    const tiles = arrangeTiles(pool(30), [card("neu", { deviation_text: "340 Hm statt < 200" })], 3, 8).flat();
    expect(tiles.find((t) => t.id === "neu")?.match?.deviation).toBe("340 Hm statt < 200");
  });
});
