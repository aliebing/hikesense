import { lodgingLink, searchLink } from "./planView";

it("search link uses the given place and never a fixed region", () => {
  expect(decodeURIComponent(searchLink("Haus Rebe", "Bad Dürkheim"))).toContain("Haus Rebe Bad Dürkheim");
  const noPlace = decodeURIComponent(searchLink("Haus Rebe"));
  expect(noPlace).toContain("Haus Rebe");
  expect(noPlace).not.toContain("Schwarzwald");
});

it("lodging link for a Palatinate plan carries the start place, not Schwarzwald", () => {
  const link = lodgingLink({ name: "Weingut Eck", website: null }, "Schweigen", "de");
  expect(link?.label).toBe("Suchen");
  expect(decodeURIComponent(link!.href)).toContain("Weingut Eck Schweigen");
  expect(link!.href).not.toContain("Schwarzwald");
});

it("dayPhotos: each day gets a photo of the stage it walks, landscapes first, never twice", async () => {
  const { dayPhotos } = await import("./planView");
  const ph = (file: string) => ({ url: file, thumb_url: file, author: "a", license: "l", license_url: null, page_url: `https://commons.wikimedia.org/wiki/File:${file}` });
  const stages = [
    { length_km: 20, photos: [ph("Bahnhof_Pforzheim.jpg"), ph("Blick_ins_Enztal.jpg")] },
    { length_km: 20, photos: [ph("Dobel_Aussicht.jpg")] },
    { length_km: 20, photos: [] },
  ];
  const days = [
    { start_km: 0, end_km: 15 },
    { start_km: 15, end_km: 30 },
    { start_km: 30, end_km: 45 },
    { start_km: 45, end_km: 60 },
  ];
  const got = dayPhotos(days, stages).map((p) => p?.url ?? null);
  expect(got[0]).toBe("Blick_ins_Enztal.jpg"); // landscape before the station photo
  expect(got[1]).toBe("Dobel_Aussicht.jpg"); // its midpoint (22.5 km) is on stage 2
  expect(got[2]).toBe("Bahnhof_Pforzheim.jpg"); // stage 2 is used up: the nearest stage with a free photo
  expect(got[3]).toBeNull(); // nothing left -- rather no photo than a repeat
});
