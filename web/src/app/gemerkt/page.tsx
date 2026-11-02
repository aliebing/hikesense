"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { stripFallback } from "../../components/ChatMessages";
import ChatText from "../../components/ChatText";
import PageFrame from "../../components/PageFrame";
import TourPreview from "../../components/TourPreview";
import TourResultCard from "../../components/TourResultCard";
import { getBrowserSupabase, useSession } from "../../lib/auth";
import type { Labels, TourCard } from "../../lib/chat";
import { isSavedSearch } from "../../lib/plans";

const MSG_LOAD = "Die gemerkte Suche konnte nicht geladen werden";
const MSG_BAD = "Diese gemerkte Suche lässt sich nicht anzeigen.";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MSG_GONE = "Diese gemerkte Suche gibt es nicht (mehr).";
const date = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "Europe/Berlin" });

type Loaded = { createdAt: string; messages: string[]; answer: string; cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels };

const isObj = (x: unknown): x is Record<string, unknown> => typeof x === "object" && x !== null;
const strings = (x: unknown): string[] => (Array.isArray(x) ? x.filter((v): v is string => typeof v === "string") : []);

/** A card the tile can render without crashing. */
function usableCard(c: unknown): c is TourCard {
  if (!isObj(c) || typeof c.trail_id !== "string" || typeof c.name !== "string" || !Array.isArray(c.results) || !isObj(c.preference)) return false;
  return Array.isArray(c.preference.met) && Array.isArray(c.preference.missing) && Array.isArray(c.preference.avoided_hit);
}

async function load(id: string): Promise<Loaded | { error: string }> {
  if (!UUID.test(id)) return { error: MSG_GONE };
  try {
    const { data, error } = await getBrowserSupabase().from("saved_plans").select("title, kind, payload, created_at").eq("id", id).maybeSingle();
    if (error) return { error: MSG_LOAD };
    if (!data) return { error: MSG_GONE };
    if (data.kind !== "search" || !isSavedSearch(data.payload)) return { error: MSG_BAD };
    const p = data.payload;
    const r = p.results as unknown as Record<string, unknown>;
    return {
      createdAt: data.created_at as string,
      messages: strings(p.messages),
      answer: typeof p.answer === "string" ? p.answer : "",
      cards: (r.cards as unknown[]).filter(usableCard),
      fallback: typeof r.fallback === "string" && r.fallback ? r.fallback : null,
      runWithoutPace: r.runWithoutPace === true,
      labels: isObj(r.labels) ? (r.labels as Labels) : {},
    };
  } catch {
    return { error: MSG_LOAD };
  }
}

function Saved() {
  const id = useSearchParams().get("id");
  const { session, loading } = useSession();
  const signedIn = !!session;
  const [result, setResult] = useState<Loaded | { error: string } | null>(null);

  useEffect(() => {
    setResult(null); // another search or no session: never show the previous one
    if (!signedIn || !id) return;
    let live = true;
    void load(id).then((r) => live && setResult(r));
    return () => {
      live = false;
    };
  }, [signedIn, id]);

  // the note above the tiles already says it, so the answer text leaves out its first sentence
  const answer = result && "answer" in result ? (result.fallback ? stripFallback(result.answer, result.fallback) : result.answer) : "";

  return (
    <main className="flex flex-1 flex-col gap-5 pb-4">
      <h1 className="font-serif text-3xl sm:text-4xl">Gemerkte Suche</h1>
      {!loading && !session && (
        <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          Zum Ansehen deiner Suche bitte{" "}
          <Link href="/anmelden" className="underline">
            Anmelden
          </Link>
          .
        </p>
      )}
      {!loading && session && !id && <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{MSG_GONE}</p>}
      {signedIn && result && "error" in result && (
        <p role="alert" className="max-w-xl rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {result.error}
        </p>
      )}
      {signedIn && result && "cards" in result && (
        <>
          {!Number.isNaN(new Date(result.createdAt).getTime()) && (
            <p className="schrift-feld text-sm text-papier">Gemerkt am {date.format(new Date(result.createdAt))}</p>
          )}
          {result.messages.length > 0 && (
            <div className="flex max-w-xl flex-col gap-2">
              {result.messages.map((m, i) => (
                <blockquote key={i} className="rounded-xl rounded-tr-sm bg-wald px-3 py-2 text-sm text-papier">
                  {m}
                </blockquote>
              ))}
            </div>
          )}
          {answer && (
            <p className="max-w-xl whitespace-pre-wrap rounded-xl rounded-tl-sm bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
              <ChatText text={answer} />
            </p>
          )}
          {result.fallback && (
            <p role="note" className="max-w-2xl rounded-xl border-l-4 border-amber-500 bg-amber-100 px-4 py-3 text-sm font-medium text-amber-950">
              {result.fallback}
            </p>
          )}
          {result.cards.length === 0 ? (
            <p className="max-w-xl rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">Diese gemerkte Suche enthält keine Touren.</p>
          ) : result.cards.length === 1 ? (
            <TourPreview card={result.cards[0]} runWithoutPace={result.runWithoutPace} labels={result.labels} fallback={!!result.fallback} />
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {result.cards.map((c) => (
                <TourResultCard key={c.trail_id} card={c} runWithoutPace={result.runWithoutPace} labels={result.labels} size="large" />
              ))}
            </div>
          )}
        </>
      )}
    </main>
  );
}

export default function GemerktPage() {
  return (
    <Suspense>
      <PageFrame back={{ href: "/meine-plaene", label: "← Meine Pläne" }}>
        <Saved />
      </PageFrame>
    </Suspense>
  );
}
