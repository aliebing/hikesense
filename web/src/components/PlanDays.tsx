"use client";

import Link from "next/link";
import type { DayPlan, DayWeather, NoForecast, PlanData, RainVariant } from "../lib/chat";
import { messagesFor, useLocale, useT, type Locale } from "../i18n";
import { dateIn, dayLabel, duration, hm, hmDown, num } from "../lib/format";
import { lodgingKind } from "../lib/map";
import { lodgingLink, numOr } from "../lib/planView";
import MerkenButton from "./MerkenButton";

/** „28.10.2026“ for a timestamp (the day a plan was saved); null when it is no date. */
function savedDate(ts: string | undefined, locale: Locale): string | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : dateIn(d, locale, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });
}

const kmText = (v: number | null | undefined, locale: Locale) => numOr(v, (n) => `${num(n, locale, { max: 1 })} km`, locale);
const clock = (t: string | null) => (t ? t.slice(0, 5) : null);

function dateText(iso: string | null, locale: Locale): string | null {
  if (!iso) return null;
  const label = dayLabel(iso, locale);
  return label === iso && Number.isNaN(new Date(`${iso}T00:00:00Z`).getTime()) ? null : label;
}

/** „Westweg ab Hausach, 3 Tage“ — also the title of the saved plan. */
export function planTitle(data: PlanData, locale: Locale): string {
  const trail = data.labels?.[`trail:${data.plan.trail_id}`] ?? data.plan.trail_name;
  return messagesFor(locale).plan.title(trail, data.start_name ?? null, data.plan.days.length);
}

const isForecast = (w: DayWeather | NoForecast | undefined): w is DayWeather => !!w && !("reason" in w);

/** `asOf`: the date a saved plan's forecast was fetched — it is not today's forecast. */
function Weather({ w, dated, asOf }: { w: DayWeather | NoForecast | undefined; dated: boolean; asOf: string | null }) {
  const { locale } = useLocale();
  const t = useT().plan;
  if (!isForecast(w)) {
    // "not yet" is already what the generic label says; every other reason is added.
    // Saved plans from before the code existed carry only the German text.
    const notYet = w?.code === "not_yet" || (w?.code === undefined && !!w?.reason.startsWith("Noch keine Vorhersage"));
    const reason = w?.reason;
    return (
      <p className="text-xs text-wald-dunkel/80">
        {t.noForecast}
        {reason && !notYet ? ` (${reason})` : ""}
        {!w && !dated && ` (${t.noDate})`}
      </p>
    );
  }
  const n0 = (n: number) => num(n, locale, { max: 0 });
  const temp = `${numOr(w.t_min_c, n0, locale)} / ${numOr(w.t_max_c, n0, locale)} °C`;
  const rain = t.rain(numOr(w.precip_prob_pct, (n) => `${n0(n)}${locale === "en" ? "%" : " %"}`, locale), numOr(w.precip_mm, (n) => `${num(n, locale, { max: 1 })} mm`, locale));
  return (
    <p className="text-xs">
      {asOf && t.forecastFrom(asOf)}
      <span className="font-medium">{w.text ?? t.weather}</span> · {temp} · {rain}
    </p>
  );
}

function Rain({ v }: { v: RainVariant | null }) {
  const { locale } = useLocale();
  const t = useT().plan;
  if (!v) {
    return <p className="text-xs text-wald-dunkel/80">{t.noStop}</p>;
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-medium">{t.rainVariant}</summary>
      <p className="mt-1">
        {t.rainWalk(v.station_name, kmText(v.walk_km, locale), numOr(v.ascent_m, (n) => hm(n, locale), locale), numOr(v.duration_h, (n) => duration(n, locale), locale))}
      </p>
      <p>{v.note}</p>
    </details>
  );
}

