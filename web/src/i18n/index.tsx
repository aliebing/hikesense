"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { de } from "./de";
import { en, type Messages } from "./en";

export type Locale = "en" | "de";
export const STORAGE_KEY = "hikeall.lang";

const catalogs: Record<Locale, Messages> = { en, de };

/** Intl locale for a UI language (time zone stays Europe/Berlin where used). */
export function intlLocale(l: Locale): "en-GB" | "de-DE" {
  return l === "de" ? "de-DE" : "en-GB";
}

function isLocale(v: unknown): v is Locale {
  return v === "en" || v === "de";
}

function readStored(): Locale | null {
  try {
    const v = window.localStorage.getItem(STORAGE_KEY);
    return isLocale(v) ? v : null;
  } catch {
    return null;
  }
}

type Ctx = { locale: Locale; setLocale: (l: Locale) => void };
const LocaleContext = createContext<Ctx | null>(null);

/** Without a provider (isolated component tests) the language comes from a test hook, else English. */
function fallbackLocale(): Locale {
  const g = (globalThis as { __HIKEALL_DEFAULT_LOCALE__?: unknown }).__HIKEALL_DEFAULT_LOCALE__;
  return isLocale(g) ? g : "en";
}

/** Server and first client render are English; the stored choice is applied right after mount. */
export function LocaleProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = readStored();
    if (stored) setLocaleState(stored);
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // storage unavailable: the choice just lasts for this page view
    }
  }, []);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): Ctx {
  const ctx = useContext(LocaleContext);
  return ctx ?? { locale: fallbackLocale(), setLocale: () => {} };
}

export function useT(): Messages {
  return catalogs[useLocale().locale];
}
