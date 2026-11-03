import { render, screen, within } from "@testing-library/react";
import { renderWithLocale } from "../../../test-utils";
import { ChatProvider } from "../../../components/ChatProvider";
import type { TrailDetail } from "../../../lib/data";

const mockGetTrail = vi.fn();
const mockGetLodgings = vi.fn();
const mockGetGroups = vi.fn();
const mockGetPois = vi.fn();
const mockGetTags = vi.fn();
const mockGetPool = vi.fn();
vi.mock("../../../lib/data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/data")>();
  return {
    ...actual,
    getTrail: () => mockGetTrail(),
    getLodgings: () => mockGetLodgings(),
    getGroups: () => mockGetGroups(),
    getTrailPois: () => mockGetPois(),
    getTrailTags: () => mockGetTags(),
    getLandscapePool: () => mockGetPool(),
  };
});

// The map itself is not under test here; no WebGL in jsdom.
vi.mock("maplibre-gl", () => ({
  setWorkerUrl() {},
  Map: class {
    constructor() {
      throw new Error("no map in tests");
    }
  },
}));

// server components read the language from a cookie; there is no request in unit tests
const cookie = vi.hoisted(() => ({ lang: "de" }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: cookie.lang }) }) }));

import TrailPage from "./page";

const detail: TrailDetail = {
  id: "day-1",
  name: "Tour 1",
  kind: "day_hike",
  length_km: 10,
  ascent_m: 300,
  descent_m: 300,
  stage_count: 0,
  center_lat: 48.1,
  cover: null,
  stages: [],
  photos: [],
  geom: { type: "LineString", coordinates: [[8, 48], [8.1, 48.1]] },
  sources: [{ id: "osm", name: "OpenStreetMap", url: null, license: "ODbL" }],
};

const page = (searchParams: { von?: string | string[] } = {}) =>
  TrailPage({ params: Promise.resolve({ trailId: "day-1" }), searchParams: Promise.resolve(searchParams) });

beforeEach(() => {
  cookie.lang = "de";
  mockGetTrail.mockReset();
  mockGetLodgings.mockReset();
  mockGetGroups.mockReset();
  mockGetGroups.mockResolvedValue([]);
  mockGetPois.mockReset();
  mockGetPois.mockResolvedValue([]);
  mockGetTags.mockReset();
  mockGetTags.mockResolvedValue([]);
  mockGetPool.mockReset();
  mockGetPool.mockResolvedValue([]);
});

test("trail footer credits the elevation data (Copernicus GLO-30)", async () => {
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockResolvedValue([]);
  render(<ChatProvider>{await page()}</ChatProvider>);
  const footer = screen.getByRole("contentinfo");
  expect(footer).toHaveTextContent("OpenStreetMap (ODbL)");
  expect(footer).toHaveTextContent("Höhen: Copernicus DEM");
  expect(footer).not.toHaveTextContent("DIN 33466"); // details are on the sources page
  expect(within(footer).getByRole("link", { name: "Quellen & Lizenzen" })).toHaveAttribute("href", "/quellen");
});

test("when lodgings fail to load, the map legend says so instead of „0 Unterkünfte“", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockRejectedValue(new Error("db down"));
  render(<ChatProvider>{await page()}</ChatProvider>);
  const legend = screen.getByTestId("map-legend");
  expect(legend).toHaveTextContent("Unterkünfte konnten nicht geladen werden");
  expect(legend).not.toHaveTextContent("0 Unterkünfte");
  const block = screen.getByRole("region", { name: "Übernachten in der Nähe" });
  expect(block).toHaveTextContent("Unterkünfte konnten nicht geladen werden");
  expect(screen.getByRole("heading", { name: "Tour 1" })).toBeInTheDocument();
});

