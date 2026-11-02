import { din33466Hours, duration, hm, hmDown, km, walkingTime } from "./format";

test("format", () => {
  expect(km(14.83, "de")).toBe("14,8 km");
  expect(hm(720, "de")).toBe("↑ 720 m");
  expect(duration(5.17, "de")).toBe("5:10 h");
});

test("format edge cases", () => {
  expect(km(286.1, "de")).toBe("286,1 km");
  expect(km(9, "de")).toBe("9,0 km");
  expect(hm(8683, "de")).toBe("↑ 8.683 m");
  expect(hmDown(700, "de")).toBe("↓ 700 m");
  expect(duration(4.999, "de")).toBe("5:00 h"); // no "4:60 h"
  expect(duration(0.5, "de")).toBe("0:30 h");
});

// Same example values as backend/tests/test_hiking_time.py
test("din33466Hours matches the backend formula", () => {
  expect(din33466Hours(12, 600, 600)).toBeCloseTo(4.7);
  expect(din33466Hours(20, 300, 300)).toBeCloseTo(5.8);
  expect(() => din33466Hours(-1, 0, 0)).toThrow();
});

test("missing numbers show a dash, never zero", () => {
  expect(km(null, "de")).toBe("– km");
  expect(hm(null, "de")).toBe("↑ – m");
  expect(hmDown(null, "de")).toBe("↓ – m");
});

test("walkingTime is omitted when any input is missing", () => {
  expect(walkingTime({ length_km: 12, ascent_m: 600, descent_m: 600 }, "de")).toBe("4:42 h");
  expect(walkingTime({ length_km: null, ascent_m: 600, descent_m: 600 }, "de")).toBeNull();
  expect(walkingTime({ length_km: 12, ascent_m: null, descent_m: 600 }, "de")).toBeNull();
  expect(walkingTime({ length_km: 12, ascent_m: 600, descent_m: null }, "de")).toBeNull();
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

test("num never shows minus zero", async () => {
  const { num } = await import("./format");
  expect(num(-0.2, "de", { max: 0 })).toBe("0");
  expect(num(-0.04, "en", { max: 1 })).toBe("0");
  expect(num(-1.4, "en", { max: 0 })).toBe("-1");
});

test("dayLabel: English 'Thu 5 Nov', German with date, bad input unchanged", async () => {
  const { dayLabel } = await import("./format");
  expect(dayLabel("2026-11-05", "en")).toBe("Thu 5 Nov");
  expect(dayLabel("2026-11-05", "de")).toBe("Do., 05.11.2026");
  expect(dayLabel("soon", "en")).toBe("soon");
});
