import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithLocale } from "../test-utils";
import MapPanel from "./MapPanel";

// No network, no WebGL in tests: maplibre is replaced by a stub. `stub` lets a
// test make the constructor throw and fire the map's events by hand.
const stub = vi.hoisted(() => ({
  throwOnCreate: null as Error | null,
  handlers: {} as Record<string, ((e?: unknown) => void)[]>,
  setStyle: vi.fn(),
  markers: [] as HTMLElement[],
  options: [] as Record<string, unknown>[],
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
    constructor(o: Record<string, unknown>) {
      stub.options.push(o);
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
  class Marker { constructor(o?: { element?: HTMLElement }) { if (o?.element) stub.markers.push(o.element); } setLngLat() { return this; } setPopup() { return this; } addTo() { return this; } remove() {} }
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
  stub.markers = [];
  stub.options = [];
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

test("without a lodging layer the legend names no lodgings and no loading error", async () => {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} />);
  await user.click(screen.getByRole("button", { name: /Karte/ }));
  const dialog = screen.getByRole("dialog", { name: /Karte/ });
  expect(dialog).not.toHaveTextContent("Unterkünfte");
  expectAttribution(dialog);
});

const poi = (id: number, kind: "food" | "viewpoint", name: string | null, along_km: number | null) => ({ id, name, kind, dist_m: 40, along_km, lon: 8.02, lat: 48.02 });

test("embedded map is visible without a click and offers full screen", async () => {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} lodgings={[]} embedded />);
  expect(document.querySelector("[data-map-status]")).not.toBeNull();
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Vollbild" }));
  expect(screen.getByRole("dialog", { name: /Karte/ })).toBeInTheDocument();
});

test("pois become markers and only present groups are in the legend", async () => {
  render(<MapPanel trail={trail} lodgings={[]} embedded pois={[poi(1, "food", "Café Adler", 3.2), poi(2, "viewpoint", null, null)]} />);
  await vi.waitFor(() => expect(stub.markers.filter((m) => m.classList.contains("map-poi"))).toHaveLength(2));
  const labels = stub.markers.filter((m) => m.classList.contains("map-poi")).map((m) => m.getAttribute("aria-label"));
  expect(labels).toEqual(["Café Adler, Einkehr, km 3,2", "Aussicht"]);
  const legend = screen.getByTestId("map-legend");
  expect(legend).toHaveTextContent("Einkehr");
  expect(legend).toHaveTextContent("Aussicht");
  expect(legend).not.toHaveTextContent("Wasserfall");
});

test("no lodgings near the trail: the legend names none instead of „0 Unterkünfte“", () => {
  render(<MapPanel trail={trail} lodgings={[]} embedded />);
  expect(screen.getByTestId("map-legend")).not.toHaveTextContent("Unterkünfte");
});

test("embedded map lets one finger scroll the page (cooperative gestures); full screen does not", async () => {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} lodgings={[]} embedded />);
  await vi.waitFor(() => expect(stub.options).toHaveLength(1));
  expect(stub.options[0].cooperativeGestures).toBe(true);
  expect((stub.options[0].locale as Record<string, string>)["CooperativeGesturesHandler.MobileHelpText"]).toBe("Mit zwei Fingern die Karte bewegen");
  await user.click(screen.getByRole("button", { name: "Vollbild" }));
  await vi.waitFor(() => expect(stub.options).toHaveLength(2));
  expect(stub.options[1].cooperativeGestures).toBeFalsy();
});

test("English: legend, buttons and POI labels are English", async () => {
  renderWithLocale(<MapPanel trail={trail} lodgings={[lodging]} embedded pois={[poi(1, "food", "Café Adler", 3.2)]} />, "en");
  const legend = screen.getByTestId("map-legend");
  expect(legend).toHaveTextContent("1 places to stay ≤ 1,000 m from the trail");
  expect(legend).toHaveTextContent("Refreshments");
  expect(legend).toHaveTextContent("OpenStreetMap contributors");
  await vi.waitFor(() => expect(stub.markers.filter((m) => m.classList.contains("map-poi"))).toHaveLength(1));
  expect(stub.markers.find((m) => m.classList.contains("map-poi"))!.getAttribute("aria-label")).toBe("Café Adler, Inn / café, km 3.2");
  expect(screen.getByRole("button", { name: "Full screen" })).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Full screen" }));
  expect(screen.getByRole("dialog", { name: /Map:/ })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Close map" })).toBeInTheDocument();
});
