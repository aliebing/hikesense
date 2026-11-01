"use client";

import type { Photo } from "../lib/data";
import ChatShell from "./ChatShell";
import { useChat } from "./ChatProvider";
import PhotoSwitcher from "./PhotoSwitcher";
import ResultsPane from "./ResultsPane";

const INTRO = "Hallo! Beschreibe deine Tagestour – zum Beispiel „Rundweg ab Hinterzarten, 10 bis 15 km, wenig Höhenmeter, mit Aussicht“.";

/**
 * Home content. Before any result: title, chat and a bounded photo (never text on it).
 * After a search or plan: chat on the left, the tiles (or the one tour, or the plan) on the right.
 */
export default function HomeStage({ photos }: { photos: Photo[] }) {
  const { state, hydrated } = useChat();
  const hasResults = hydrated && ((state.last && state.last.cards.length > 0) || !!state.plan);

  if (hasResults) {
    return (
      <div className="grid flex-1 items-start gap-6 md:grid-cols-[24rem_1fr]">
        <div className="flex flex-col gap-3 md:sticky md:top-4">
          <h1 className="font-serif text-2xl">Wandern im Schwarzwald</h1>
          <ChatShell intro={INTRO} />
        </div>
        <div className="min-w-0">
          <ResultsPane />
        </div>
      </div>
    );
  }

  return (
    <div className="grid flex-1 items-center gap-8 py-4 md:grid-cols-2 sm:py-8">
      <div className="flex flex-col gap-6">
        <section>
          <h1 className="font-serif text-4xl leading-tight sm:text-6xl">Wandern im Schwarzwald</h1>
          <p className="mt-3 max-w-lg text-base text-papier/90 sm:text-lg">
            Fernweg-Etappen (Westweg, Mittelweg, Ostweg) und Tagestouren mit echten Strecken, Höhenmetern und Gehzeiten – im Gespräch geplant.
          </p>
        </section>
        <ChatShell intro={INTRO} />
      </div>
      <PhotoSwitcher photos={photos} />
    </div>
  );
}
