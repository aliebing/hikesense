import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MapPanel from "./MapPanel";

// No network, no WebGL in tests: maplibre is replaced by a stub. `stub` lets a
// test make the constructor throw and fire the map's events by hand.
const stub = vi.hoisted(() => ({
  throwOnCreate: null as Error | null,
  handlers: {} as Record<string, ((e?: unknown) => void)[]>,
  setStyle: vi.fn(),
  fire(name: string, e?: unknown) {
    for (const h of this.handlers[name] ?? []) h(e);
  },
}));

vi.mock("maplibre-gl", () => {
  class GPUInitializationError extends Error {
    constructor() {
      super("Failed to initialize WebGL2");
      this.name = "GPUInitializationError";
    }
  }
  class Map {
    constructor() {
      if (stub.throwOnCreate) throw stub.throwOnCreate;
    }
    on(name: string, ...args: unknown[]) {
      // Layer-scoped handlers (map.on(type, layer, fn)) are irrelevant here.
      if (args.length === 1) (stub.handlers[name] ??= []).push(args[0] as (e?: unknown) => void);
      return this;
    }
    getZoom() { return 12; }
    once() { return this; }
    addControl() { return this; }
    setStyle(s: unknown) { stub.setStyle(s); }
    getSource() { return undefined; }
    addSource() {}
    addLayer() {}
    remove() {}
  }
  class Marker { setLngLat() { return this; } setPopup() { return this; } addTo() { return this; } remove() {} }
  class Popup { setDOMContent() { return this; } setLngLat() { return this; } addTo() { return this; } }
  class NavigationControl {}
  return { Map, Marker, Popup, NavigationControl, GPUInitializationError, setWorkerUrl() {} };
});

const trail = {
  name: "W",
  geom: { type: "LineString" as const, coordinates: [[8, 48], [8.1, 48.1]] },
  stages: [],
};

const lodging = {
  id: 1,
  name: "Hotel Adler",
  kind: "hotel",
  website: null,
  lat: 48.05,
  lon: 8.05,
  dist_m: 300,
  along_km: 1.2,
};

beforeEach(() => {
  stub.throwOnCreate = null;
  stub.handlers = {};
  stub.setStyle.mockReset();
});

async function openMap(lodgings: Parameters<typeof MapPanel>[0]["lodgings"] = []) {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} lodgings={lodgings} />);
  await user.click(screen.getByRole("button", { name: /Karte/ }));
  return screen.getByRole("dialog", { name: /Karte/ });
}

function expectAttribution(dialog: HTMLElement) {
  expect(dialog).toHaveTextContent("© BKG (basemap.de) CC BY 4.0");
  expect(dialog).toHaveTextContent("© OpenStreetMap-Mitwirkende, ODbL");
}

test("map button opens an overlay with attribution; close button and Escape close it", async () => {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} lodgings={[]} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Karte/ }));
  const dialog = screen.getByRole("dialog", { name: /Karte/ });
  expectAttribution(dialog);

  await user.click(screen.getByRole("button", { name: "Karte schließen" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Karte/ }));
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});

test("loading text is shown until the style loads, then the map is ready", async () => {
  const dialog = await openMap();
  expect(await screen.findByRole("status")).toHaveTextContent("Karte wird geladen …");
  await vi.waitFor(() => expect(stub.handlers["style.load"]).toBeDefined());

  act(() => stub.fire("style.load"));
  expect(screen.queryByRole("status")).not.toBeInTheDocument();
  expect(dialog.querySelector("[data-map-status]")).toHaveAttribute("data-map-status", "ready");
  expectAttribution(dialog);
});

test("without WebGL2 the map explains it in German and keeps the attribution", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  const { GPUInitializationError } = (await import("maplibre-gl")) as unknown as {
    GPUInitializationError: new () => Error;
  };
  stub.throwOnCreate = new GPUInitializationError();
  const dialog = await openMap();

  expect(await screen.findByText(/Die Karte braucht WebGL2/)).toBeVisible();
  expect(screen.getByRole("alert")).toHaveTextContent(/Hardwarebeschleunigung/);
  expect(screen.queryByText("Karte wird geladen …")).not.toBeInTheDocument();
  expectAttribution(dialog);
});

test("any other failure while creating the map shows a generic error", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  stub.throwOnCreate = new Error("boom");
  const dialog = await openMap();

  expect(await screen.findByRole("alert")).toHaveTextContent("Die Karte konnte nicht geladen werden.");
  expectAttribution(dialog);
});

test("basemap.de failing falls back to OSM once; if that fails too, it is an error, not endless loading", async () => {
  vi.spyOn(console, "warn").mockImplementation(() => {});
  vi.spyOn(console, "error").mockImplementation(() => {});
  const dialog = await openMap();
  await vi.waitFor(() => expect(stub.handlers.error).toBeDefined());

  act(() => stub.fire("error", { error: new Error("style 404") }));
  expect(stub.setStyle).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("status")).toHaveTextContent("Karte wird geladen …");

  act(() => stub.fire("error", { error: new Error("tiles unreachable") }));
  expect(stub.setStyle).toHaveBeenCalledTimes(1);
  expect(screen.getByRole("alert")).toHaveTextContent("Die Karte konnte nicht geladen werden.");
  expectAttribution(dialog);
});

test("legend counts lodgings near the trail", async () => {
  const dialog = await openMap([lodging]);
  expect(dialog).toHaveTextContent("1 Unterkünfte ≤ 1.000 m vom Weg");
});

test("legend says lodgings could not be loaded instead of showing 0", async () => {
  const dialog = await openMap(null);
  expect(dialog).toHaveTextContent("Unterkünfte konnten nicht geladen werden");
  expect(dialog).not.toHaveTextContent("0 Unterkünfte");
});
