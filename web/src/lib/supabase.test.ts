import { browserSupabaseUrl } from "./supabase";

afterEach(() => vi.unstubAllEnvs());

it("defaults to the same origin (/sb, proxied by Next) so one tunnel to :3000 serves the phone", () => {
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "");
  expect(browserSupabaseUrl()).toBe(`${window.location.origin}/sb`);
});

it("keeps an explicit NEXT_PUBLIC_SUPABASE_URL", () => {
  vi.stubEnv("NEXT_PUBLIC_SUPABASE_URL", "http://127.0.0.1:54321");
  expect(browserSupabaseUrl()).toBe("http://127.0.0.1:54321");
});
