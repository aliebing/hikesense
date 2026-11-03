import { expect, it } from "vitest";
import type { Photo } from "./data";
import { isLandscape, pickBackdrop } from "./backdrop";

const ph = (file: string): Photo => ({
  url: `https://upload.example/${file}`,
  thumb_url: `https://upload.example/t/${file}`,
  author: "A",
  license: "CC BY 4.0",
  license_url: null,
  page_url: `https://commons.wikimedia.org/wiki/File:${file}`,
});

it("takes landscapes by their Commons file name and leaves out the rest", () => {
  expect(isLandscape(ph("Blick_ins_Renchtal.JPG"))).toBe(true);
  expect(isLandscape(ph("Sch%C3%B6nwald_im_Schwarzwald_Blindensee_02.jpg"))).toBe(true);
  expect(isLandscape(ph("Feldberg_(Schwarzwald)_-_Falkauer_Wasserfall.jpg"))).toBe(true);
  expect(isLandscape(ph("Sunset_on_the_black_forest_high_road_(14815875445).jpg"))).toBe(true);
  expect(isLandscape(ph("N26_Maestro.jpg"))).toBe(false);
  expect(isLandscape(ph("Marxzell-Pfaffenrot-Dorfmuseum_Kantebuahaus-02-2025-gje.jpg"))).toBe(false);
  expect(isLandscape(ph("Sender_Waldachtal_23072014_2.JPG"))).toBe(false);
  expect(isLandscape(ph("Kirche,_Schluchsee_-_geo-en.hlipp.de_-_12591.jpg"))).toBe(false);
  expect(isLandscape(ph("Winter_im_Schwarzwald_-_panoramio.jpg"))).toBe(false); // „Schwarzwald“ alone is no landscape hint
  expect(isLandscape({ ...ph("Blick.jpg"), page_url: null })).toBe(false);
  expect(isLandscape(ph("ISS060-E-53009_-_View_of_Earth.jpg"))).toBe(false);
  expect(isLandscape(ph("Mapillary_(ZXStreetview)_2026-06-13_view.jpg"))).toBe(false);
});

it("prefers the tour's own landscape, else a steady pick from the pool", () => {
  const own = [ph("N26_Maestro.jpg"), ph("Blick_vom_Turm.jpg")];
  const pool = [ph("Blick_ins_Renchtal.JPG"), ph("Teufensee_-_panoramio.jpg"), ph("Enztal_Querung_Gegenlicht.jpg")];
  expect(pickBackdrop(own, pool, "day-1")?.url).toBe("https://upload.example/Blick_vom_Turm.jpg");
  const a = pickBackdrop([ph("N26_Maestro.jpg")], pool, "day-12724385");
  expect(pool.map((p) => p.url)).toContain(a?.url);
  expect(pickBackdrop([ph("N26_Maestro.jpg")], pool, "day-12724385")?.url).toBe(a?.url); // same tour, same picture
  expect(pickBackdrop([ph("N26_Maestro.jpg")], [], "x")).toBeNull();
});

it("isWinter: winter and snow photos by file name, not the Eisenweg", async () => {
  const { isWinter } = await import("./backdrop");
  const p = (file: string) => ({ url: "u", thumb_url: "t", author: "a", license: "l", license_url: null, page_url: `https://commons.wikimedia.org/wiki/File:${file}` });
  expect(isWinter(p("Winter_Vally_Baden_Wurttemberg.jpg"))).toBe(true);
  expect(isWinter(p("Feldberg_im_Schnee.jpg"))).toBe(true);
  expect(isWinter(p("Eisenweg_Blick.jpg"))).toBe(false);
  expect(isWinter(p("Mathisleweiher_Panorama.jpg"))).toBe(false);
  expect(isWinter(null)).toBe(false);
});
