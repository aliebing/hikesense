import { beforeEach, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("next/headers", () => ({ cookies: async () => ({ get }) }));
import { getServerLocale } from "./server";

beforeEach(() => get.mockReset());

it("defaults to English without a cookie", async () => {
  get.mockReturnValue(undefined);
  expect(await getServerLocale()).toBe("en");
});
it("reads de and ignores unknown values", async () => {
  get.mockReturnValue({ value: "de" });
  expect(await getServerLocale()).toBe("de");
  get.mockReturnValue({ value: "fr" });
  expect(await getServerLocale()).toBe("en");
});
