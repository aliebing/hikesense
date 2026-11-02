import { hasDescription } from "./tourDescription";

const empty = { sentence: null, tags: [], surface: null, profile: null };

describe("hasDescription", () => {
  it("is false without any data", () => expect(hasDescription(empty)).toBe(false));
  it.each([
    { sentence: "A short walk." },
    { tags: ["view"] },
    { surface: "80 % path" },
    { profile: [[0, 100]] as [number, number][] },
  ])("is true with %o", (extra) => expect(hasDescription({ ...empty, ...extra })).toBe(true));
});

// A function exported from a "use client" module cannot be called from a server page (the
// day hike page crashed that way): helpers used by pages live in lib/.
it("keeps TourDescription.tsx free of non-component exports", async () => {
  const { readFileSync } = await import("node:fs");
  const src = readFileSync("src/components/TourDescription.tsx", "utf8");
  expect(src.match(/^export (?!default)/gm)).toBeNull();
});
