import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import LanguageFlags from "../components/LanguageFlags";
import { de } from "./de";
import { en } from "./en";
import { intlLocale, LocaleProvider, useLocale, useT } from "./index";

function Probe() {
  const { locale } = useLocale();
  const t = useT();
  return <p>{locale}:{t.common.flags.group}</p>;
}

beforeEach(() => window.localStorage.clear());
afterEach(() => vi.restoreAllMocks());

it("is English without a stored choice", () => {
  render(<LocaleProvider><Probe /></LocaleProvider>);
  expect(screen.getByText("en:Language")).toBeInTheDocument();
  expect(document.documentElement.lang).toBe("en");
});

it("setLocale stores the choice and renders German", async () => {
  render(<LocaleProvider><Probe /><LanguageFlags /></LocaleProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  expect(screen.getByText("de:Sprache")).toBeInTheDocument();
  expect(window.localStorage.getItem("hikeall.lang")).toBe("de");
  expect(document.documentElement.lang).toBe("de");
});

it("applies the stored choice after mount", () => {
  window.localStorage.setItem("hikeall.lang", "de");
  render(<LocaleProvider><Probe /></LocaleProvider>);
  expect(screen.getByText("de:Sprache")).toBeInTheDocument();
});

it("falls back to English when localStorage throws", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
  render(<LocaleProvider><Probe /><LanguageFlags /></LocaleProvider>);
  expect(screen.getByText("en:Language")).toBeInTheDocument();
  await act(async () => { await userEvent.click(screen.getByRole("button", { name: "Deutsch" })); });
  expect(screen.getByText("de:Sprache")).toBeInTheDocument();
});

function keyPaths(o: unknown, prefix = ""): string[] {
  if (o === null || typeof o !== "object") return [prefix];
  return Object.entries(o).flatMap(([k, v]) => keyPaths(v, prefix ? `${prefix}.${k}` : k));
}

it("English and German catalogs have the same keys", () => {
  expect(keyPaths(de).sort()).toEqual(keyPaths(en).sort());
});

it("maps the language to an Intl locale", () => {
  expect(intlLocale("en")).toBe("en-GB");
  expect(intlLocale("de")).toBe("de-DE");
});

it("flags mark the active language with aria-pressed", async () => {
  render(<LocaleProvider><LanguageFlags /></LocaleProvider>);
  expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "Deutsch" })).toHaveAttribute("aria-pressed", "false");
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  expect(screen.getByRole("button", { name: "Deutsch" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("button", { name: "English" })).toHaveAttribute("aria-pressed", "false");
});
