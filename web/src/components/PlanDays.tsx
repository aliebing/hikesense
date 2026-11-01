"use client";

import Link from "next/link";
import type { DayPlan, DayWeather, NoForecast, PlanData, RainVariant } from "../lib/chat";
import { duration, hm, hmDown } from "../lib/format";
import { lodgingKind } from "../lib/map";
import { lodgingLink, numOr } from "../lib/planView";
import MerkenButton from "./MerkenButton";

const de1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });
const de0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" });

const savedFmt = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });

/** „28.10.2026“ for a timestamp (the day a plan was saved); null when it is no date. */
function savedDate(ts: string | undefined): string | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : savedFmt.format(d);
}

const kmText = (v: number | null | undefined) => numOr(v, (n) => `${de1.format(n)} km`);
const clock = (t: string | null) => (t ? t.slice(0, 5) : null);

function dateText(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(`${iso}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : dateFmt.format(d);
}

/** „Westweg ab Hausach, 3 Tage“ — also the title of the saved plan. */
export function planTitle(data: PlanData): string {
  const startName = data.start_name;
  const n = data.plan.days.length;
  const trail = data.labels?.[`trail:${data.plan.trail_id}`] ?? data.plan.trail_name;
  return `${trail}${startName ? ` ab ${startName}` : ""}, ${n} ${n === 1 ? "Tag" : "Tage"}`;
}

const isForecast = (w: DayWeather | NoForecast | undefined): w is DayWeather => !!w && !("reason" in w);

/** `asOf`: the date a saved plan's forecast was fetched — it is not today's forecast. */
function Weather({ w, dated, asOf }: { w: DayWeather | NoForecast | undefined; dated: boolean; asOf: string | null }) {
  if (!isForecast(w)) {
    const reason = w?.reason;
    return (
      <p className="text-xs text-wald-dunkel/80">
        Noch keine Vorhersage{reason && !reason.startsWith("Noch keine Vorhersage") ? ` (${reason})` : ""}
        {!w && !dated && " (ohne Datum)"}
      </p>
    );
  }
  const temp = `${numOr(w.t_min_c, (n) => de0.format(n))} / ${numOr(w.t_max_c, (n) => de0.format(n))} °C`;
  const rain = `Regen ${numOr(w.precip_prob_pct, (n) => `${de0.format(n)} %`)} / ${numOr(w.precip_mm, (n) => `${de1.format(n)} mm`)}`;
  return (
    <p className="text-xs">
      {asOf && `Vorhersage vom ${asOf}: `}
      <span className="font-medium">{w.text ?? "Wetter"}</span> · {temp} · {rain}
    </p>
  );
}

function Rain({ v }: { v: RainVariant | null }) {
  if (!v) {
    return <p className="text-xs text-wald-dunkel/80">Keine Haltestelle am Weg – Regenvariante nicht möglich</p>;
  }
  return (
    <details className="text-xs">
      <summary className="cursor-pointer font-medium">Regenvariante</summary>
      <p className="mt-1">
        Bis zur Haltestelle {v.station_name}: {kmText(v.walk_km)}, {numOr(v.ascent_m, (n) => hm(n))},{" "}
        {numOr(v.duration_h, duration)} (ohne Pausen).
      </p>
      <p>{v.note}</p>
    </details>
  );
}

function DayCard({ d, from, weather, asOf, rain, unterwegsHref }: { d: DayPlan; from: string; unterwegsHref?: string; weather: DayWeather | NoForecast | undefined; asOf: string | null; rain: RainVariant | null | undefined }) {
  const date = dateText(d.date);
  const stop = d.stop;
  const link = stop ? lodgingLink(stop) : null;
  const end = stop ? (stop.name ?? lodgingKind(stop.kind)) : "Wegende";
  return (
    <li className="flex flex-col gap-1.5 rounded-xl bg-papier/95 p-3 text-sm text-wald-dunkel shadow">
      <h3 className="font-serif text-base leading-snug">
        Tag {d.day}
        {date && ` · ${date}`}
      </h3>
      <p>
        {from} → {end}
      </p>
      <p className="text-xs">
        {kmText(d.length_km)} · {numOr(d.ascent_m, (n) => hm(n))} · {numOr(d.descent_m, (n) => hmDown(n))}
        {d.access_km > 0 && ` · davon ${kmText(d.access_km)} Zuweg zur Unterkunft (Luftlinie, ohne Höhenmeter des Zuwegs)`}
      </p>
      {d.arrival ? (
        <p className="text-xs">
          Zeit {numOr(d.duration_h, duration)}, Start {clock(d.start_time)} Uhr, Ankunft {clock(d.arrival)} Uhr (ohne Pausen)
        </p>
      ) : (
        <p className="text-xs">Zeit {numOr(d.duration_h, duration)} (ohne Pausen)</p>
      )}
      {d.gap && (
        <p role="note" className="rounded-lg border-l-4 border-amber-500 bg-amber-100 px-2 py-1 text-xs font-medium text-amber-950">
          {d.gap}
        </p>
      )}
      {stop && (
        <p className="text-xs">
          Unterkunft: {stop.name ?? "ohne Namen"} · {lodgingKind(stop.kind)} · {numOr(stop.dist_m, (n) => `${de0.format(n)} m`)} vom Weg
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
          Unterwegs
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
export default function PlanDays({ data, save = true, title, mapHref, planId, forecastFrom }: { data: PlanData; save?: boolean; title?: string; mapHref?: string; /** saved plan id: every day links to „Unterwegs“ */ planId?: string; /** saved plan: created_at */ forecastFrom?: string }) {
  const { plan, weather, rain } = data;
  const startName = data.start_name ?? null;
  const notes = plan.notes ?? [];
  const hasWeather = Object.values(weather ?? {}).some(isForecast);
  const asOf = save ? null : savedDate(forecastFrom);
  return (
    <section aria-label="Mehrtagesplan" className="flex max-w-3xl flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-serif text-xl">{title ?? planTitle(data)}</h2>
        {save && plan.days.length > 0 && (
          <MerkenButton kind="multiday" title={planTitle(data)} payload={data} className="[&_button]:bg-papier/90 [&_button]:text-wald-dunkel" />
        )}
      </div>
      {mapHref && plan.days.length > 0 && (
        <Link href={mapHref} className="self-start rounded-full bg-papier/90 px-4 py-1.5 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
          Karte mit Tagesabschnitten
        </Link>
      )}
      {(notes.length > 0 || plan.days.length > 0) && (
        <ul aria-label="Hinweise" className="flex flex-col gap-1">
          {notes.map((n, i) => (
            <li key={i} role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-950">
              {n}
            </li>
          ))}
          {plan.days.length > 0 && <li className="text-sm text-papier/90">Alle Zeiten ohne Pausen (Gehzeit nach DIN 33466)</li>}
        </ul>
      )}
      <ol aria-label="Tage" className="flex flex-col gap-3">
        {plan.days.map((d, i) => (
          <DayCard
            key={d.day}
            d={d}
            from={i === 0 ? (startName ?? `km ${de1.format(d.start_km)}`) : (plan.days[i - 1].stop?.name ?? `km ${de1.format(d.start_km)}`)}
            weather={weather?.[String(d.day)]}
            asOf={asOf}
            rain={rain?.[String(d.day)]}
            unterwegsHref={planId ? `/unterwegs?plan=${encodeURIComponent(planId)}&day=${d.day}` : undefined}
          />
        ))}
      </ol>
      {hasWeather && (
        <p className="text-[11px] text-papier/80">
          Wetter:{" "}
          <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer" className="underline">
            Open-Meteo.com
          </a>{" "}
          (CC BY 4.0){asOf && ` · Vorhersage vom ${asOf}, beim Merken abgerufen – nicht aktuell`}
        </p>
      )}
    </section>
  );
}
