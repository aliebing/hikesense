import { adminErrorText, backendGet, backendLogin, backendLogout, backendPost, ms, usd, when } from "./backend";

const reply = (status: number, body: unknown) => ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

beforeEach(() => {
  vi.restoreAllMocks();
});

it("formats costs and durations", () => {
  expect(usd(null, "de")).toBe("–");
  expect(usd(0.0021, "de")).toBe("0,0021 $");
  expect(ms(4200, "de")).toBe("4,2 s");
  expect(ms(null, "de")).toBe("–");
  expect(usd(0.0021, "en")).toBe("$0.0021");
  expect(ms(4200, "en")).toBe("4.2 s");
});

it("formats the time relative to today", () => {
  const now = new Date("2026-11-02T12:00:00Z");
  expect(when("2026-11-02T13:02:00Z", "de", now)).toBe("heute 14:02");
  expect(when("2026-11-01T08:12:00Z", "de", now)).toBe("gestern 09:12");
  expect(when("2026-10-31T17:40:00Z", "de", now)).toBe("31.10. 18:40");
  expect(when("2026-11-02T13:02:00Z", "en", now)).toBe("today 14:02");
  expect(when("2026-11-01T08:12:00Z", "en", now)).toBe("yesterday 09:12");
  expect(when("2026-10-31T17:40:00Z", "en", now)).toBe("31/10 18:40");
});

it("turns a status into a catalog text", () => {
  expect(adminErrorText(401, "en")).toBe("Please sign in");
  expect(adminErrorText(403, "en")).toBe("No access");
  expect(adminErrorText(503, "en")).toBe("Not set up");
  expect(adminErrorText(0, "en")).toBe("Backend unreachable");
  expect(adminErrorText(500, "en")).toBe("Error 500");
  expect(adminErrorText(403, "de")).toBe("Kein Zugriff");
  expect(adminErrorText(0, "de")).toBe("Backend nicht erreichbar");
});

it("asks /api/backend with the session cookie and no Supabase token", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { name: "admin" }));
  expect(await backendGet("/me")).toEqual({ ok: true, data: { name: "admin" } });
  const [url, init] = f.mock.calls[0];
  expect(url).toBe("/api/backend/me");
  expect((init as RequestInit).credentials).toBe("same-origin");
  expect(JSON.stringify((init as RequestInit).headers ?? {})).not.toMatch(/authorization/i);
});

it("returns the status on failure and 0 without a connection", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(reply(401, { detail: "Bitte anmelden" }));
  expect(await backendGet("/users")).toEqual({ ok: false, status: 401 });
  vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new TypeError("offline"));
  expect(await backendGet("/users")).toEqual({ ok: false, status: 0 });
});

it("posts login, logout and actions as JSON", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { status: "gesperrt" }));
  await backendLogin("admin", "pw");
  expect(f.mock.calls[0][0]).toBe("/api/backend/login");
  expect((f.mock.calls[0][1] as RequestInit).method).toBe("POST");
  expect(JSON.parse(String((f.mock.calls[0][1] as RequestInit).body))).toEqual({ name: "admin", password: "pw" });
  expect(await backendPost("/users/u1/block")).toEqual({ ok: true, data: { status: "gesperrt" } });
  await backendLogout();
  expect(f.mock.calls.map((c) => c[0])).toEqual(["/api/backend/login", "/api/backend/users/u1/block", "/api/backend/logout"]);
});

it("names 429 as too many tries", () => {
  expect(adminErrorText(429, "de")).toBe("Zu viele Versuche – bitte später noch einmal");
  expect(adminErrorText(429, "en")).toBe("Too many attempts – please try again later");
});
