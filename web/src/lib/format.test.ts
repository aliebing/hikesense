import { din33466Hours, duration, hm, hmDown, km, walkingTime } from "./format";

test("format", () => {
  expect(km(14.83)).toBe("14,8 km");
  expect(hm(720)).toBe("↑ 720 m");
  expect(duration(5.17)).toBe("5:10 h");
});

test("format edge cases", () => {
  expect(km(286.1)).toBe("286,1 km");
  expect(km(9)).toBe("9,0 km");
  expect(hm(8683)).toBe("↑ 8.683 m");
  expect(hmDown(700)).toBe("↓ 700 m");
  expect(duration(4.999)).toBe("5:00 h"); // no "4:60 h"
  expect(duration(0.5)).toBe("0:30 h");
});

// Same example values as backend/tests/test_hiking_time.py
test("din33466Hours matches the backend formula", () => {
  expect(din33466Hours(12, 600, 600)).toBeCloseTo(4.7);
  expect(din33466Hours(20, 300, 300)).toBeCloseTo(5.8);
  expect(() => din33466Hours(-1, 0, 0)).toThrow();
});

test("missing numbers show a dash, never zero", () => {
  expect(km(null)).toBe("– km");
  expect(hm(null)).toBe("↑ – m");
  expect(hmDown(null)).toBe("↓ – m");
});

test("walkingTime is omitted when any input is missing", () => {
  expect(walkingTime({ length_km: 12, ascent_m: 600, descent_m: 600 })).toBe("4:42 h");
  expect(walkingTime({ length_km: null, ascent_m: 600, descent_m: 600 })).toBeNull();
  expect(walkingTime({ length_km: 12, ascent_m: null, descent_m: 600 })).toBeNull();
  expect(walkingTime({ length_km: 12, ascent_m: 600, descent_m: null })).toBeNull();
});

test("format in both languages", () => {
  expect(km(11.6, "en")).toBe("11.6 km");
  expect(km(11.6, "de")).toBe("11,6 km");
  expect(km(null, "en")).toBe("– km");
  expect(hm(1200, "en")).toBe("↑ 1,200 m");
  expect(hm(1200, "de")).toBe("↑ 1.200 m");
  expect(hmDown(1200, "en")).toBe("↓ 1,200 m");
  expect(duration(5.17, "en")).toBe("5:10 h");
});
