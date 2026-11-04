const sb = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  getSession: vi.fn(),
}));
vi.mock("@supabase/supabase-js", () => ({ createClient: () => ({ auth: sb }) }));

import { checkBlocked, getAccessToken, onBlocked, reportBlocked, safeNext, signIn, signOut, signUp } from "./auth";

beforeEach(() => {
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://sb");
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_ANON_KEY", "anon");
});
afterEach(() => vi.unstubAllEnvs());

it("maps supabase error to German", async () => {
  sb.signInWithPassword.mockResolvedValue({ data: {}, error: { message: "Invalid login credentials" } });
  expect(await signIn("a@b.de", "x", "de")).toEqual({ error: "E-Mail oder Passwort falsch" });
  sb.signUp.mockResolvedValue({ data: {}, error: { message: "User already registered" } });
  expect((await signUp("a@b.de", "xxxxxx", "de")).error).toMatch(/schon registriert/);
});

it("sign-up without session asks to confirm the e-mail", async () => {
  sb.signUp.mockResolvedValue({ data: { session: null, user: {} }, error: null });
  expect(await signUp("a@b.de", "xxxxxx", "de")).toEqual({ error: null, notice: "Bitte bestätige deine E-Mail-Adresse" });
  sb.signUp.mockResolvedValue({ data: { session: {}, user: {} }, error: null });
  expect(await signUp("a@b.de", "xxxxxx", "de")).toEqual({ error: null });
});

it("signs in and out, and reads the token", async () => {
  sb.signInWithPassword.mockResolvedValue({ data: {}, error: null });
  expect(await signIn("a@b.de", "x", "de")).toEqual({ error: null });
  sb.signOut.mockResolvedValue({ error: null });
  expect(await signOut("de")).toEqual({ error: null });
  sb.getSession.mockResolvedValue({ data: { session: { access_token: "t" } } });
  expect(await getAccessToken()).toBe("t");
  sb.getSession.mockRejectedValue(new Error("x"));
  expect(await getAccessToken()).toBeNull();
});

it("safeNext keeps only relative paths of this site", () => {
  expect(safeNext("/gemerkt")).toBe("/gemerkt");
  expect(safeNext("/t/abc?x=1")).toBe("/t/abc?x=1");
  expect(safeNext(null)).toBe("/");
  expect(safeNext("https://evil.example")).toBe("/");
  expect(safeNext("//evil.example")).toBe("/");
  expect(safeNext("/\\evil.example")).toBe("/");
  expect(safeNext("gemerkt")).toBe("/");
});

it("checkBlocked asks /api/account with the token", async () => {
  sb.getSession.mockResolvedValue({ data: { session: { access_token: "tok" } } });
  const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response('{"detail":"account_blocked"}', { status: 403 }));
  expect(await checkBlocked()).toBe(true);
  expect(f.mock.calls[0][0]).toBe("/api/account");
  expect((f.mock.calls[0][1] as RequestInit).headers).toEqual({ Authorization: "Bearer tok" });
  f.mockResolvedValue(new Response('{"status":"aktiv"}', { status: 200 }));
  expect(await checkBlocked()).toBe(false);
  f.mockRejectedValue(new TypeError("offline"));
  expect(await checkBlocked()).toBe(false);
  f.mockRestore();
});

it("checkBlocked without a session asks nothing", async () => {
  sb.getSession.mockResolvedValue({ data: { session: null } });
  const f = vi.spyOn(globalThis, "fetch");
  expect(await checkBlocked()).toBe(false);
  expect(f).not.toHaveBeenCalled();
  f.mockRestore();
});

it("reportBlocked reaches every listener until it unsubscribes", () => {
  const seen: number[] = [];
  const off = onBlocked(() => seen.push(1));
  reportBlocked();
  off();
  reportBlocked();
  expect(seen).toEqual([1]);
});
