"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useT } from "../../i18n";
import { useChat } from "../../components/ChatProvider";
import PageFrame from "../../components/PageFrame";
import PlanDays from "../../components/PlanDays";
import PlanMap from "../../components/PlanMap";
import { getBrowserSupabase, useSession } from "../../lib/auth";
import type { PlanData } from "../../lib/chat";
import { normalizePlan } from "../../lib/chatState";
import { getLodgings, getTrail, type LodgingOnTrail } from "../../lib/data";
import { mapTrail, type MapTrail } from "../../lib/map";
import { useSearchParams } from "next/navigation";

type Failure = { error: "loadFailed" | "notFound" };
type Loaded = { title: string; createdAt: string; data: PlanData; trail: MapTrail | null; lodgings: LodgingOnTrail[] | null; lengthKm: number | null };

/** A saved multi-day plan (own rows only, RLS) with the trail loaded for the map; the map is optional. */
async function load(id: string): Promise<Loaded | Failure> {
  try {
    const { data, error } = await getBrowserSupabase().from("saved_plans").select("title, kind, payload, created_at").eq("id", id).maybeSingle();
    if (error || !data) return { error: error ? "loadFailed" : "notFound" };
    const p = normalizePlan(data.payload);
    if (data.kind !== "multiday" || !p) return { error: "loadFailed" };
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
    return { error: "loadFailed" };
  }
}

function SavedPlan() {
  const t = useT().plan;
  const id = useSearchParams().get("id");
  const { session, loading } = useSession();
  const signedIn = !!session;
  const [result, setResult] = useState<Loaded | Failure | null>(null);

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
      <h1 className="font-serif text-3xl sm:text-4xl">{t.savedPlan}</h1>
      {!loading && !session && (
        <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          {t.signInToView}
          <Link href="/anmelden" className="underline">
            {t.signIn}
          </Link>
          .
        </p>
      )}
      {result && "error" in result && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {t[result.error]}
        </p>
      )}
      {result && "data" in result && (
        <>
          {result.trail && <PlanMap trail={result.trail} lodgings={result.lodgings} plan={result.data.plan} lengthKm={result.lengthKm} embedded />}
          <PlanDays data={result.data} save={false} title={result.title} planId={id ?? undefined} forecastFrom={result.createdAt} />
        </>
      )}
    </main>
  );
}

type MapData = { trail: MapTrail; lodgings: LodgingOnTrail[] | null; lengthKm: number | null };

/** The plan from the chat (no id): map with the day sections on top, the days below. The map is optional. */
function ChatPlan() {
  const t = useT().plan;
  const { state, hydrated } = useChat();
  const plan = state.plan;
  const trailId = plan?.plan.trail_id;
  const [map, setMap] = useState<MapData | null>(null);

  useEffect(() => {
    setMap(null);
    if (!trailId) return;
    let live = true;
    (async () => {
      const t = await getTrail(trailId);
      if (!t) return null;
      return { trail: mapTrail(t), lengthKm: t.length_km, lodgings: await getLodgings(trailId).catch(() => null) };
    })()
      .catch((e) => {
        console.error(`plan map ${trailId} failed:`, e);
        return null;
      })
      .then((m) => live && setMap(m));
    return () => {
      live = false;
    };
  }, [trailId]);

  if (!hydrated) return null;
  if (!plan) {
    return (
      <main className="flex flex-1 flex-col items-start gap-3">
        <p>{t.noPlanInChat}</p>
        <Link href="/" className="rounded-full bg-papier px-5 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
          {t.toHome}
        </Link>
      </main>
    );
  }
  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      {map && <PlanMap trail={map.trail} lodgings={map.lodgings} plan={plan.plan} lengthKm={map.lengthKm} embedded />}
      <PlanDays data={plan} />
    </main>
  );
}

function PlanView() {
  const t = useT().plan;
  const id = useSearchParams().get("id");
  if (!id) {
    return (
      <PageFrame back={{ href: "/", label: t.backChat }}>
        <ChatPlan />
      </PageFrame>
    );
  }
  return (
    <PageFrame back={{ href: "/meine-plaene", label: t.backPlans }}>
      <SavedPlan />
    </PageFrame>
  );
}

export default function PlanPage() {
  return (
    <Suspense>
      <PlanView />
    </Suspense>
  );
}
