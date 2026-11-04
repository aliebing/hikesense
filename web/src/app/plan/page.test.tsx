import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithLocale } from "../../test-utils";
import { ChatProvider } from "../../components/ChatProvider";
import { initialState, saveState } from "../../lib/chatState";
import type { TrailDetail } from "../../lib/data";

const h = vi.hoisted(() => ({ row: { data: null, error: null } as { data: unknown; error: unknown }, id: null as string | null, session: null as null | object, getTrail: vi.fn(), getLodgings: vi.fn() }));
vi.mock("next/navigation", () => ({ useSearchParams: () => ({ get: () => h.id }), useRouter: () => ({ refresh() {} }) }));
vi.mock("../../lib/auth", () => ({
  checkBlocked: async () => false,
  onBlocked: () => () => {},
  reportBlocked: () => {}, useSession: () => ({ session: h.session, loading: false }), getBrowserSupabase: () => ({ from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => h.row }) }) }) }), onSignedOut: () => () => {} }));
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

it("saved plan: a language switch keeps the loaded plan (no blank, no second load)", async () => {
  h.id = "p1";
  h.session = { user: {} };
  h.row = { data: { title: "Mein Plan", kind: "multiday", payload: plan, created_at: "2026-10-28T10:00:00Z" }, error: null };
  renderWithLocale(<PlanPage />, "en");
  expect(await screen.findByRole("list", { name: "Days" })).toBeInTheDocument();
  expect(h.getTrail).toHaveBeenCalledTimes(1);
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  await waitFor(() => expect(screen.getByRole("list", { name: "Tage" })).toBeInTheDocument());
  expect(h.getTrail).toHaveBeenCalledTimes(1);
});

it("saved plan error follows the language", async () => {
  h.id = "p1";
  h.session = { user: {} };
  h.row = { data: null, error: null };
  renderWithLocale(<PlanPage />, "en");
  expect(await screen.findByRole("alert")).toHaveTextContent("Plan not found");
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Plan nicht gefunden"));
});
