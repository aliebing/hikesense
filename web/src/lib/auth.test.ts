const sb = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  getSession: vi.fn(),
  resend: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  updateUser: vi.fn(),
}));
vi.mock("@supabase/supabase-js", () => ({ createClient: () => ({ auth: sb }) }));

import { checkBlocked, getAccessToken, onBlocked, reportBlocked, requestPasswordReset, resendConfirmation, safeNext, setNewPassword, signIn, signOut, signUp } from "./auth";

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

it("signUp sends the confirmation link back to /anmelden/bestaetigt", async () => {
  sb.signUp.mockResolvedValue({ data: { session: null, user: {} }, error: null });
  await signUp("a@b.de", "xxxxxx", "de");
  expect(sb.signUp).toHaveBeenLastCalledWith({ email: "a@b.de", password: "xxxxxx", options: { emailRedirectTo: `${window.location.origin}/anmelden/bestaetigt` } });
});

it("resendConfirmation resends the sign-up mail", async () => {
  sb.resend.mockResolvedValue({ error: null });
  expect(await resendConfirmation("a@b.de", "de")).toEqual({ error: null, notice: "Bestätigungsmail ist unterwegs." });
  expect(sb.resend).toHaveBeenCalledWith({ type: "signup", email: "a@b.de", options: { emailRedirectTo: `${window.location.origin}/anmelden/bestaetigt` } });
});

it("requestPasswordReset gives the same neutral notice whether the address exists or not", async () => {
  sb.resetPasswordForEmail.mockResolvedValueOnce({ error: { message: "User not found" } });
  const unknown = await requestPasswordReset("nobody@b.de", "de");
  sb.resetPasswordForEmail.mockResolvedValueOnce({ error: null });
  const known = await requestPasswordReset("a@b.de", "de");
  expect(unknown).toEqual(known);
  expect(known).toEqual({ error: null, notice: "Wenn es ein Konto mit dieser Adresse gibt, haben wir dir einen Link geschickt." });
  expect(sb.resetPasswordForEmail).toHaveBeenLastCalledWith("a@b.de", { redirectTo: `${window.location.origin}/passwort-neu` });
});

it("requestPasswordReset says so when Supabase refuses for too many mails", async () => {
  sb.resetPasswordForEmail.mockResolvedValueOnce({ error: { message: "email rate limit exceeded", status: 429 } });
  expect(await requestPasswordReset("a@b.de", "de")).toEqual({ error: "Zu viele Versuche – bitte warte einen Moment" });
  sb.resetPasswordForEmail.mockResolvedValueOnce({ error: { message: "For security purposes, you can only request this after 40 seconds.", status: 429 } });
  expect((await requestPasswordReset("a@b.de", "en")).error).toBe("Too many attempts – please wait a moment");
});

it("requestPasswordReset reports only an unreachable service", async () => {
  sb.resetPasswordForEmail.mockRejectedValueOnce(new TypeError("offline"));
  expect((await requestPasswordReset("a@b.de", "de")).error).toMatch(/nicht erreichbar/);
});

it("setNewPassword updates the password and maps errors", async () => {
  sb.updateUser.mockResolvedValueOnce({ data: {}, error: null });
  expect(await setNewPassword("neues-pw-1", "de")).toEqual({ error: null });
  expect(sb.updateUser).toHaveBeenCalledWith({ password: "neues-pw-1" });
  sb.updateUser.mockResolvedValueOnce({ data: {}, error: { message: "Password should be at least 6 characters" } });
  expect((await setNewPassword("x", "de")).error).toMatch(/zu kurz/);
});

it("a blocked account signing in is told so", async () => {
  sb.signInWithPassword.mockResolvedValue({ data: {}, error: { message: "User is banned" } });
  expect(await signIn("a@b.de", "x", "de")).toEqual({ error: "Dein Konto ist gesperrt." });
  expect(await signIn("a@b.de", "x", "en")).toEqual({ error: "Your account has been blocked." });
});
