import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DayPlan, PlanData } from "../lib/chat";

const h = vi.hoisted(() => ({ session: null as null | object, savePlan: vi.fn() }));
vi.mock("../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }) }));
vi.mock("../lib/plans", () => ({ savePlan: h.savePlan }));

import PlanDays, { planTitle } from "./PlanDays";

const day = (n: number, over: Partial<DayPlan> = {}): DayPlan => ({
  day: n, date: "2026-11-02", start_km: (n - 1) * 15, end_km: n * 15, walk_km: 15, access_km: 0, length_km: 15,
  ascent_m: 400, descent_m: 0, duration_h: 4.42, start_time: "09:00:00", arrival: "13:25:00",
  stop: { lodging_id: n, name: `Gasthaus ${n}`, kind: "guest_house", website: null, along_km: n * 15, dist_m: 300 },
  gap: null, within_band: true, ...over,
});
const data = (days: DayPlan[], over: Partial<PlanData> = {}): PlanData => ({
  plan: { trail_id: "westweg-west", trail_name: "Westweg (Westvariante)", target_km: 15, days, notes: [], source_ids: [] },
  weather: {}, rain: {}, ...over,
});

beforeEach(() => {
  h.session = null;
  h.savePlan.mockReset();
});

it("renders days with arrival and 'ohne Pausen'", () => {
  render(<PlanDays data={data([day(1), day(2)])} startName="Hausach" />);
  const cards = screen.getAllByRole("listitem").filter((li) => li.querySelector("h3"));
  expect(cards).toHaveLength(2);
  expect(cards[0]).toHaveTextContent("Tag 1 · Mo., 02.11.2026");
  expect(cards[0]).toHaveTextContent("Hausach → Gasthaus 1");
  expect(cards[0]).toHaveTextContent("15 km");
  expect(cards[0]).toHaveTextContent("↑ 400 m");
  expect(cards[0]).toHaveTextContent("Ankunft 13:25 Uhr (ohne Pausen)");
  expect(cards[1]).toHaveTextContent("Gasthaus 1 → Gasthaus 2");
  expect(screen.getByText(/Alle Zeiten ohne Pausen/)).toBeInTheDocument();
  // lodging without website: search link, never a made-up site
  const link = within(cards[0]).getByRole("link", { name: "Suchen" });
  expect(link.getAttribute("href")).toContain("q=Gasthaus%201");
});

it("shows gap note and never an arrival time when arrival is null", () => {
  render(<PlanDays data={data([day(1, { arrival: null, gap: "Tagesstrecke zu lang für einen Tag (20 h ohne Pausen)" })])} />);
  expect(screen.getByRole("note")).toHaveTextContent("Tagesstrecke zu lang");
  expect(screen.queryByText(/Ankunft/)).toBeNull();
});

it("shows notes of an empty plan above no days", () => {
  render(<PlanDays data={data([], { plan: { ...data([]).plan, notes: ["Ab Kandern bleiben 28 km bis Basel."] } })} />);
  expect(screen.getByRole("note")).toHaveTextContent("Ab Kandern bleiben 28 km bis Basel.");
  expect(screen.queryByText(/Alle Zeiten ohne Pausen/)).toBeNull();
});

it("shows 'Noch keine Vorhersage' and weather values", () => {
  render(
    <PlanDays
      data={data([day(1), day(2)], {
        weather: {
          "1": { date: "2026-11-02", code: 2, text: "Teils bewölkt", t_min_c: 3, t_max_c: 11.4, precip_mm: 0.2, precip_prob_pct: 10, source_id: "open-meteo" },
          "2": { reason: "Noch keine Vorhersage (mehr als 14 Tage)" },
        },
      })}
    />,
  );
  expect(screen.getByText("Teils bewölkt")).toBeInTheDocument();
  expect(screen.getByText(/3 \/ 11 °C/)).toBeInTheDocument();
  expect(screen.getByText(/Regen 10 % \/ 0,2 mm/)).toBeInTheDocument();
  expect(screen.getByText(/Noch keine Vorhersage/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Open-Meteo.com" })).toBeInTheDocument();
});

it("rain variant is collapsible; null says no station", async () => {
  render(
    <PlanDays
      data={data([day(1), day(2)], {
        rain: { "1": { station_name: "Haltestelle Wolfach", walk_km: 9.3, ascent_m: 0, duration_h: 2.45, note: "Fahrplan bitte selbst prüfen." }, "2": null },
      })}
    />,
  );
  const summary = screen.getByText("Regenvariante");
  const details = summary.closest("details")!;
  expect(details.open).toBe(false);
  await userEvent.click(summary);
  expect(details.open).toBe(true);
  expect(details).toHaveTextContent("Haltestelle Wolfach: 9,3 km");
  expect(screen.getByText(/Regenvariante nicht möglich/)).toBeInTheDocument();
});

it("missing numbers say unbekannt", () => {
  render(<PlanDays data={data([day(1, { ascent_m: null as unknown as number, stop: { lodging_id: 1, name: "X", kind: null, website: null, along_km: 15, dist_m: null as unknown as number } })])} />);
  expect(screen.getAllByText(/unbekannt/).length).toBeGreaterThan(0);
});

it("Merken saves the plan unchanged, only when signed in", async () => {
  const d = data([day(1), day(2), day(3)]);
  const { unmount } = render(<PlanDays data={d} startName="Hausach" />);
  expect(screen.queryByRole("button", { name: "Merken" })).toBeNull();
  unmount();
  h.session = { user: {} };
  h.savePlan.mockResolvedValue({ error: null });
  render(<PlanDays data={d} startName="Hausach" />);
  await userEvent.click(screen.getByRole("button", { name: "Merken" }));
  expect(h.savePlan).toHaveBeenCalledWith("multiday", "Westweg (Westvariante) ab Hausach, 3 Tage", d);
});

it("planTitle prefers the trail label", () => {
  expect(planTitle(data([day(1)], { labels: { "trail:westweg-west": "Westweg" } }), "Hausach")).toBe("Westweg ab Hausach, 1 Tag");
});
