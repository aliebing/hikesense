import { toProfile, getTrails, photoPool, pickSpread, toSummary, type OverviewRow, type TrailSummary } from "./data";

const t = (id: string, lat: number | null, withCover = true): TrailSummary => ({
  id, name: id, kind: "day_hike", length_km: 10, ascent_m: 100, descent_m: 100,
  stage_count: 0, center_lat: lat,
  cover: withCover
    ? { url: "u", thumb_url: "t", author: "a", license: "CC0", license_url: null, page_url: null }
    : null,
});

test("pickSpread takes an even north-to-south spread of hikes with photos", () => {
  const hikes = Array.from({ length: 10 }, (_, i) => t(`d${i}`, 47 + i * 0.1));
  hikes.push(t("nophoto", 49, false));
  const picked = pickSpread(hikes, 4).map((h) => h.id);
  expect(picked).toEqual(["d9", "d6", "d3", "d0"]);
  expect(pickSpread(hikes, 4)).toEqual(pickSpread([...hikes].reverse(), 4)); // deterministic
  expect(pickSpread(hikes.slice(0, 2), 12).map((h) => h.id)).toEqual(["d1", "d0"]);
});

test("getTrails fails with a clear error when env is missing", async () => {
  const saved = { ...process.env };
  delete process.env.SUPABASE_URL;
  delete process.env.SUPABASE_ANON_KEY;
  delete process.env.NEXT_PUBLIC_SUPABASE_URL;
  delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  await expect(getTrails()).rejects.toThrow(/SUPABASE_URL/);
  process.env = saved;
});

test("toSummary keeps missing numbers as null instead of 0", () => {
  const row: OverviewRow = {
    id: "x", name: "X", kind: "day_hike", length_km: null, ascent_m: null, descent_m: null,
    stage_count: 0, center_lat: null, source_id: null, cover_url: null, cover_thumb_url: null,
    cover_author: null, cover_license: null, cover_license_url: null, cover_page_url: null,
  };
  const s = toSummary(row);
  expect(s.length_km).toBeNull();
  expect(s.ascent_m).toBeNull();
  expect(s.descent_m).toBeNull();
  expect(toSummary({ ...row, length_km: "14.83", ascent_m: 0 }).length_km).toBe(14.83); // 0 is a real value
  expect(toSummary({ ...row, ascent_m: 0 }).ascent_m).toBe(0);
});

test("photoPool counts only day hikes with a photo", () => {
  expect(photoPool([t("a", 48), t("b", 48.2, false), t("c", null)]).map((h) => h.id)).toEqual(["a"]);
});

test("toProfile keeps [km, m] pairs and refuses anything else", () => {
  expect(toProfile([[0, 100], [1.5, 120]])).toEqual([[0, 100], [1.5, 120]]);
  expect(toProfile(null)).toBeNull();
  expect(toProfile([[0, 100]])).toBeNull();
  expect(toProfile([[0, "x"], [1, 2]])).toBeNull();
});
