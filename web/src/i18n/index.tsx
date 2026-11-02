"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { COOKIE_NAME, intlLocale, isLocale, messagesFor, STORAGE_KEY, type Locale } from "./locale";
import type { Messages } from "./en";

export { intlLocale, messagesFor, STORAGE_KEY };
export type { Locale };

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
export function LocaleProvider({ children, initialLocale = "en" }: { children: React.ReactNode; initialLocale?: Locale }) {
  const router = useRouter();
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    const stored = readStored();
    if (stored) setLocaleState(stored);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // storage unavailable: the cookie below still carries the choice
    }
    // the cookie lets server components render the chosen language
    document.cookie = `${COOKIE_NAME}=${l}; path=/; max-age=31536000; SameSite=Lax`;
    router.refresh();
  }, [router]);

  const value = useMemo(() => ({ locale, setLocale }), [locale, setLocale]);
  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): Ctx {
  const ctx = useContext(LocaleContext);
  return ctx ?? { locale: fallbackLocale(), setLocale: () => {} };
}

export function useT(): Messages {
  return messagesFor(useLocale().locale);
}
