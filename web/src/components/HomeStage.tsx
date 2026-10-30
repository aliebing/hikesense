"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { TrailSummary } from "../lib/data";
import ChatShell from "./ChatShell";
import { useChat } from "./ChatProvider";
import CreditsOverlay from "./CreditsOverlay";
import TileRows, { layoutTiles, useNarrow } from "./TileRows";

const NO_MATCHES: never[] = [];

/** Home content: title, chat on the left, drifting tiles on the right, suggestions button and credits. */
export default function HomeStage({ pool }: { pool: TrailSummary[] }) {
  const { state } = useChat();
  const narrow = useNarrow();
  const [credits, setCredits] = useState(false);
  const matches = state.last?.cards ?? NO_MATCHES;

  // exactly the photos of the tiles currently shown, once each
  const photos = useMemo(
    () =>
      layoutTiles(pool, matches, narrow)
        .flat()
        .flatMap((t) => (t.photo ? [t.photo] : []))
        .filter((p, i, all) => all.findIndex((q) => q.url === p.url) === i),
    [pool, matches, narrow],
  );

  return (
    <>
      <section className="max-w-2xl pt-4 sm:pt-8">
        <h1 className="font-serif text-4xl leading-tight drop-shadow-md sm:text-6xl">Wandern im Schwarzwald</h1>
        <p className="mt-3 max-w-lg text-base text-papier/90 drop-shadow sm:text-lg">
          Westweg-Etappen und Tagestouren mit echten Strecken, Höhenmetern und Gehzeiten – im Gespräch geplant.
        </p>
      </section>

      <div className="grid flex-1 content-start gap-6 md:grid-cols-[minmax(0,40fr)_minmax(0,55fr)] md:items-center">
        <ChatShell intro="Hallo! Beschreibe deine Tagestour – zum Beispiel „Rundweg ab Hinterzarten, 10 bis 15 km, wenig Höhenmeter, mit Aussicht“." />
        <div className="grid min-w-0 gap-4">
          <TileRows pool={pool} matches={matches} />
          <div className="flex flex-wrap items-center justify-end gap-3">
            {state.last && state.last.cards.length > 0 && (
              <Link href="/vorschlaege" className="rounded-full bg-papier px-5 py-2 text-sm font-medium text-wald-dunkel shadow-lg hover:bg-white">
                Vorschläge zeigen →
              </Link>
            )}
            <button
              type="button"
              onClick={() => setCredits(true)}
              className="rounded-full border border-papier/50 px-4 py-2 text-sm text-papier hover:bg-papier/10"
            >
              Bildnachweise
            </button>
          </div>
        </div>
      </div>

      {credits && <CreditsOverlay photos={photos} onClose={() => setCredits(false)} />}
    </>
  );
}
