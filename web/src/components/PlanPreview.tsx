"use client";

import Link from "next/link";
import { useLocale, useT } from "../i18n";
import { num } from "../lib/format";
import type { PlanData } from "../lib/chat";
import { lodgingKind } from "../lib/map";
import { numOr } from "../lib/planView";
import { planTitle } from "./PlanDays";

/** The chat's multi-day plan on the home page: one small tile per day and the way to the plan with its map. */
export default function PlanPreview({ data }: { data: PlanData }) {
  const { locale } = useLocale();
  const t = useT().plan;
  const n1 = (n: number) => num(n, locale, { max: 1 });
  const days = data.plan.days;
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-serif text-2xl sm:text-3xl">{planTitle(data, locale)}</h2>
      {days.length === 0 ? (
        <p role="note" className="max-w-2xl rounded-xl border-l-4 border-amber-500 bg-amber-100 px-4 py-3 text-sm font-medium text-amber-950">
          {data.plan.notes.join(" ") || t.noPlan}
        </p>
      ) : (
        <>
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {days.map((d) => (
              <li key={d.day} className="flex flex-col gap-1 rounded-xl bg-papier p-3 text-sm text-wald-dunkel">
                <span className="font-serif text-lg">{t.day(d.day)}</span>
                <span className="tabular-nums">
                  km {n1(d.start_km)}–{n1(d.end_km)} · {numOr(d.length_km, (n) => `${n1(n)} km`, locale)}
                </span>
                <span className="text-wald-dunkel/80">{d.stop ? `🛏 ${d.stop.name ?? lodgingKind(d.stop.kind, locale)}` : t.noLodgingAtEnd}</span>
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
