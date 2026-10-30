import { render, screen } from "@testing-library/react";
import { ChatProvider } from "../../../components/ChatProvider";
import userEvent from "@testing-library/user-event";
import type { TrailDetail } from "../../../lib/data";

const mockGetTrail = vi.fn();
const mockGetLodgings = vi.fn();
vi.mock("../../../lib/data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../lib/data")>();
  return { ...actual, getTrail: () => mockGetTrail(), getLodgings: () => mockGetLodgings() };
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
  mockGetTrail.mockReset();
  mockGetLodgings.mockReset();
});

test("trail footer credits the elevation data (Copernicus GLO-30)", async () => {
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockResolvedValue([]);
  render(<ChatProvider>{await page()}</ChatProvider>);
  const footer = screen.getByRole("contentinfo");
  expect(footer).toHaveTextContent("OpenStreetMap (ODbL)");
  expect(footer).toHaveTextContent("Höhen: Copernicus DEM GLO-30 © DLR e.V./Airbus, bereitgestellt von EU/ESA");
});

test("when lodgings fail to load, the map legend says so instead of „0 Unterkünfte“", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrail.mockResolvedValue(detail);
  mockGetLodgings.mockRejectedValue(new Error("db down"));
  render(<ChatProvider>{await page()}</ChatProvider>);
  await userEvent.setup().click(screen.getByRole("button", { name: /Karte/ }));
  const dialog = screen.getByRole("dialog", { name: /Karte/ });
  expect(dialog).toHaveTextContent("Unterkünfte konnten nicht geladen werden");
  expect(dialog).not.toHaveTextContent("0 Unterkünfte");
});

describe("back link", () => {
  beforeEach(() => {
    mockGetTrail.mockResolvedValue(detail);
    mockGetLodgings.mockResolvedValue([]);
  });

  test("goes back to the suggestions when coming from there", async () => {
    render(<ChatProvider>{await page({ von: "vorschlaege" })}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Zu den Vorschlägen" })).toHaveAttribute("href", "/vorschlaege");
  });

  test("goes back home otherwise", async () => {
    render(<ChatProvider>{await page()}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Zur Startseite" })).toHaveAttribute("href", "/");
  });

  test("unknown von is ignored", async () => {
    render(<ChatProvider>{await page({ von: "https://evil" })}</ChatProvider>);
    expect(screen.getByRole("link", { name: "← Zur Startseite" })).toHaveAttribute("href", "/");
  });
});
