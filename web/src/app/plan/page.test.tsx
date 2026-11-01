import { render, screen } from "@testing-library/react";
import { ChatProvider } from "../../components/ChatProvider";
import { initialState, saveState } from "../../lib/chatState";
import type { TrailDetail } from "../../lib/data";

const h = vi.hoisted(() => ({ id: null as string | null, session: null as null | object, getTrail: vi.fn(), getLodgings: vi.fn() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => ({ get: () => h.id }) }));
vi.mock("../../lib/auth", () => ({ useSession: () => ({ session: h.session, loading: false }), getBrowserSupabase: () => ({}), onSignedOut: () => () => {} }));
vi.mock("../../lib/data", async (orig) => ({ ...(await orig<typeof import("../../lib/data")>()), getTrail: h.getTrail, getLodgings: h.getLodgings }));
vi.mock("../../components/PlanMap", () => ({ default: (p: { embedded?: boolean }) => <p data-testid="plan-map">{p.embedded ? "embedded" : "button"}</p> }));
vi.mock("../../components/AccountMenu", () => ({ default: () => null }));

import PlanPage from "./page";

const day = { day: 1, date: null, start_km: 0, end_km: 15, walk_km: 15, access_km: 0, length_km: 15, ascent_m: 1, descent_m: 1, duration_h: 4, start_time: "09:00:00", arrival: "13:00:00", stop: null, gap: null, within_band: true };
const plan = { plan: { trail_id: "westweg-west", trail_name: "Westweg", target_km: 15, days: [day], notes: [], source_ids: [] }, weather: {}, rain: {} };
const trail = { id: "westweg-west", name: "Westweg", kind: "long_distance", length_km: 285, ascent_m: 1, descent_m: 1, stage_count: 0, center_lat: 48, cover: null, stages: [], photos: [], geom: null, sources: [] } as unknown as TrailDetail;

const show = () =>
  render(
    <ChatProvider>
      <PlanPage />
    </ChatProvider>,
  );

beforeEach(() => {
  sessionStorage.clear();
  h.id = null;
  h.session = null;
  h.getTrail.mockReset().mockResolvedValue(trail);
  h.getLodgings.mockReset().mockResolvedValue([]);
  vi.spyOn(console, "error").mockImplementation(() => {});
});

it("without id: the chat's plan with the map on top", async () => {
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  const map = await screen.findByTestId("plan-map");
  expect(map).toHaveTextContent("embedded");
  const days = screen.getByRole("list", { name: "Tage" });
  expect(map.compareDocumentPosition(days) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(h.getTrail).toHaveBeenCalledWith("westweg-west");
  expect(screen.getByRole("link", { name: "← Zurück zum Chat" })).toHaveAttribute("href", "/");
});

it("without id, trail fails to load: the days stay, no map", async () => {
  h.getTrail.mockRejectedValue(new Error("down"));
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  expect(await screen.findByRole("list", { name: "Tage" })).toHaveTextContent("Tag 1");
  await vi.waitFor(() => expect(h.getTrail).toHaveBeenCalled());
  expect(screen.queryByTestId("plan-map")).toBeNull();
});

it("without id and without a plan in the chat: a hint and the way home", async () => {
  show();
  expect(await screen.findByText("Noch kein Plan im Chat.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zur Startseite" })).toHaveAttribute("href", "/");
});

it("with id and no session: asks to sign in", () => {
  h.id = "p1";
  show();
  expect(screen.getByText(/Zum Ansehen deines Plans bitte/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Meine Pläne" })).toHaveAttribute("href", "/meine-plaene");
});
