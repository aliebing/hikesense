import { din33466Hours, duration, hm, hmDown, km } from "./format";

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
