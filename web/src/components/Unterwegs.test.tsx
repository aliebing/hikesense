import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { MapTrail } from "../lib/map";

const mapProps = vi.hoisted(() => ({ last: null as Record<string, unknown> | null }));
vi.mock("./MapPanel", () => ({
  default: (p: Record<string, unknown>) => {
    mapProps.last = p;
    return <div data-testid="map" />;
  },
}));

import { renderWithLocale } from "../test-utils";
import Unterwegs from "./Unterwegs";

// north-south line of 0.1° ≈ 11.1 km at lon 8.0 ([lon, lat] like GeoJSON)
const coords = [[8.0, 48.0], [8.0, 48.05], [8.0, 48.1]];
const trail: MapTrail = { name: "Testweg", geom: { type: "LineString", coordinates: coords }, stages: [] };

type Ok = (p: { coords: { latitude: number; longitude: number } }) => void;
type Fail = (e: { code: number }) => void;
const geo = vi.hoisted(() => ({ ok: null as unknown, fail: null as unknown, watch: vi.fn(), clear: vi.fn() }));

beforeEach(() => {
  geo.watch.mockReset().mockImplementation((ok: Ok, fail: Fail) => {
    geo.ok = ok;
    geo.fail = fail;
    return 7;
  });
  geo.clear.mockReset();
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: { watchPosition: geo.watch, clearWatch: geo.clear } });
});

// climb first, descent last: at half distance almost no climb remains
const profile: [number, number][] = [[0, 0], [1, 600], [10, 600], [11.12, 0]];
const view = () => <Unterwegs title="Testweg" trail={trail} line={coords} profile={profile} lengthKm={null} />;
const fix = (lat: number, lon: number) => act(() => (geo.ok as Ok)({ coords: { latitude: lat, longitude: lon } }));

test("shows remaining km and arrival on the line", async () => {
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.0);
  expect(screen.getByText(/Noch 5,6 km/)).toBeInTheDocument();
  expect(screen.getByText(/Ankunft ca\. \d\d:\d\d Uhr/)).toHaveTextContent("ohne Pausen");
});

test("off-route over 200 m: distance message, no remaining km", async () => {
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.02); // ~1.5 km east
  expect(screen.getByText(/Du bist 1,5 km vom Weg entfernt – Restkilometer erst wieder am Weg/)).toBeInTheDocument();
  expect(screen.queryByText(/Noch .* km/)).not.toBeInTheDocument();
});

test("denied permission message", async () => {
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  act(() => (geo.fail as Fail)({ code: 1 }));
  expect(screen.getByRole("alert")).toHaveTextContent("Standortfreigabe verweigert – in den Browser-Einstellungen erlauben");
});

test("unavailable and timeout have their own messages", async () => {
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  act(() => (geo.fail as Fail)({ code: 2 }));
  expect(screen.getByRole("alert")).toHaveTextContent("Standort nicht verfügbar");
  act(() => (geo.fail as Fail)({ code: 3 }));
  expect(screen.getByRole("alert")).toHaveTextContent("Zeitüberschreitung");
});

test("never sends position", async () => {
  const f = vi.fn();
  vi.stubGlobal("fetch", f);
  const beacon = vi.fn();
  Object.defineProperty(navigator, "sendBeacon", { configurable: true, value: beacon });
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.0);
  fix(48.06, 8.0);
  expect(f).not.toHaveBeenCalled();
  expect(beacon).not.toHaveBeenCalled();
  vi.unstubAllGlobals();
});

test("clears watch on unmount and on stop", async () => {
  const { unmount } = render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  await userEvent.click(screen.getByRole("button", { name: "Beenden" }));
  expect(geo.clear).toHaveBeenCalledWith(7);
  geo.clear.mockReset();
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  unmount();
  expect(geo.clear).toHaveBeenCalledWith(7);
});

test("without geolocation support: own message", async () => {
  Object.defineProperty(navigator, "geolocation", { configurable: true, value: undefined });
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Standortbestimmung ist in diesem Browser nicht verfügbar");
});

test("unknown ascent: remaining km but no arrival guess", async () => {
  render(<Unterwegs title="Testweg" trail={trail} line={coords} profile={null} lengthKm={null} />);
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.0);
  expect(screen.getByText(/Noch 5,6 km/)).toBeInTheDocument();
  expect(screen.getByText(/Ankunft: unbekannt/)).toBeInTheDocument();
});

test("arrival comes from the remaining profile, not a pro-rata share", async () => {
  vi.useFakeTimers({ toFake: ["Date"] });
  vi.setSystemTime(new Date(2026, 10, 2, 9, 0, 0));
  try {
    render(view());
    await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
    fix(48.05, 8.0); // half way: ~5.56 km left, 0 m up, 600 m down -> 1.39 h + 0.6 h = 1:59 h
    expect(screen.getByText(/Ankunft ca\. 10:59 Uhr/)).toBeInTheDocument();
    expect(screen.queryByText(/anteilig/)).not.toBeInTheDocument();
  } finally {
    vi.useRealTimers();
  }
});

test("known section length gives the remaining km (plan card km), offset into the trail profile", async () => {
  render(<Unterwegs title="Tag 2" trail={trail} line={coords} profile={profile} startKm={20} lengthKm={10} />);
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.0); // half of the line = half of the 10 km
  expect(screen.getByText(/Noch 5,0 km/)).toBeInTheDocument();
  expect(screen.getByText(/bisher 5,0 km von 10,0 km/)).toBeInTheDocument();
  // km 25..30 lies beyond the profile: its last elevation holds, so no ascent/descent and an arrival of 1.25 h
  expect(screen.getByText(/Ankunft ca\./)).toBeInTheDocument();
});

test("Beenden clears the position and the progress", async () => {
  render(view());
  await userEvent.click(screen.getByRole("button", { name: "Unterwegs starten" }));
  fix(48.05, 8.0);
  expect(screen.getByText(/Noch/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Beenden" }));
  expect(screen.queryByText(/Noch/)).not.toBeInTheDocument();
});

test("the map gets no lodging layer (none loaded here), so it shows no loading error", () => {
  render(view());
  expect(mapProps.last).not.toBeNull();
  expect(mapProps.last).not.toHaveProperty("lodgings");
});

test("English: remaining km, arrival and errors are English", async () => {
  renderWithLocale(view(), "en");
  await userEvent.click(screen.getByRole("button", { name: "Start" }));
  fix(48.05, 8.0);
  expect(screen.getByText(/5\.6 km to go/)).toBeInTheDocument();
  expect(screen.getByText(/Arrival about \d\d:\d\d/)).toHaveTextContent("without breaks");
  act(() => (geo.fail as Fail)({ code: 1 }));
  expect(screen.getByRole("alert")).toHaveTextContent("Location permission denied – allow it in the browser settings");
});
