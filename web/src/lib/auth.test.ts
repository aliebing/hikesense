const sb = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  getSession: vi.fn(),
}));
vi.mock("@supabase/supabase-js", () => ({ createClient: () => ({ auth: sb }) }));

import { getAccessToken, signIn, signOut, signUp } from "./auth";

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
