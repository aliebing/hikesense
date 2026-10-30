import { render, screen } from "@testing-library/react";
import type { PlanData } from "../lib/chat";
import type { LodgingOnTrail } from "../lib/data";
import { initialState, saveState } from "../lib/chatState";
import type { MapTrail } from "../lib/map";
import { ChatProvider } from "./ChatProvider";

const cap = vi.hoisted(() => ({ props: null as null | { days?: { day: number; lodging_missing: boolean }[]; lodgings: unknown[] | null } }));
vi.mock("./MapPanel", () => ({
  default: (p: typeof cap.props) => {
    cap.props = p;
    return <p>map</p>;
  },
}));

import TrailMap from "./TrailMap";

const trail: MapTrail = { name: "W", geom: { type: "LineString", coordinates: [[8, 48], [8, 48.2], [8.2, 48.2]] }, stages: [] };
const lodging = (id: number): LodgingOnTrail => ({ id, name: `L${id}`, kind: null, website: null, dist_m: 1500, along_km: 10, lon: 8.05, lat: 48.21 });
const stop = (id: number) => ({ lodging_id: id, name: `L${id}`, kind: null, website: null, along_km: 0, dist_m: 1500 });
const day = (n: number, end: number, id: number) =>
  ({ day: n, date: null, start_km: end - 20, end_km: end, stop: stop(id) }) as never;
const plan = (trail_id: string): PlanData => ({
  plan: { trail_id, trail_name: "W", target_km: 20, days: [day(1, 20, 1), day(2, 40, 2)], notes: [], source_ids: [] },
  weather: {},
  rain: {},
});

const show = (trailId: string, von: boolean, p: PlanData | null, lodgings: LodgingOnTrail[] | null = [lodging(1)]) => {
  sessionStorage.clear();
  saveState(sessionStorage, { ...initialState("th"), plan: p });
  cap.props = null;
  render(
    <ChatProvider>
      <TrailMap trailId={trailId} fromSuggestions={von} trail={trail} lodgings={lodgings} lengthKm={40} />
    </ChatProvider>,
  );
  expect(screen.getByText("map")).toBeInTheDocument();
};

it("plan for this trail with von=vorschlaege: day sections, missing stop flagged", () => {
  show("w", true, plan("w"));
  expect(cap.props?.days?.map((d) => [d.day, d.lodging_missing])).toEqual([[1, false], [2, true]]);
  expect(cap.props?.lodgings).toHaveLength(1);
});

it("plan for another trail: no sections", () => {
  show("w", true, plan("other"));
  expect(cap.props?.days).toBeUndefined();
});

it("without von: no sections", () => {
  show("w", false, plan("w"));
  expect(cap.props?.days).toBeUndefined();
});
