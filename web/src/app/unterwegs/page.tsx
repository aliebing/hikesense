"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { useT } from "../../i18n";
import PageFrame from "../../components/PageFrame";
import Unterwegs from "../../components/Unterwegs";
import { getBrowserSupabase, useSession } from "../../lib/auth";
import { normalizePlan } from "../../lib/chatState";
import type { Profile } from "../../lib/geo";
import { getTrail } from "../../lib/data";
import { daySections, mapTrail, trailLine, type DaySection, type MapTrail } from "../../lib/map";
import type { Position } from "geojson";

/** Errors are codes; the text is chosen at render so a language switch needs no reload. */
type Failure = { error: "loadFailed" | "notFound" | "uwTourLoadFailed" | "uwTourNotFound" | "uwNoSection" | "uwNoDay"; day?: number };

/** `dayNo`: set for one plan day, whose title is built at render ("<plan> – day n"). */
type Loaded = { dayNo?: number; title: string; trail: MapTrail; line: Position[]; days?: DaySection[]; profile: Profile | null; startKm: number; lengthKm: number | null };

async function loadTrail(id: string): Promise<Loaded | Failure> {
  try {
    const t = await getTrail(id);
    if (!t) return { error: "uwTourNotFound" };
    const trail = mapTrail(t);
    return { title: t.name, trail, line: trailLine(trail), profile: t.profile ?? null, startKm: 0, lengthKm: t.length_km };
  } catch {
    return { error: "uwTourLoadFailed" };
  }
}

/** One day of a saved multi-day plan: the line is the day's section (the backend's own cut, as on the map). */
async function loadDay(planId: string, dayNo: number): Promise<Loaded | Failure> {
  try {
    const { data, error } = await getBrowserSupabase().from("saved_plans").select("title, kind, payload").eq("id", planId).maybeSingle();
    if (error) return { error: "loadFailed" };
    if (!data) return { error: "notFound" };
    const p = normalizePlan(data.payload);
    if (data.kind !== "multiday" || !p) return { error: "loadFailed" };
    const day = p.plan.days.find((d) => d.day === dayNo);
    if (!day) return { error: "uwNoDay", day: dayNo };
    const t = await getTrail(p.plan.trail_id);
    if (!t) return { error: "uwTourLoadFailed" };
    const trail = mapTrail(t);
    const section = daySections(trailLine(trail), p.plan.days, t.length_km).find((x) => x.day === dayNo);
    if (!section) return { error: "uwNoSection" };
    return {
      dayNo,
      title: data.title as string,
      trail,
      line: section.geom.coordinates,
      days: [section],
      profile: t.profile ?? null,
      startKm: Math.min(day.start_km, day.end_km),
      lengthKm: Math.abs(day.end_km - day.start_km) || null,
    };
  } catch {
    return { error: "uwTourLoadFailed" };
  }
}

function Content() {
  const t = useT().plan;
  const params = useSearchParams();
  const trailId = params.get("trail");
  const planId = params.get("plan");
  const rawDay = params.get("day");
  // no day = day 1; anything else must be a whole number >= 1
  const dayNo = rawDay === null ? 1 : /^\d+$/.test(rawDay) ? Number(rawDay) : 0;
  const badDay = !!planId && dayNo < 1;
  const { session, loading } = useSession();
  const needsLogin = !!planId && !loading && !session;
  const ready = (!!trailId && !planId) || (!!planId && !!session && !badDay);
  const [result, setResult] = useState<Loaded | Failure | null>(null);

  useEffect(() => {
    setResult(null);
    if (!ready) return;
    let live = true;
    const p = planId ? loadDay(planId, dayNo) : loadTrail(trailId!);
    void p.then((r) => live && setResult(r));
    return () => {
      live = false;
    };
  }, [ready, planId, trailId, dayNo]);

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <h1 className="font-serif text-3xl sm:text-4xl">{t.uwTitle}</h1>
      {needsLogin && (
        <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          {t.uwSignInForPlan}
          <Link href="/anmelden" className="underline">
            {t.signIn}
          </Link>
          .
        </p>
      )}
      {badDay && <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">{t.uwBadDay(rawDay ?? "")}</p>}
      {!trailId && !planId && <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{t.uwNoTour}</p>}
      {result && "error" in result && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {result.error === "uwNoDay" ? t.uwNoDay(result.day ?? 0) : t[result.error]}
        </p>
      )}
      {result && "line" in result && <Unterwegs key={`${planId ?? trailId}-${dayNo}`} {...result} title={result.dayNo ? t.uwDay(result.title, result.dayNo) : result.title} />}
    </main>
  );
}

export default function UnterwegsPage() {
  const t = useT();
  return (
    <PageFrame back={{ href: "/", label: t.tour.backHome }}>
      <Suspense>
        <Content />
      </Suspense>
    </PageFrame>
  );
}
