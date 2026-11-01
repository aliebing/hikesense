const h = vi.hoisted(() => ({ redirect: vi.fn() }));
vi.mock("next/navigation", () => ({ redirect: h.redirect }));

import Vorschlaege from "./page";

it("old suggestions page always goes to the home page, where the tiles are now", () => {
  Vorschlaege();
  expect(h.redirect).toHaveBeenCalledWith("/");
});
