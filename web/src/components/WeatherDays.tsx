"use client";

import { useLocale, useT } from "../i18n";
import { dateIn, num } from "../lib/format";
import { numOr } from "../lib/planView";
import type { WeatherDaysData } from "../lib/chat";

function dayText(iso: string, locale: "de" | "en"): string {
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? iso : dateIn(d, locale, { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });
}

/**
 * The weather day finder: the days that fit a weather wish at a place (or, with `best_only`, the closest ones),
 * each with weekday and date, weather word, temperature, rain and snow. Match: green check mark; no match: dimmed;
 * unknown: „?“. The words come from the backend in the reply language.
 */
export default function WeatherDays({ data }: { data: WeatherDaysData }) {
  const { locale } = useLocale();
  const t = useT().weather;
  if (data.days.length === 0 && !data.note) return null;
  const wish = t.wishes[data.wish] ?? data.wish;
  const n0 = (n: number) => num(n, locale, { max: 0 });
  const pct = (n: number) => `${n0(n)}${locale === "en" ? "%" : " %"}`;
  const cm = (n: number) => `${num(n, locale, { max: 1 })} cm`;
  return (
    <section aria-label={t.finder} className="flex flex-col gap-1 rounded-xl bg-papier/95 px-3 py-2 text-sm text-wald-dunkel">
      <h3 className="font-medium">{t.heading(wish, data.place)}</h3>
      {data.best_only && <p className="text-xs">{t.bestOnly(wish)}</p>}
      {data.days.length > 0 && (
        <ul aria-label={t.title} className="flex flex-col gap-0.5">
          {data.days.map((d) => {
            const w = d.weather;
            const snow = typeof w.snowfall_cm === "number" && w.snowfall_cm > 0 ? ` · ${t.snow(cm(w.snowfall_cm))}` : "";
            const temp = `${numOr(w.t_min_c, n0, locale)} / ${numOr(w.t_max_c, n0, locale)} °C`;
            const rain = t.rain(numOr(w.precip_prob_pct, pct, locale), numOr(w.precip_mm, (n) => `${num(n, locale, { max: 1 })} mm`, locale));
            return (
              <li key={d.date} className={`flex flex-wrap items-baseline gap-x-2 ${d.match === false ? "opacity-60" : ""}`}>
                <span className="font-medium">{dayText(d.date, locale)}</span>
                <span className="text-xs">
                  {w.text ?? t.title} · {temp} · {rain}
                  {snow}
                </span>
                {d.match === true && <span className="text-xs font-semibold text-green-800">{t.fitsMark}</span>}
                {d.match === null && (
                  <span className="text-xs" title={t.unknownFit} aria-label={t.unknownFit}>
                    ?
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}
      {data.note && <p className="text-xs">{data.note}</p>}
      <p className="text-[11px] text-wald-dunkel/70">
        {t.source}{" "}
        <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" className="underline">
          Open-Meteo.com
        </a>{" "}
        (CC BY 4.0)
      </p>
    </section>
  );
}
