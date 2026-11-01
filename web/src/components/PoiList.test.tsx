import { render, screen } from "@testing-library/react";
import type { TrailPoi } from "../lib/data";
import PoiList from "./PoiList";

const poi = (id: number, kind: TrailPoi["kind"], name: string | null, along_km: number | null): TrailPoi => ({ id, name, kind, dist_m: 20, along_km, lon: 8, lat: 48 });

it("lists points in the given order with icon and km", () => {
  render(<PoiList pois={[poi(1, "food", "Café am Weg", 3.2), poi(2, "viewpoint", null, null)]} />);
  const items = screen.getAllByRole("listitem");
  expect(items[0]).toHaveTextContent("☕");
  expect(items[0]).toHaveTextContent("Café am Weg");
  expect(items[0]).toHaveTextContent("km 3,2");
  expect(items[1]).toHaveTextContent("Aussicht");
  expect(items[1]).not.toHaveTextContent("km");
});

it("renders nothing without points", () => {
  const { container } = render(<PoiList pois={[]} />);
  expect(container).toBeEmptyDOMElement();
});
