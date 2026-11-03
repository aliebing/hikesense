"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useLocale, useT } from "../i18n";
import { num } from "../lib/format";
import type { PlanData } from "../lib/chat";
import { getTrail, type Photo } from "../lib/data";
import { lodgingKind } from "../lib/map";
import { dayPhotos, numOr } from "../lib/planView";
import Attribution from "./Attribution";
import { planTitle } from "./PlanDays";

/** The chat's multi-day plan on the home page: one small tile per day and the way to the plan with its map. */
export default function PlanPreview({ data }: { data: PlanData }) {
  const { locale } = useLocale();
  const t = useT().plan;
  const n1 = (n: number) => num(n, locale, { max: 1 });
  const days = data.plan.days;
  // one photo per day from the stage it walks (loaded after the plan; without it the tiles stay text)
  const [photos, setPhotos] = useState<(Photo | null)[]>([]);
  const trailId = data.plan.trail_id;
  useEffect(() => {
    let live = true;
    getTrail(trailId)
      .then((trail) => live && trail && setPhotos(dayPhotos(days, trail.stages)))
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [trailId, days]);
  return (
    <section className="flex flex-col gap-4">
      <h2 className="schrift-feld font-serif text-2xl sm:text-3xl">{planTitle(data, locale)}</h2>
      {days.length === 0 ? (
        <p role="note" className="max-w-2xl rounded-xl border-l-4 border-amber-500 bg-amber-100 px-4 py-3 text-sm font-medium text-amber-950">
          {data.plan.notes.join(" ") || t.noPlan}
        </p>
      ) : (
        <>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {days.map((d, i) => (
              <li key={d.day} className="flex flex-col gap-1 rounded-md bg-papier p-3 text-sm text-tinte">
                {photos[i] && (
                  <div className="flex flex-col gap-0.5">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={photos[i]!.thumb_url} alt="" loading="lazy" className="h-28 w-full rounded-sm object-cover" />
                    <Attribution photo={photos[i]!} className="text-tinte/70" />
                  </div>
                )}
                <span className="font-serif text-lg">{t.day(d.day)}</span>
                <span className="tabular-nums">
                  km {n1(d.start_km)}–{n1(d.end_km)} · {numOr(d.length_km, (n) => `${n1(n)} km`, locale)}
                </span>
                <span className="text-tinte/80">{d.stop ? `🛏 ${d.stop.name ?? lodgingKind(d.stop.kind, locale)}` : t.noLodgingAtEnd}</span>
              </li>
            ))}
          </ul>
          <Link href="/plan" className="self-start rounded-full bg-papier px-5 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
            {t.viewPlan}
          </Link>
        </>
      )}
    </section>
  );
}
