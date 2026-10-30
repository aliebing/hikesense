import { render, screen, waitFor, within } from "@testing-library/react";

const h = vi.hoisted(() => ({
  session: null as null | object,
  query: "plan=p1&day=2",
  row: { data: null, error: null } as { data: unknown; error: unknown },
  trail: null as unknown,
}));
vi.mock("../../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  getBrowserSupabase: () => ({ from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => h.row }) }) }) }),
}));
vi.mock("next/navigation", () => ({ useSearchParams: () => new URLSearchParams(h.query) }));
vi.mock("../../lib/data", () => ({ getTrail: async () => h.trail }));
// the view itself is tested in Unterwegs.test.tsx: here only what the page hands over
vi.mock("../../components/Unterwegs", () => ({
  default: (p: { title: string; line: number[][]; startKm?: number; lengthKm: number | null; profile: unknown; days?: unknown[] }) => (
    <pre data-testid="view">{JSON.stringify({ title: p.title, line: p.line, startKm: p.startKm, lengthKm: p.lengthKm, profile: p.profile, days: p.days?.length })}</pre>
  ),
}));

import UnterwegsPage from "./page";

const profile = [[0, 100], [30, 400]];
// straight west-east line, 30 km: planar cut at km 10 / 20 falls on lon 8.1 / 8.2
const trail = {
  id: "t1", name: "Testweg", kind: "day_hike", length_km: 30, ascent_m: 300, descent_m: 0, stage_count: 0, center_lat: 48, cover: null,
  stages: [], photos: [], sources: [], profile,
  geom: { type: "LineString", coordinates: [[8.0, 48.0], [8.3, 48.0]] },
};
const day = (n: number) => ({ day: n, start_km: (n - 1) * 10, end_km: n * 10, walk_km: 10, access_km: 0, length_km: 10, ascent_m: 100, descent_m: 0, stop: null });
const payload = { plan: { trail_id: "t1", trail_name: "Testweg", target_km: 10, days: [day(1), day(2), day(3)], notes: [], source_ids: [] }, weather: {}, rain: {} };
const view = () => JSON.parse(screen.getByTestId("view").textContent!);

beforeEach(() => {
  h.session = { user: {} };
  h.query = "plan=p1&day=2";
  h.row = { data: { title: "Mein Plan", kind: "multiday", payload }, error: null };
  h.trail = trail;
});

it("plan without session: hint with link to /anmelden", () => {
  h.session = null;
  render(<UnterwegsPage />);
  expect(within(screen.getByText(/Für einen gemerkten Plan/)).getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/anmelden");
});

it("no trail and no plan: says nothing is selected", () => {
  h.query = "";
  render(<UnterwegsPage />);
  expect(screen.getByText(/Keine Tour ausgewählt/)).toBeInTheDocument();
});

it("plan day: the day's slice of the line, its start km and length, the trail profile", async () => {
  render(<UnterwegsPage />);
  const v = JSON.parse((await screen.findByTestId("view")).textContent!);
  expect(v.title).toBe("Mein Plan – Tag 2");
  expect(v.startKm).toBe(10);
  expect(v.lengthKm).toBe(10);
  expect(v.profile).toEqual(profile);
  expect(v.days).toBe(1);
  expect(v.line[0][0]).toBeCloseTo(8.1, 6);
  expect(v.line[v.line.length - 1][0]).toBeCloseTo(8.2, 6);
});

it("without day: day 1", async () => {
  h.query = "plan=p1";
  render(<UnterwegsPage />);
  await screen.findByTestId("view");
  expect(view().title).toBe("Mein Plan – Tag 1");
  expect(view().startKm).toBe(0);
});

it("whole trail: full line, trail length and profile", async () => {
  h.query = "trail=t1";
  render(<UnterwegsPage />);
  await screen.findByTestId("view");
  expect(view()).toMatchObject({ title: "Testweg", startKm: 0, lengthKm: 30, profile });
  expect(view().line).toHaveLength(2);
});

it("plan not found or not mine (RLS returns no row)", async () => {
  h.row = { data: null, error: null };
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Plan nicht gefunden");
  expect(screen.queryByTestId("view")).not.toBeInTheDocument();
});

it("database error", async () => {
  h.row = { data: null, error: { message: "boom" } };
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Der Plan konnte nicht geladen werden");
});

it("a day hike plan (wrong kind) is refused", async () => {
  h.row = { data: { title: "x", kind: "day_hike", payload }, error: null };
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Der Plan konnte nicht geladen werden");
});

it("day out of range", async () => {
  h.query = "plan=p1&day=4";
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Der Plan hat keinen Tag 4");
});

it.each(["abc", "0", "-1", "1.5", ""])("invalid day %j: clear message, nothing loaded", async (d) => {
  h.query = `plan=p1&day=${d}`;
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Ungültiger Tag");
  await waitFor(() => expect(screen.queryByTestId("view")).not.toBeInTheDocument());
});

it("trail of the plan is gone", async () => {
  h.trail = null;
  render(<UnterwegsPage />);
  expect(await screen.findByRole("alert")).toHaveTextContent("Die Tour konnte nicht geladen werden");
});
