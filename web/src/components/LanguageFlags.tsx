"use client";

import { useLocale, useT, type Locale } from "../i18n";

const FLAGS: { locale: Locale; flag: string; label: string }[] = [
  { locale: "en", flag: "🇬🇧", label: "English" },
  { locale: "de", flag: "🇩🇪", label: "Deutsch" },
];

/** Two flag buttons that switch the interface language; the active one is highlighted. */
export default function LanguageFlags() {
  const { locale, setLocale } = useLocale();
  const t = useT();
  return (
    <div role="group" aria-label={t.common.flags.group} className="flex items-center gap-1">
      {FLAGS.map((f) => (
        <button
          key={f.locale}
          type="button"
          aria-label={f.label}
          lang={f.locale}
          aria-pressed={locale === f.locale}
          onClick={() => setLocale(f.locale)}
          className={`inline-flex min-h-10 min-w-10 items-center justify-center rounded px-1 text-lg leading-none transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-papier ${
            locale === f.locale ? "opacity-100 ring-1 ring-papier/70" : "opacity-50 hover:opacity-100"
          }`}
        >
          <span aria-hidden="true">{f.flag}</span>
        </button>
      ))}
    </div>
  );
}
