import { de } from "./de";
import { en, type Messages } from "./en";

/** Plain module (no "use client"): usable from server and client components alike. */
export type Locale = "en" | "de";
export const STORAGE_KEY = "hikeall.lang";
export const COOKIE_NAME = "hikeall.lang";

const catalogs: Record<Locale, Messages> = { en, de };

export function isLocale(v: unknown): v is Locale {
  return v === "en" || v === "de";
}

/** Intl locale for a UI language (time zone stays Europe/Berlin where used). */
export function intlLocale(l: Locale): "en-GB" | "de-DE" {
  return l === "de" ? "de-DE" : "en-GB";
}

/** Catalog lookup without hooks, e.g. for server components. */
export function messagesFor(l: Locale): Messages {
  return catalogs[l];
}
