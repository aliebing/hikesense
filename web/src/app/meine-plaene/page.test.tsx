import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const h = vi.hoisted(() => ({
  session: null as null | { user: { email: string } },
  loading: false,
  listPlans: vi.fn(),
  deletePlan: vi.fn(),
  blocked: false,
  report: vi.fn(),
}));
vi.mock("../../lib/auth", () => ({
  checkBlocked: async () => h.blocked,
  onBlocked: () => () => {},
  reportBlocked: h.report,
  useSession: () => ({ session: h.session, loading: h.loading }),
  signOut: vi.fn(async () => ({ error: null })),
}));
vi.mock("../../lib/plans", async (orig) => ({ ...(await orig<typeof import("../../lib/plans")>()), listPlans: h.listPlans, deletePlan: h.deletePlan }));

import MeinePlaene from "./page";
import { renderWithLocale } from "../../test-utils";

const plans = [
  { id: "p1", kind: "day_hike", title: "Feldsee-Runde", payload: { trail_id: "t1" }, created_at: "2026-10-30T10:00:00Z" },
  { id: "p2", kind: "multiday", title: "Westweg in 5 Tagen", payload: {}, created_at: "2026-10-29T10:00:00Z" },
];

beforeEach(() => {
  vi.clearAllMocks();
  h.blocked = false;
  h.session = { user: { email: "a@b.de" } };
  h.loading = false;
  h.listPlans.mockResolvedValue({ plans, error: null });
});

it("asks to sign in without a session", () => {
  h.session = null;
  render(<MeinePlaene />);
  expect(screen.getByText(/Zum Ansehen deiner Pläne/)).toBeInTheDocument();
  for (const l of screen.getAllByRole("link", { name: "Anmelden" })) expect(l).toHaveAttribute("href", "/anmelden");
  expect(h.listPlans).not.toHaveBeenCalled();
});

it("lists title, kind, date and links to the tour or the plan view", async () => {
  render(<MeinePlaene />);
  expect(await screen.findByRole("link", { name: "Feldsee-Runde" })).toHaveAttribute("href", "/t/t1");
  expect(screen.getByRole("link", { name: "Westweg in 5 Tagen" })).toHaveAttribute("href", "/plan?id=p2");
  expect(screen.getByText(/Tageswanderung/)).toBeInTheDocument();
  expect(screen.getByText(/Mehrtagestour/)).toBeInTheDocument();
  expect(screen.getByText(/30\.10\.2026/)).toBeInTheDocument();
});

it("deletes a plan and removes it from the list", async () => {
  h.deletePlan.mockResolvedValue({ error: null });
  render(<MeinePlaene />);
  await screen.findByText("Feldsee-Runde");
  await userEvent.click(screen.getAllByRole("button", { name: /Löschen/ })[0]);
  await waitFor(() => expect(screen.queryByText("Feldsee-Runde")).toBeNull());
  expect(h.deletePlan).toHaveBeenCalledWith("p1");
});

it("shows an empty hint and load errors", async () => {
  h.listPlans.mockResolvedValue({ plans: [], error: null });
  const { unmount } = render(<MeinePlaene />);
  expect(await screen.findByText(/noch keine Pläne/)).toBeInTheDocument();
  unmount();
  h.listPlans.mockResolvedValue({ plans: [], error: "load" });
  render(<MeinePlaene />);
  expect(await screen.findByRole("alert")).toHaveTextContent("nicht geladen");
});

it("clears the list on sign-out (shared device)", async () => {
  const { rerender } = render(<MeinePlaene />);
  expect(await screen.findByText("Feldsee-Runde")).toBeInTheDocument();
  h.session = null;
  rerender(<MeinePlaene />);
  expect(screen.queryByText("Feldsee-Runde")).toBeNull();
  expect(screen.getByText(/Zum Ansehen deiner Pläne/)).toBeInTheDocument();
});

const search = { id: "s1", kind: "search", title: "Rundweg mit Einkehr", payload: { v: 1, messages: ["Rundweg mit Einkehr"], answer: "", results: { cards: [{}, {}, {}] } }, created_at: "2026-10-31T10:00:00Z" };

it("lists saved searches in their own section", async () => {
  h.listPlans.mockResolvedValue({ plans: [search, ...plans], error: null });
  render(<MeinePlaene />);
  expect(await screen.findByRole("heading", { name: "Gemerkte Suchen" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "Touren und Pläne" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Rundweg mit Einkehr" })).toHaveAttribute("href", "/gemerkt?id=s1");
  expect(screen.getByText("Suche · 31.10.2026 · 3 Touren")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Feldsee-Runde" })).toHaveAttribute("href", "/t/t1");
});

it("hides a section without entries", async () => {
  h.listPlans.mockResolvedValue({ plans: [search], error: null });
  render(<MeinePlaene />);
  await screen.findByRole("heading", { name: "Gemerkte Suchen" });
  expect(screen.queryByRole("heading", { name: "Touren und Pläne" })).toBeNull();
  expect(screen.queryByText(/noch keine Pläne/)).toBeNull();
});

it("deletes a saved search", async () => {
  h.deletePlan.mockResolvedValue({ error: null });
  h.listPlans.mockResolvedValue({ plans: [search, ...plans], error: null });
  render(<MeinePlaene />);
  await userEvent.click(await screen.findByRole("button", { name: "Löschen: Rundweg mit Einkehr" }));
  await waitFor(() => expect(screen.queryByText("Rundweg mit Einkehr")).toBeNull());
  expect(h.deletePlan).toHaveBeenCalledWith("s1");
});

it("says 1 Tour in the singular", async () => {
  h.listPlans.mockResolvedValue({ plans: [{ ...search, payload: { ...search.payload, results: { cards: [{}] } } }], error: null });
  render(<MeinePlaene />);
  expect(await screen.findByText("Suche · 31.10.2026 · 1 Tour")).toBeInTheDocument();
});

describe("in English", () => {
  it("shows heading, kind, date and delete label", async () => {
    renderWithLocale(<MeinePlaene />, "en");
    expect(screen.getByRole("heading", { level: 1, name: "My plans" })).toBeInTheDocument();
    expect(await screen.findByText("Day hike · 30/10/2026")).toBeInTheDocument();
    expect(screen.getByText(/^Multi-day tour/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Delete: Feldsee-Runde" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "← Back to chat" })).toHaveAttribute("href", "/");
  });

  it("asks to sign in, shows the empty hint and a translated error", async () => {
    h.session = null;
    const { unmount } = renderWithLocale(<MeinePlaene />, "en");
    expect(screen.getByText(/To view your plans, please/)).toBeInTheDocument();
    unmount();
    h.session = { user: { email: "a@b.de" } };
    h.listPlans.mockResolvedValue({ plans: [], error: null });
    const second = renderWithLocale(<MeinePlaene />, "en");
    expect(await screen.findByText("You haven't saved any plans yet.")).toBeInTheDocument();
    second.unmount();
    h.listPlans.mockResolvedValue({ plans: [], error: "load" });
    renderWithLocale(<MeinePlaene />, "en");
    expect(await screen.findByRole("alert")).toHaveTextContent("Your plans could not be loaded");
  });
});

it("a refused delete of a blocked account signs it out", async () => {
  h.deletePlan.mockResolvedValue({ error: "delete" });
  h.blocked = true;
  render(<MeinePlaene />);
  await screen.findByText("Feldsee-Runde");
  await userEvent.click(screen.getAllByRole("button", { name: /Löschen/ })[0]);
  await waitFor(() => expect(h.report).toHaveBeenCalledTimes(1));
});
