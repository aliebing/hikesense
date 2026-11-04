import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { existsSync } from "node:fs";
import { join } from "node:path";

vi.mock("../../components/AccountMenu", () => ({ default: () => null }));

import AdminPage from "./page";
import { renderWithLocale } from "../../test-utils";

const json = (status: number, body: unknown) => ({ ok: status < 300, status, json: async () => body }) as Response;
const item = (id: string, owner: string, msg: string, over = {}) => ({
  request_id: id, ts: "2026-11-02T13:02:00Z", owner, email: "a@x.de", message: msg, intent: "day_hike", hits: 3, fallback: false,
  tool_calls: 2, tokens: 3530, cost_usd: 0.0021, duration_ms: 4200, error: null, detailed: true, ...over,
});
const users = { users: [{ user_id: "u1", email: "anna@x.de", status: "aktiv", created_at: "2026-11-01T09:00:00Z", last_sign_in_at: null, searches: 2 }, { user_id: "u2", email: "ali@x.de", status: "gesperrt", created_at: "2026-11-01T09:00:00Z", last_sign_in_at: null, searches: 1 }, { user_id: "unknown", email: null, status: null, created_at: null, last_sign_in_at: null, searches: 1 }], total: 3 };
const sums = { count: 4, cost_usd: 0.41, avg_duration_ms: 3600 };

let calls: string[];
let signedIn: boolean;
function route(me: Response, extra: Record<string, (u: string) => Response> = {}) {
  calls = [];
  signedIn = me.ok;
  vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
    const u = String(input);
    calls.push(u);
    if (u.endsWith("/backend/login")) {
      const body = JSON.parse(String(init?.body));
      if (body.password !== "richtig") return json(401, { detail: "Anmeldung fehlgeschlagen" });
      signedIn = true;
      return json(200, { name: "admin" });
    }
    if (u.endsWith("/backend/logout")) { signedIn = false; return json(200, { ok: true }); }
    if (u.endsWith("/backend/me")) return signedIn ? json(200, { name: "admin" }) : me.ok ? json(401, { detail: "Bitte anmelden" }) : me;
    if (u.endsWith("/backend/users")) return json(200, users);
    for (const [k, f] of Object.entries(extra)) if (u.includes(k)) return f(u);
    if (u.includes("/backend/searches/")) return json(200, { request_id: "x", ts: "2026-11-02T13:02:00Z", owner: "u1", email: "a@x.de", message: "Detailtext", llm_calls: [], tools: [] });
    if (u.includes("user=u2")) return json(200, { items: [item("s9", "u2", "Von Ali")], total: 1, sums: { count: 1, cost_usd: 0.002, avg_duration_ms: 1000 } });
    if (u.includes("offset=50")) return json(200, { items: [item("s2", "u1", "Zweite Seite")], total: 4, sums });
    return json(200, { items: [item("s1", "u1", "Rundtour Feldberg")], total: 4, sums });
  });
}

const ME = { name: "admin" };

beforeEach(() => {
  vi.restoreAllMocks();
});

it("shows the login form when not signed in, and asks nothing else", async () => {
  route(json(401, { detail: "Bitte anmelden" }));
  render(<AdminPage />);
  expect(await screen.findByLabelText("Name")).toBeInTheDocument();
  expect(screen.getByLabelText("Passwort")).toHaveAttribute("type", "password");
  expect(calls).toEqual(["/api/backend/me"]);
});

it("shows users after login", async () => {
  route(json(401, { detail: "Bitte anmelden" }));
  render(<AdminPage />);
  await userEvent.type(await screen.findByLabelText("Name"), "admin");
  await userEvent.type(screen.getByLabelText("Passwort"), "richtig");
  await userEvent.click(screen.getByRole("button", { name: "Anmelden" }));
  expect(await screen.findByText("Alle (4)")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Abmelden" })).toBeInTheDocument();
});

it("login error shows message", async () => {
  route(json(401, { detail: "Bitte anmelden" }));
  render(<AdminPage />);
  await userEvent.type(await screen.findByLabelText("Name"), "admin");
  await userEvent.type(screen.getByLabelText("Passwort"), "falsch");
  await userEvent.click(screen.getByRole("button", { name: "Anmelden" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Name oder Passwort falsch");
});

it("Abmelden returns to the login form", async () => {
  route(json(200, ME));
  render(<AdminPage />);
  await userEvent.click(await screen.findByRole("button", { name: "Abmelden" }));
  expect(await screen.findByLabelText("Name")).toBeInTheDocument();
  expect(calls).toContain("/api/backend/logout");
});

it("the old /admin page is gone", () => {
  expect(existsSync(join(__dirname, "..", "admin"))).toBe(false);
});

it("shows the message when the backend is unavailable", async () => {
  route(json(503, { detail: "Nicht eingerichtet" }));
  render(<AdminPage />);
  expect(await screen.findByText("Nicht eingerichtet")).toBeInTheDocument();
});

it("lists users, selects another one and shows summary row", async () => {
  route(json(200, ME));
  render(<AdminPage />);
  expect(await screen.findByText("Alle (4)")).toBeInTheDocument();
  expect(screen.getByText("Unbekannt (1)")).toBeInTheDocument();
  expect(await screen.findByText("Summe: 4 Suchen · 0,4100 $ · Ø 3,6 s")).toBeInTheDocument();
  fireEvent.click(screen.getByText("ali@x.de (1)"));
  await waitFor(() => expect(calls.some((c) => c.includes("/backend/searches?user=u2"))).toBe(true));
  expect((await screen.findAllByText("Von Ali")).length).toBeGreaterThan(0);
  await waitFor(() => expect(calls.some((c) => c.includes("/backend/searches/s9"))).toBe(true));
});

it("loads more with offset=50", async () => {
  route(json(200, ME));
  render(<AdminPage />);
  fireEvent.click(await screen.findByRole("button", { name: "Mehr laden" }));
  await waitFor(() => expect(calls.some((c) => c.includes("offset=50"))).toBe(true));
  expect((await screen.findAllByText("Zweite Seite")).length).toBeGreaterThan(0);
});

it("shows details of a clicked row", async () => {
  route(json(200, ME));
  render(<AdminPage />);
  await screen.findByText("Alle (4)");
  expect(await screen.findByText("Detailtext")).toBeInTheDocument();
});

describe("in English", () => {
  it("shows the login form in English", async () => {
    route(json(401, { detail: "Bitte anmelden" }));
    renderWithLocale(<AdminPage />, "en");
    expect(await screen.findByLabelText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows the table header and the total row in English", async () => {
    route(json(200, ME));
    renderWithLocale(<AdminPage />, "en");
    expect(await screen.findByText("All (4)")).toBeInTheDocument();
    expect(await screen.findByText("Total: 4 searches · $0.4100 · avg 3.6 s")).toBeInTheDocument();
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
