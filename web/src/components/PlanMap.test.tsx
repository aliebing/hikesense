import { render } from "@testing-library/react";
import type { LodgingOnTrail, TrailPoi } from "../lib/data";
import type { MapTrail } from "../lib/map";

const cap = vi.hoisted(() => ({ props: [] as Record<string, unknown>[] }));
vi.mock("./MapPanel", () => ({
  default: (p: Record<string, unknown>) => {
    cap.props.push(p);
    return <p>map</p>;
  },
}));

import PlanMap from "./PlanMap";

const mk = () => ({
  trail: { name: "W", geom: { type: "LineString" as const, coordinates: [[8, 48], [8.1, 48.1]] }, stages: [] } as MapTrail,
  lodgings: [{ id: 1, name: "L", kind: null, website: null, dist_m: 100, along_km: 1, lon: 8, lat: 48 }] as LodgingOnTrail[],
  pois: [{ id: 1, name: null, kind: "food", dist_m: 10, along_km: 1, lon: 8, lat: 48 }] as TrailPoi[],
});

it("equal-content props in new objects (router.refresh) reach the map as the same objects", () => {
  cap.props = [];
  const a = mk();
  const { rerender } = render(<PlanMap {...a} plan={null} lengthKm={10} />);
  const b = mk();
  rerender(<PlanMap {...b} plan={null} lengthKm={10} />);
  const [first, second] = cap.props;
  expect(second.trail).toBe(first.trail);
  expect(second.lodgings).toBe(first.lodgings);
  expect(second.pois).toBe(first.pois);
});

it("changed content produces new objects", () => {
  cap.props = [];
  const a = mk();
  const { rerender } = render(<PlanMap {...a} plan={null} lengthKm={10} />);
  const b = mk();
  b.lodgings = [...b.lodgings, { ...b.lodgings[0], id: 2 }];
  rerender(<PlanMap {...b} plan={null} lengthKm={10} />);
  expect(cap.props[1].lodgings).not.toBe(cap.props[0].lodgings);
});