describe("back link", () => {
  beforeEach(() => {
    mockGetTrail.mockResolvedValue(detail);
    mockGetLodgings.mockResolvedValue([]);
  });

  test("goes back to the suggestions on the home page when coming from the chat", async () => {
    render(<ChatProvider>{await page({ von: "chat" })}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Zurück zu den Vorschlägen" })).toHaveAttribute("href", "/");
  });

  test("old links with von=vorschlaege behave the same", async () => {
    render(<ChatProvider>{await page({ von: "vorschlaege" })}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Zurück zu den Vorschlägen" })).toHaveAttribute("href", "/");
  });

  test("goes back home otherwise", async () => {
    render(<ChatProvider>{await page()}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Startseite" })).toHaveAttribute("href", "/");
  });

  test("unknown von is ignored", async () => {
    render(<ChatProvider>{await page({ von: "https://evil" })}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Startseite" })).toHaveAttribute("href", "/");
  });
});

test("shows „Gruppen in der Nähe“ with Stand, nearest first, and leaves the section out when none are near", async () => {
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockResolvedValue([]);
  mockGetGroups.mockResolvedValue([
    { name: "Fern", kind: "wanderverein", place: "Weit", url: "https://example.org/fern", checked_at: "2026-10-01", lat: 49.5, lon: 8 },
    { name: "Nah", kind: "lauftreff", place: "Hier", url: "https://example.org/nah", checked_at: "2026-03-01", lat: 48.01, lon: 8.0 },
  ]);
  const { unmount } = render(<ChatProvider>{await page()}</ChatProvider>);
  const section = screen.getByRole("region", { name: "Gruppen in der Nähe" });
  expect(section).toHaveTextContent("Nah");
  expect(section).not.toHaveTextContent("Fern");
  expect(section).toHaveTextContent("Stand: 01.03.2026");
  unmount();
  mockGetGroups.mockResolvedValue([]);
  render(<ChatProvider>{await page()}</ChatProvider>);
  expect(screen.queryByRole("region", { name: "Gruppen in der Nähe" })).toBeNull();
});

const poi = (id: number, kind: "food" | "hut" | "viewpoint", name: string, along_km: number) => ({ id, name, kind, dist_m: 30, along_km, lon: 8.05, lat: 48.05 });

test("day hike: map without a click, description from data, lodgings and stops", async () => {
  mockGetTrail.mockResolvedValue({ ...detail, profile: [[0, 700], [5, 900], [10, 700]], surface_shares: { paved: 0.2, unpaved: 0.8 } });
  mockGetLodgings.mockResolvedValue([{ id: 1, name: "Hotel Adler", kind: "hotel", website: null, dist_m: 200, along_km: 2, lon: 8.02, lat: 48.02 }]);
  mockGetPois.mockResolvedValue([poi(1, "food", "Café", 3.2), poi(2, "hut", "Hütte", 7.8), poi(3, "viewpoint", "Blick", 5.1)]);
  mockGetTags.mockResolvedValue(["feature:rundweg", "surface:naturweg"]);
  const { container } = render(<ChatProvider>{await page()}</ChatProvider>);
  expect(screen.getByRole("button", { name: "Vollbild" })).toBeInTheDocument();
  const desc = screen.getByRole("region", { name: "Beschreibung" });
  expect(desc).toHaveTextContent("Rundweg, 10,0 km mit 300 m Aufstieg, Gehzeit etwa 3:18 h nach DIN 33466. Unterwegs 2 Einkehrmöglichkeiten und 1 Aussichtspunkt.");
  expect(desc).toHaveTextContent("Naturweg");
  expect(desc).toHaveTextContent("Belag: 80 % naturbelassen · 20 % Asphalt");
  expect(screen.getByRole("img", { name: /Höhenprofil/ })).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "Übernachten in der Nähe" })).toHaveTextContent("Hotel Adler");
  expect(screen.getByRole("region", { name: "Einkehr & Aussicht" })).toHaveTextContent("Café");
  expect(container.querySelector(".fixed")).toBeNull();
});

test("empty blocks fall away and nothing says 0", async () => {
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockResolvedValue([]);
  render(<ChatProvider>{await page()}</ChatProvider>);
  expect(screen.queryByRole("region", { name: "Übernachten in der Nähe" })).toBeNull();
  expect(screen.queryByRole("region", { name: "Einkehr & Aussicht" })).toBeNull();
  expect(screen.queryByRole("region", { name: "Gruppen in der Nähe" })).toBeNull();
  expect(screen.queryByRole("region", { name: "Fotos" })).toBeNull();
  expect(screen.getByRole("region", { name: "Beschreibung" })).not.toHaveTextContent("Unterwegs");
  expect(screen.queryByText(/\b0 (Unterkünfte|Einkehr)/)).toBeNull();
});

test("a landscape photo of the tour lies behind the middle, credited in the footer", async () => {
  const cover = { url: "https://img/c.jpg", thumb_url: "https://img/c-t.jpg", author: "Clara", license: "CC BY 4.0", license_url: null, page_url: "https://commons.wikimedia.org/wiki/File:Blick_ins_Tal.jpg" };
  mockGetTrail.mockResolvedValue({ ...detail, cover, photos: [cover] });
  mockGetLodgings.mockResolvedValue([]);
  const { container } = render(<ChatProvider>{await page()}</ChatProvider>);
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/c.jpg']")).not.toBeNull();
  expect(screen.getByRole("contentinfo")).toHaveTextContent("Hintergrundbild: Clara");
});

test("a tour without a landscape photo gets one from the pool, never e.g. a bank card", async () => {
  const card = { url: "https://img/n26.jpg", thumb_url: "https://img/n26-t.jpg", author: "X", license: "CC BY 4.0", license_url: null, page_url: "https://commons.wikimedia.org/wiki/File:N26_Maestro.jpg" };
  const view = { url: "https://img/see.jpg", thumb_url: "https://img/see-t.jpg", author: "Sina", license: "CC BY 4.0", license_url: null, page_url: "https://commons.wikimedia.org/wiki/File:Teufensee.jpg" };
  mockGetTrail.mockResolvedValue({ ...detail, cover: card, photos: [card] });
  mockGetLodgings.mockResolvedValue([]);
  mockGetPool.mockResolvedValue([view]);
  const { container } = render(<ChatProvider>{await page()}</ChatProvider>);
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/n26.jpg']")).toBeNull();
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/see.jpg']")).not.toBeNull();
  expect(screen.getByRole("contentinfo")).toHaveTextContent("Hintergrundbild: Sina");
});

test("no chat on the tour page, a clear back button instead", async () => {
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockResolvedValue([]);
  render(<ChatProvider>{await page({ von: "chat" })}</ChatProvider>);
  expect(screen.queryByRole("complementary", { name: "Planungs-Chat" })).toBeNull();
  expect(screen.getByRole("heading", { name: "Tour 1" })).toHaveClass("schrift-feld", "w-full");
  const back = screen.getByRole("link", { name: "← Zurück zu den Vorschlägen" });
  expect(back).toHaveAttribute("href", "/");
  expect(back.className).toContain("rounded-full");
});

test("English: the tour page, its blocks and tags are in English", async () => {
  cookie.lang = "en";
  mockGetTrail.mockResolvedValue({ ...detail, profile: [[0, 700], [5, 900], [10, 700]], surface_shares: { paved: 0.2, unpaved: 0.8 } });
  mockGetLodgings.mockResolvedValue([{ id: 1, name: null, kind: "guest_house", website: null, dist_m: 1200, along_km: 2, lon: 8.02, lat: 48.02 }]);
  mockGetPois.mockResolvedValue([poi(1, "food", "Café", 3.2), poi(2, "hut", "Hütte", 7.8), poi(3, "viewpoint", "Blick", 5.1)]);
  mockGetTags.mockResolvedValue(["feature:rundweg", "feature:einkehr", "surface:naturweg"]);
  mockGetGroups.mockResolvedValue([{ name: "Nah", kind: "lauftreff", place: "Hier", url: "https://example.org/nah", checked_at: "2026-03-01", lat: 48.01, lon: 8.0 }]);
  renderWithLocale(<ChatProvider>{await page({ von: "chat" })}</ChatProvider>, "en");
  expect(screen.getByRole("link", { name: "← Back to suggestions" })).toBeInTheDocument();
  expect(screen.getByText("Day hike")).toBeInTheDocument();
  expect(screen.getByText("Ascent")).toBeInTheDocument();
  expect(screen.getByText("↑ 300 m")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Full screen" })).toBeInTheDocument();
  const desc = screen.getByRole("region", { name: "Description" });
  expect(desc).toHaveTextContent("Round walk, 10.0 km with 300 m ascent, walking time about 3:18 h to DIN 33466. Along the way: 2 refreshment stops and 1 viewpoint.");
  expect(desc).toHaveTextContent("Inn / café stop");
  expect(desc).toHaveTextContent("Surface: 80% natural · 20% tarmac");
  expect(screen.getByRole("img", { name: /Elevation profile/ })).toBeInTheDocument();
  const lodging = screen.getByRole("region", { name: "Places to stay nearby" });
  expect(lodging).toHaveTextContent("Guesthouse");
  expect(lodging).toHaveTextContent("1,200 m from the trail");
  expect(screen.getByRole("region", { name: "Groups nearby" })).toHaveTextContent("As of 01/03/2026 · within 15 km of the trail");
  expect(screen.getByRole("region", { name: "Inns & viewpoints" })).toHaveTextContent("Café");
  expect(screen.getByRole("contentinfo")).toHaveTextContent("Sources: OpenStreetMap (ODbL) · Elevation: Copernicus DEM · Sources & licences");
});

test("English: the data-load error is English", async () => {
  cookie.lang = "en";
  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrail.mockRejectedValue(new Error("db"));
  renderWithLocale(<ChatProvider>{await page()}</ChatProvider>, "en");
  expect(screen.getByText("Data could not be loaded.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Home" })).toBeInTheDocument();
});
