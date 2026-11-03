import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { LocaleProvider, type Locale } from "./i18n";

/** Renders `ui` inside a LocaleProvider that starts in `locale` (also stored, so the mount keeps it). */
export function renderWithLocale(ui: ReactElement, locale: Locale) {
  window.localStorage.setItem("hikesense.lang", locale);
  return render(<LocaleProvider initialLocale={locale}>{ui}</LocaleProvider>);
}
