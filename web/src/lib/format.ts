import { intlLocale, type Locale } from "../i18n/locale";

const formats = {
  en: { one: mk("en", 1), zero: mk("en", 0) },
  de: { one: mk("de", 1), zero: mk("de", 0) },
};
function mk(l: Locale, digits: number) {
  return new Intl.NumberFormat(intlLocale(l), { minimumFractionDigits: digits, maximumFractionDigits: digits });
}
const one = (l: Locale) => formats[l].one;
const zero = (l: Locale) => formats[l].zero;

/** Shown instead of a number that is missing in the data (never 0). */
export const MISSING = "–";

/** 14.83 → "14,8 km"; null → "– km" */
export function km(n: number | null, locale: Locale): string {
  return `${n === null ? MISSING : one(locale).format(n)} km`;
}

/** 720 → "↑ 720 m"; null → "↑ – m" */
export function hm(n: number | null, locale: Locale): string {
  return `↑ ${n === null ? MISSING : zero(locale).format(n)} m`;
}

/** 700 → "↓ 700 m"; null → "↓ – m" */
export function hmDown(n: number | null, locale: Locale): string {
  return `↓ ${n === null ? MISSING : zero(locale).format(n)} m`;
}

/** 5.17 → "5:10 h" (rounded to whole minutes) */
export function duration(hours: number, locale: Locale): string {
  void locale; // "5:10 h" reads the same in both languages
  const minutes = Math.round(hours * 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, "0")} h`;
}

/**
 * DIN 33466 hiking time in hours (guidance, no breaks) — same formula as
 * backend/src/hikeall/hiking_time.py: max(h, v) + min(h, v) / 2 with
 * h = km / 4 and v = ascent / 300 + descent / 500, rounded to 2 decimals.
 */
export function din33466Hours(distanceKm: number, ascentM: number, descentM: number): number {
  if (Math.min(distanceKm, ascentM, descentM) < 0) {
    throw new Error("distance, ascent and descent must be >= 0");
  }
  const horizontal = distanceKm / 4;
  const vertical = ascentM / 300 + descentM / 500;
  const hours = Math.max(horizontal, vertical) + Math.min(horizontal, vertical) / 2;
  return Math.round(hours * 100) / 100;
}

/** DIN walking time as text, or null when distance, ascent or descent is missing. */
export function walkingTime(
  x: {
    length_km: number | null;
    ascent_m: number | null;
    descent_m: number | null;
  },
  locale: Locale,
): string | null {
  if (x.length_km === null || x.ascent_m === null || x.descent_m === null) return null;
  return duration(din33466Hours(x.length_km, x.ascent_m, x.descent_m), locale);
}

const numCache = new Map<string, Intl.NumberFormat>();
const dateCache = new Map<string, Intl.DateTimeFormat>();

/** A plain number in the UI language, e.g. num(3.25, "en", { max: 1 }) → "3.3"; `min` forces decimals. */
export function num(n: number, locale: Locale, o: { min?: number; max?: number } = {}): string {
  const key = `${locale}|${o.min ?? 0}|${o.max ?? 0}`;
  let f = numCache.get(key);
  if (!f) {
    f = new Intl.NumberFormat(intlLocale(locale), { minimumFractionDigits: o.min ?? 0, maximumFractionDigits: o.max ?? o.min ?? 0 });
    numCache.set(key, f);
  }
  return f.format(n).replace(/^[-\u2212](0(?:[.,]0+)?)$/, "$1"); // never "-0"
}

/** A date or time in the UI language with the given Intl options (cached formatters). */
export function dateIn(d: Date, locale: Locale, options: Intl.DateTimeFormatOptions): string {
  const key = `${locale}|${JSON.stringify(options)}`;
  let f = dateCache.get(key);
  if (!f) {
    f = new Intl.DateTimeFormat(intlLocale(locale), options);
    dateCache.set(key, f);
  }
  return f.format(d);
}

/**
 * A calendar day (ISO "2026-11-05") for cards: "Thu 5 Nov" (en) / "Do., 05.11.2026" (de), computed in UTC
 * so the day never shifts. Not a date: the input comes back unchanged.
 */
export function dayLabel(iso: string, locale: Locale): string {
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return iso;
  return locale === "en"
    ? dateIn(d, locale, { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" })
    : dateIn(d, locale, { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });
}
