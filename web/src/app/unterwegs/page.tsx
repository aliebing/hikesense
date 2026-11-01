"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import PageFrame from "../../components/PageFrame";
import Unterwegs from "../../components/Unterwegs";
import { getBrowserSupabase, useSession } from "../../lib/auth";
import { normalizePlan } from "../../lib/chatState";
import type { Profile } from "../../lib/geo";
import { getTrail } from "../../lib/data";
import { daySections, mapTrail, trailLine, type DaySection, type MapTrail } from "../../lib/map";
import type { Position } from "geojson";

const MSG_LOAD = "Die Tour konnte nicht geladen werden";

type Loaded = { title: string; trail: MapTrail; line: Position[]; days?: DaySection[]; profile: Profile | null; startKm: number; lengthKm: number | null };

async function loadTrail(id: string): Promise<Loaded | { error: string }> {
  try {
    const t = await getTrail(id);
    if (!t) return { error: "Tour nicht gefunden" };
    const trail = mapTrail(t);
    return { title: t.name, trail, line: trailLine(trail), profile: t.profile ?? null, startKm: 0, lengthKm: t.length_km };
  } catch {
    return { error: MSG_LOAD };
  }
}

/** One day of a saved multi-day plan: the line is the day's section (the backend's own cut, as on the map). */
async function loadDay(planId: string, dayNo: number): Promise<Loaded | { error: string }> {
  try {
    const { data, error } = await getBrowserSupabase().from("saved_plans").select("title, kind, payload").eq("id", planId).maybeSingle();
    if (error) return { error: "Der Plan konnte nicht geladen werden" };
    if (!data) return { error: "Plan nicht gefunden" };
    const p = normalizePlan(data.payload);
    if (data.kind !== "multiday" || !p) return { error: "Der Plan konnte nicht geladen werden" };
    const day = p.plan.days.find((d) => d.day === dayNo);
    if (!day) return { error: `Der Plan hat keinen Tag ${dayNo}` };
    const t = await getTrail(p.plan.trail_id);
    if (!t) return { error: MSG_LOAD };
    const trail = mapTrail(t);
    const section = daySections(trailLine(trail), p.plan.days, t.length_km).find((x) => x.day === dayNo);
    if (!section) return { error: "Für diesen Tag lässt sich kein Wegabschnitt bestimmen" };
    return {
      title: `${data.title as string} – Tag ${dayNo}`,
      trail,
      line: section.geom.coordinates,
      days: [section],
      profile: t.profile ?? null,
      startKm: Math.min(day.start_km, day.end_km),
      lengthKm: Math.abs(day.end_km - day.start_km) || null,
    };
  } catch {
    return { error: MSG_LOAD };
  }
}

function Content() {
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
  const [result, setResult] = useState<Loaded | { error: string } | null>(null);

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
      <h1 className="font-serif text-3xl sm:text-4xl">Unterwegs</h1>
      {needsLogin && (
        <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          Für einen gemerkten Plan bitte{" "}
          <Link href="/anmelden" className="underline">
            Anmelden
          </Link>
          .
        </p>
      )}
      {badDay && <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">Ungültiger Tag „{rawDay}“ – bitte öffne „Unterwegs“ bei einem Tag des Plans.</p>}
      {!trailId && !planId && <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">Keine Tour ausgewählt – öffne „Unterwegs“ bei einer Tour oder einem gemerkten Plan.</p>}
      {result && "error" in result && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {result.error}
        </p>
      )}
      {result && "line" in result && <Unterwegs key={`${planId ?? trailId}-${dayNo}`} {...result} />}
    </main>
  );
}

export default function UnterwegsPage() {
  return (
    <PageFrame back={{ href: "/", label: "← Zur Startseite" }}>
      <Suspense>
        <Content />
      </Suspense>
    </PageFrame>
  );
}
