import { render, screen } from "@testing-library/react";
import type { TrailSummary } from "../lib/data";
import { ChatProvider } from "../components/ChatProvider";

const mockGetTrails = vi.fn();
vi.mock("../lib/data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/data")>();
  return { ...actual, getTrails: () => mockGetTrails() };
});

import Home from "./page";

const trail = (id: string, kind: TrailSummary["kind"], lat: number): TrailSummary => ({
  id,
  name: `Weg ${id}`,
  kind,
  length_km: 10,
  ascent_m: 300,
  descent_m: 300,
  stage_count: kind === "long_distance" ? 25 : 0,
  center_lat: lat,
  cover: {
    url: `https://upload.example/${id}.jpg`,
    thumb_url: `https://upload.example/${id}-t.jpg`,
    author: `Autor ${id}`,
    license: "CC BY 4.0",
    license_url: null,
    page_url: null,
  },
});

beforeEach(() => {
  mockGetTrails.mockReset();
});

test("home shows a clear message when data cannot be loaded", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrails.mockRejectedValue(new Error("no supabase"));
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText(/Daten konnten nicht geladen werden/)).toBeInTheDocument();
});

test("home explains an empty database", async () => {
  mockGetTrails.mockResolvedValue([]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText(/Noch keine Wege/)).toBeInTheDocument();
});

test("home lists long-distance trails and day hikes with attribution", async () => {
  mockGetTrails.mockResolvedValue([
    trail("westweg-west", "long_distance", 48.5),
    trail("day-1", "day_hike", 48.1),
  ]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByRole("link", { name: /Weg westweg-west/ })).toHaveAttribute("href", "/t/westweg-west");
  expect(screen.getByRole("link", { name: /Weg day-1/ })).toHaveAttribute("href", "/t/day-1");
  expect(screen.getAllByText(/Autor day-1/).length).toBeGreaterThan(0);
});

test("home footer credits the elevation data (Copernicus GLO-30)", async () => {
  mockGetTrails.mockResolvedValue([trail("day-1", "day_hike", 48.1)]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByRole("contentinfo")).toHaveTextContent(
    "Höhen: Copernicus DEM GLO-30 © DLR e.V./Airbus, bereitgestellt von EU/ESA",
  );
});

test("home counts only day hikes that have a photo", async () => {
  const noPhoto = { ...trail("day-2", "day_hike", 48.2), cover: null };
  mockGetTrails.mockResolvedValue([trail("day-1", "day_hike", 48.1), noPhoto]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText(/1 von 1 Tagestouren mit Foto/)).toBeInTheDocument();
});
