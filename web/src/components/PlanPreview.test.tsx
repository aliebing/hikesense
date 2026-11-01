import { render, screen } from "@testing-library/react";
import type { PlanData } from "../lib/chat";
import PlanPreview from "./PlanPreview";

const stop = (name: string) => ({ lodging_id: 1, name, kind: "hotel", website: null, along_km: 0, dist_m: 300 });
const day = (n: number, a: number, b: number, s: string | null) =>
  ({ day: n, date: null, start_km: a, end_km: b, walk_km: b - a, access_km: 0, length_km: b - a, ascent_m: 1, descent_m: 1, duration_h: 4, start_time: "09:00:00", arrival: "13:00:00", stop: s ? stop(s) : null, gap: null, within_band: true });
const data = (days: ReturnType<typeof day>[], notes: string[] = []) =>
  ({ plan: { trail_id: "westweg-west", trail_name: "Westweg", target_km: 15, days, notes, source_ids: [] }, weather: {}, rain: {}, start_name: "Hausach" }) as unknown as PlanData;

it("one tile per day with stretch, km and lodging, and the way to the map", () => {
  render(<PlanPreview data={data([day(1, 0, 15.2, "Hotel Adler"), day(2, 15.2, 30, "Gasthof Linde")])} />);
  expect(screen.getByRole("heading", { name: "Westweg ab Hausach, 2 Tage" })).toBeInTheDocument();
  const tiles = screen.getAllByRole("listitem");
  expect(tiles).toHaveLength(2);
  expect(tiles[0]).toHaveTextContent("Tag 1");
  expect(tiles[0]).toHaveTextContent("km 0–15,2");
  expect(tiles[0]).toHaveTextContent("15,2 km");
  expect(tiles[0]).toHaveTextContent("Hotel Adler");
  expect(screen.getByRole("link", { name: "Plan mit Karte ansehen →" })).toHaveAttribute("href", "/plan");
});

it("a plan without days says why", () => {
  render(<PlanPreview data={data([], ["Keine Unterkunft in Reichweite."])} />);
  expect(screen.getByText("Keine Unterkunft in Reichweite.")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Plan mit Karte/ })).toBeNull();
});
