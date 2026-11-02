import { adminErrorText, adminGet, ms, usd, when } from "./admin";

const h = vi.hoisted(() => ({ token: "tok" as string | null }));
vi.mock("./auth", () => ({ getAccessToken: async () => h.token }));

const reply = (status: number, body: unknown) => ({ ok: status >= 200 && status < 300, status, json: async () => body }) as Response;

beforeEach(() => {
  h.token = "tok";
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

it("needs a token", async () => {
  h.token = null;
  const f = vi.spyOn(globalThis, "fetch");
  expect(await adminGet("/me")).toEqual({ ok: false, status: 401 });
  expect(f).not.toHaveBeenCalled();
});

it("sends the token and returns data", async () => {
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(200, { user_id: "u" }));
  expect(await adminGet("/me")).toEqual({ ok: true, data: { user_id: "u" } });
  expect(f).toHaveBeenCalledWith("/api/admin/me", { headers: { Authorization: "Bearer tok" } });
});

it("returns the detail of an error", async () => {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(reply(403, { detail: "Kein Zugriff" }));
  expect(await adminGet("/me")).toEqual({ ok: false, status: 403 });
});

it("reports a network error", async () => {
  vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("x"));
  expect(await adminGet("/me")).toEqual({ ok: false, status: 0 });
});