function DayCard({ d, from, place, weather, asOf, rain, unterwegsHref }: { d: DayPlan; from: string; place: string; unterwegsHref?: string; weather: DayWeather | NoForecast | undefined; asOf: string | null; rain: RainVariant | null | undefined }) {
  const { locale } = useLocale();
  const t = useT().plan;
  const dur = numOr(d.duration_h, (n) => duration(n, locale), locale);
  const date = dateText(d.date, locale);
  const stop = d.stop;
  const link = stop ? lodgingLink(stop, place, locale) : null;
  const end = stop ? (stop.name ?? lodgingKind(stop.kind, locale)) : t.trailEnd;
  return (
    <li className="flex flex-col gap-1.5 rounded-xl bg-papier/90 p-3 backdrop-blur-sm text-sm text-wald-dunkel shadow">
      <h3 className="font-serif text-base leading-snug">
        {t.day(d.day)}
        {date && ` · ${date}`}
      </h3>
      <p>
        {from} → {end}
      </p>
      <p className="text-xs">
        {kmText(d.length_km, locale)} · {numOr(d.ascent_m, (n) => hm(n, locale), locale)} · {numOr(d.descent_m, (n) => hmDown(n, locale), locale)}
        {d.access_km > 0 && t.access(kmText(d.access_km, locale))}
      </p>
      {d.arrival ? (
        <p className="text-xs">
          {t.timeTimes(dur, clock(d.start_time) ?? "", clock(d.arrival) ?? "")}
        </p>
      ) : (
        <p className="text-xs">{t.timeNoBreaks(dur)}</p>
      )}
      {d.gap && (
        <p role="note" className="rounded-lg border-l-4 border-amber-500 bg-amber-100 px-2 py-1 text-xs font-medium text-amber-950">
          {d.gap}
        </p>
      )}
      {stop && (
        <p className="text-xs">
          {t.lodging}: {stop.name ?? t.unnamed} · {lodgingKind(stop.kind, locale)} · {t.fromTrail(numOr(stop.dist_m, (n) => `${num(n, locale, { max: 0 })} m`, locale))}
          {link && (
            <>
              {" · "}
              <a href={link.href} target="_blank" rel="noopener noreferrer" className="underline">
                {link.label}
              </a>
            </>
          )}
        </p>
      )}
      <Weather w={weather} dated={d.date !== null} asOf={asOf} />
      {rain !== undefined && <Rain v={rain} />}
      {unterwegsHref && (
        <Link href={unterwegsHref} className="self-start text-xs font-medium underline">
          {t.onTheTrail}
        </Link>
      )}
    </li>
  );
}

/**
 * The multi-day plan: notes (trail end, access walks, missing section), one card per day with weather and
 * the rain variant, and „Merken“ (signed-in users only). `save: false` for an already saved plan;
 * its weather is labelled „Vorhersage vom <forecastFrom>“ (the save time), never shown as current.
 */
export default function PlanDays({ data, save = true, title, planId, forecastFrom }: { data: PlanData; save?: boolean; title?: string; /** saved plan id: every day links to „Unterwegs“ */ planId?: string; /** saved plan: created_at */ forecastFrom?: string }) {
  const { locale } = useLocale();
  const t = useT().plan;
  const { plan, weather, rain } = data;
  const startName = data.start_name ?? null;
  const notes = plan.notes ?? [];
  const hasWeather = Object.values(weather ?? {}).some(isForecast);
  const asOf = save ? null : savedDate(forecastFrom, locale);
  return (
    <section aria-label={t.section} className="flex max-w-3xl flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-xl">{title ?? planTitle(data, locale)}</h2>
        {save && plan.days.length > 0 && (
          <MerkenButton kind="multiday" title={planTitle(data, locale)} payload={data} className="[&_button]:bg-papier/90 [&_button]:text-wald-dunkel" />
        )}
      </div>
      {(notes.length > 0 || plan.days.length > 0) && (
        <ul aria-label={t.notes} className="flex flex-col gap-1">
          {notes.map((n, i) => (
            <li key={i} role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-950">
              {n}
            </li>
          ))}
          {plan.days.length > 0 && <li className="text-sm text-papier/90">{t.allTimes}</li>}
        </ul>
      )}
      <ol aria-label={t.days} className="flex flex-col gap-3">
        {plan.days.map((d, i) => (
          <DayCard
            key={d.day}
            d={d}
            from={i === 0 ? (startName ?? `km ${num(d.start_km, locale, { max: 1 })}`) : (plan.days[i - 1].stop?.name ?? `km ${num(d.start_km, locale, { max: 1 })}`)}
            place={startName ?? plan.trail_name}
            weather={weather?.[String(d.day)]}
            asOf={asOf}
            rain={rain?.[String(d.day)]}
            unterwegsHref={planId ? `/unterwegs?plan=${encodeURIComponent(planId)}&day=${d.day}` : undefined}
          />
        ))}
      </ol>
      {hasWeather && (
        <p className="text-[11px] text-papier/80">
          {t.weatherSource}{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" className="underline">
            Open-Meteo.com
          </a>{" "}
          (CC BY 4.0){asOf && t.weatherSaved(asOf)}
        </p>
      )}
    </section>
  );
}
