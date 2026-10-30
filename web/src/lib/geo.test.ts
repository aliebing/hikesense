import { etaFromProfile, progressOnLine } from "./geo";

// ~111.2 km per degree of latitude: a straight north-south line of 0.1° ≈ 11.12 km
const line: [number, number][] = [
  [48.0, 8.0],
  [48.05, 8.0],
  [48.1, 8.0],
];

test("progress on straight line", () => {
  const p = progressOnLine(line, { lat: 48.05, lon: 8.0 });
  expect(p.alongKm).toBeCloseTo(5.56, 1);
  expect(p.remainingKm).toBeCloseTo(5.56, 1);
  expect(p.distToLineM).toBeLessThan(1);
});

test("position beside the line projects onto the nearest segment", () => {
  const p = progressOnLine(line, { lat: 48.075, lon: 8.001 });
  expect(p.alongKm).toBeCloseTo(8.34, 1);
  expect(p.distToLineM).toBeGreaterThan(60);
  expect(p.distToLineM).toBeLessThan(80);
});

test("off-route far away: distance is large, ends clamp", () => {
  const p = progressOnLine(line, { lat: 47.99, lon: 8.0 });
  expect(p.alongKm).toBe(0);
  expect(p.distToLineM).toBeGreaterThan(1000);
});

test("eta uses DIN 33466 like the backend (12 km, 600 up, 600 down = 4.7 h)", () => {
  const now = new Date("2026-11-02T09:00:00Z");
  expect(etaFromProfile(12, 600, 600, now).toISOString()).toBe("2026-11-02T13:42:00.000Z");
  // 20 km, 300/300: 5.8 h
  expect(etaFromProfile(20, 300, 300, now).toISOString()).toBe("2026-11-02T14:48:00.000Z");
});
