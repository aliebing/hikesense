"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import PageFrame from "../../components/PageFrame";
import PlanDays from "../../components/PlanDays";
import PlanMap from "../../components/PlanMap";
import { getBrowserSupabase, useSession } from "../../lib/auth";
import type { PlanData } from "../../lib/chat";
import { normalizePlan } from "../../lib/chatState";
import { getLodgings, getTrail, type LodgingOnTrail } from "../../lib/data";
import { mapTrail, type MapTrail } from "../../lib/map";
import { useSearchParams } from "next/navigation";

const MSG_LOAD = "Der Plan konnte nicht geladen werden";

type Loaded = { title: string; createdAt: string; data: PlanData; trail: MapTrail | null; lodgings: LodgingOnTrail[] | null; lengthKm: number | null };

/** A saved multi-day plan (own rows only, RLS) with the trail loaded for the map; the map is optional. */
async function load(id: string): Promise<Loaded | { error: string }> {
  try {
    const { data, error } = await getBrowserSupabase().from("saved_plans").select("title, kind, payload, created_at").eq("id", id).maybeSingle();
    if (error || !data) return { error: error ? MSG_LOAD : "Plan nicht gefunden" };
    const p = normalizePlan(data.payload);
    if (data.kind !== "multiday" || !p) return { error: MSG_LOAD };
    const data2 = p;
    let trail: MapTrail | null = null;
    let lodgings: LodgingOnTrail[] | null = null;
    let lengthKm: number | null = null;
    try {
      const t = await getTrail(p.plan.trail_id);
      if (t) {
        trail = mapTrail(t);
        lengthKm = t.length_km;
        lodgings = await getLodgings(p.plan.trail_id).catch(() => null);
      }
    } catch {
      // no map without the trail; the days are still shown
    }
    return { title: data.title as string, createdAt: data.created_at as string, data: data2, trail, lodgings, lengthKm };
  } catch {
    return { error: MSG_LOAD };
  }
}

function SavedPlan() {
  const id = useSearchParams().get("id");
  const { session, loading } = useSession();
  const signedIn = !!session;
  const [result, setResult] = useState<Loaded | { error: string } | null>(null);

  useEffect(() => {
    setResult(null); // another plan or no session: never show the previous one
    if (!signedIn || !id) return;
    let live = true;
    void load(id).then((r) => live && setResult(r));
    return () => {
      live = false;
    };
  }, [signedIn, id]);

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <h1 className="font-serif text-3xl sm:text-4xl">Gemerkter Plan</h1>
      {!loading && !session && (
        <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          Zum Ansehen deines Plans bitte{" "}
          <Link href="/anmelden" className="underline">
            Anmelden
          </Link>
          .
        </p>
      )}
      {signedIn && !id && <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">Kein Plan ausgewählt.</p>}
      {result && "error" in result && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {result.error}
        </p>
      )}
      {result && "data" in result && (
        <>
          <PlanDays data={result.data} save={false} title={result.title} planId={id ?? undefined} forecastFrom={result.createdAt} />
          {result.trail && <PlanMap trail={result.trail} lodgings={result.lodgings} plan={result.data.plan} lengthKm={result.lengthKm} />}
        </>
      )}
    </main>
  );
}

export default function PlanPage() {
  return (
    <PageFrame back={{ href: "/meine-plaene", label: "← Meine Pläne" }}>
      <Suspense>
        <SavedPlan />
      </Suspense>
    </PageFrame>
  );
}
