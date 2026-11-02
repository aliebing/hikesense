"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import PageFrame from "../../components/PageFrame";
import { useSession } from "../../lib/auth";
import { deletePlan, isSavedSearch, listPlans, type SavedPlan } from "../../lib/plans";

const KIND: Record<SavedPlan["kind"], string> = { day_hike: "Tageswanderung", multiday: "Mehrtagestour", search: "Suche" };
const date = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });

/** day_hike → its trail page; multiday → the saved plan view (/plan, built with the multi-day plan). */
function hrefOf(p: SavedPlan): string | null {
  if (p.kind === "multiday") return `/plan?id=${encodeURIComponent(p.id)}`;
  const id = (p.payload as { trail_id?: unknown } | null)?.trail_id;
  return typeof id === "string" ? `/t/${id}` : null;
}

function hrefFor(p: SavedPlan): string | null {
  return p.kind === "search" ? `/gemerkt?id=${encodeURIComponent(p.id)}` : hrefOf(p);
}

function detail(p: SavedPlan): string {
  let s = `${KIND[p.kind]} · ${date.format(new Date(p.created_at))}`;
  if (p.kind === "search" && isSavedSearch(p.payload)) {
    const n = p.payload.results.cards.length;
    s += ` · ${n} ${n === 1 ? "Tour" : "Touren"}`;
  }
  return s;
}

function Section({ title, plans, onRemove }: { title: string; plans: SavedPlan[]; onRemove: (id: string) => Promise<void> }) {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="schrift-feld font-serif text-xl text-papier">{title}</h2>
      <ul className="flex flex-col gap-2">
        {plans.map((p) => {
          const href = hrefFor(p);
          return (
            <li key={p.id} className="flex items-center justify-between gap-3 rounded-xl bg-papier/95 p-3 text-sm text-wald-dunkel shadow">
              <div className="flex flex-col gap-0.5">
                <h3 className="font-serif text-base leading-snug">
                  {href ? (
                    <Link href={href} className="underline-offset-2 hover:underline">
                      {p.title}
                    </Link>
                  ) : (
                    p.title
                  )}
                </h3>
                <p className="text-xs text-wald-dunkel/80">{detail(p)}</p>
              </div>
              <button
                type="button"
                onClick={() => void onRemove(p.id)}
                aria-label={`Löschen: ${p.title}`}
                className="rounded-full border border-wald-dunkel/30 px-3 py-1 text-xs hover:bg-wald-dunkel/10"
              >
                Löschen
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

/** The signed-in user's saved plans. */
export default function MeinePlaene() {
  const { session, loading } = useSession();
  const [plans, setPlans] = useState<SavedPlan[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const signedIn = !!session;

  useEffect(() => {
    if (!signedIn) {
      // signed out (shared device): never keep showing the previous user's plans
      setPlans(null);
      setError(null);
      return;
    }
    let live = true;
    void listPlans().then((r) => {
      if (!live) return;
      setPlans(r.plans);
      setError(r.error);
    });
    return () => {
      live = false;
    };
  }, [signedIn]);

  const remove = async (id: string) => {
    const r = await deletePlan(id);
    if (r.error) setError(r.error);
    else {
      setError(null);
      setPlans((ps) => (ps ?? []).filter((p) => p.id !== id));
    }
  };

  const searches = (plans ?? []).filter((p) => p.kind === "search");
  const others = (plans ?? []).filter((p) => p.kind !== "search");

  return (
    <PageFrame back={{ href: "/", label: "← Zum Chat" }}>
      <main className="flex flex-1 flex-col items-center gap-5 pb-4">
        <h1 className="font-serif text-3xl sm:text-4xl">Meine Pläne</h1>
        <div className="flex w-full max-w-xl flex-col gap-3">
          {!loading && !session && (
            <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
              Zum Ansehen deiner Pläne bitte{" "}
              <Link href="/anmelden" className="underline">
                Anmelden
              </Link>
              .
            </p>
          )}
          {error && (
            <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
              {error}
            </p>
          )}
          {plans && plans.length === 0 && !error && (
            <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">Du hast noch keine Pläne gemerkt.</p>
          )}
          {searches.length > 0 && <Section title="Gemerkte Suchen" plans={searches} onRemove={remove} />}
          {others.length > 0 && <Section title="Touren und Pläne" plans={others} onRemove={remove} />}
        </div>
      </main>
    </PageFrame>
  );
}
