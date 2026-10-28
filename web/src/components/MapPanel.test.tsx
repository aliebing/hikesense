import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MapPanel from "./MapPanel";

// No network, no WebGL in tests: maplibre is replaced by a stub.
vi.mock("maplibre-gl", () => {
  class Map {
    on() { return this; }
    getZoom() { return 12; }
    once() { return this; }
    addControl() { return this; }
    remove() {}
  }
  class Marker { setLngLat() { return this; } setPopup() { return this; } addTo() { return this; } remove() {} }
  class Popup { setDOMContent() { return this; } setLngLat() { return this; } addTo() { return this; } }
  class NavigationControl {}
  return { Map, Marker, Popup, NavigationControl, setWorkerUrl() {} };
});

const trail = {
  name: "W",
  geom: { type: "LineString" as const, coordinates: [[8, 48], [8.1, 48.1]] },
  stages: [],
};

test("map button opens an overlay with attribution; close button and Escape close it", async () => {
  const user = userEvent.setup();
  render(<MapPanel trail={trail} lodgings={[]} />);
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Karte/ }));
  const dialog = screen.getByRole("dialog", { name: /Karte/ });
  expect(dialog).toHaveTextContent("© BKG (basemap.de) CC BY 4.0");
  expect(dialog).toHaveTextContent("© OpenStreetMap-Mitwirkende, ODbL");

  await user.click(screen.getByRole("button", { name: "Karte schließen" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Karte/ }));
  await user.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
