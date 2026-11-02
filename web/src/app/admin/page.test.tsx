import { fireEvent, render, screen, waitFor } from "@testing-library/react";

const h = vi.hoisted(() => ({ session: { user: {} } as null | object }));
vi.mock("../../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  getAccessToken: async () => "tok",
}));
vi.mock("../../components/AccountMenu", () => ({ default: () => null }));

import AdminPage from "./page";
import { renderWithLocale } from "../../test-utils";

const json = (status: number, body: unknown) => ({ ok: status < 300, status, json: async () => body }) as Response;
const item = (id: string, owner: string, msg: string, over = {}) => ({
  request_id: id, ts: "2026-11-02T13:02:00Z", owner, email: "a@x.de", message: msg, intent: "day_hike", hits: 3, fallback: false,
  tool_calls: 2, tokens: 3530, cost_usd: 0.0021, duration_ms: 4200, error: null, detailed: true, ...over,
});
const users = { users: [{ user_id: "u1", email: "anna@x.de", role: "admin", searches: 2 }, { user_id: "u2", email: "ali@x.de", role: "user", searches: 1 }, { user_id: "unknown", email: null, role: null, searches: 1 }], total: 3 };
const sums = { count: 4, cost_usd: 0.41, avg_duration_ms: 3600 };

let calls: string[];
function route(me: Response, extra: Record<string, (u: string) => Response> = {}) {
  calls = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
    const u = String(input);
    calls.push(u);
    if (u.endsWith("/admin/me")) return me;
    if (u.endsWith("/admin/users")) return json(200, users);
    for (const [k, f] of Object.entries(extra)) if (u.includes(k)) return f(u);
    if (u.includes("/admin/searches/")) return json(200, { request_id: "x", ts: "2026-11-02T13:02:00Z", owner: "u1", email: "a@x.de", message: "Detailtext", llm_calls: [], tools: [] });
    if (u.includes("user=u2")) return json(200, { items: [item("s9", "u2", "Von Ali")], total: 1, sums: { count: 1, cost_usd: 0.002, avg_duration_ms: 1000 } });
    if (u.includes("offset=50")) return json(200, { items: [item("s2", "u1", "Zweite Seite")], total: 4, sums });
    return json(200, { items: [item("s1", "u1", "Rundtour Feldberg")], total: 4, sums });
  });
}

beforeEach(() => {
  h.session = { user: {} };
  vi.restoreAllMocks();
});

it("asks to sign in without a session", () => {
  h.session = null;
  route(json(200, {}));
  render(<AdminPage />);
  expect(screen.getByRole("link", { name: "Bitte anmelden" })).toHaveAttribute("href", "/anmelden");
  expect(calls).toEqual([]);
});

it("non-admin: only Kein Zugriff, no further requests", async () => {
  route(json(403, { detail: "Kein Zugriff" }));
  render(<AdminPage />);
  expect(await screen.findByText("Kein Zugriff")).toBeInTheDocument();
  expect(calls).toEqual(["/api/admin/me"]);
});

it("shows the message when the backend is unavailable", async () => {
  route(json(503, { detail: "Nicht eingerichtet" }));
  render(<AdminPage />);
  expect(await screen.findByText("Nicht eingerichtet")).toBeInTheDocument();
});

it("lists users, selects another one and shows summary row", async () => {
  route(json(200, { user_id: "u1", role: "admin" }));
  render(<AdminPage />);
  expect(await screen.findByText("Alle (4)")).toBeInTheDocument();
  expect(screen.getByText("Unbekannt (1)")).toBeInTheDocument();
  expect(await screen.findByText("Summe: 4 Suchen · 0,4100 $ · Ø 3,6 s")).toBeInTheDocument();
  fireEvent.click(screen.getByText("ali@x.de (1)"));
  await waitFor(() => expect(calls.some((c) => c.includes("/admin/searches?user=u2"))).toBe(true));
  expect((await screen.findAllByText("Von Ali")).length).toBeGreaterThan(0);
  await waitFor(() => expect(calls.some((c) => c.includes("/admin/searches/s9"))).toBe(true));
});

it("loads more with offset=50", async () => {
  route(json(200, { user_id: "u1", role: "admin" }));
  render(<AdminPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Mehr laden" }));
  await waitFor(() => expect(calls.some((c) => c.includes("offset=50"))).toBe(true));
  expect((await screen.findAllByText("Zweite Seite")).length).toBeGreaterThan(0);
});

it("shows details of a clicked row", async () => {
  route(json(200, { user_id: "u1", role: "admin" }));
  render(<AdminPage />);
  await screen.findByText("Alle (4)");
  expect(await screen.findByText("Detailtext")).toBeInTheDocument();
});

describe("in English", () => {
  it("says No access for a 403", async () => {
    route(json(403, { detail: "Kein Zugriff" }));
    renderWithLocale(<AdminPage />, "en");
    expect(await screen.findByText("No access")).toBeInTheDocument();
  });

  it("shows the table header and the total row in English", async () => {
    route(json(200, { user_id: "u1", role: "admin" }));
    renderWithLocale(<AdminPage />, "en");
    expect(await screen.findByText("All (4)")).toBeInTheDocument();
    expect(await screen.findByText("Total: 4 searches · 0.4100 $ · Ø 3.6 s")).toBeInTheDocument();
    for (const h of ["Time", "User", "Search", "Hits"]) expect(screen.getByRole("columnheader", { name: h })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load more" })).toBeInTheDocument();
    expect(screen.getByText("Recent searches · all")).toBeInTheDocument();
  });

  it("translates a backend failure by its status", async () => {
    route(json(503, { detail: "Nicht eingerichtet" }));
    renderWithLocale(<AdminPage />, "en");
    expect(await screen.findByText("Not set up")).toBeInTheDocument();
  });
});
