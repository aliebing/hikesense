import { lodgingLink, searchLink } from "./planView";

it("search link uses the given place and never a fixed region", () => {
  expect(decodeURIComponent(searchLink("Haus Rebe", "Bad Dürkheim"))).toContain("Haus Rebe Bad Dürkheim");
  const noPlace = decodeURIComponent(searchLink("Haus Rebe"));
  expect(noPlace).toContain("Haus Rebe");
  expect(noPlace).not.toContain("Schwarzwald");
});

it("lodging link for a Palatinate plan carries the start place, not Schwarzwald", () => {
  const link = lodgingLink({ name: "Weingut Eck", website: null }, "Schweigen");
  expect(link?.label).toBe("Suchen");
  expect(decodeURIComponent(link!.href)).toContain("Weingut Eck Schweigen");
  expect(link!.href).not.toContain("Schwarzwald");
});
