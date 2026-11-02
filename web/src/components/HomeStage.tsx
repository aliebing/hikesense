"use client";

import { useT } from "../i18n";
import { pickBackdrop } from "../lib/backdrop";
import { coverOf } from "../lib/chatState";
import type { Photo } from "../lib/data";
import Attribution from "./Attribution";
import Backdrop from "./Backdrop";
import ChatShell from "./ChatShell";
import { useChat } from "./ChatProvider";
import PhotoSwitcher from "./PhotoSwitcher";
import ResultsPane from "./ResultsPane";

/**
 * Home content. Before any result: title and chat in the middle of the full-screen background photo.
 * After a search or plan: chat on the left, the tiles (or the one tour, or the plan) on the right.
 */
export default function HomeStage({ photos, landscapes = [] }: { photos: Photo[]; /** background pool for the results view */ landscapes?: Photo[] }) {
  const { state, hydrated } = useChat();
  const t = useT().home;
  const hasResults = hydrated && ((state.last && state.last.cards.length > 0) || !!state.plan);

  if (hasResults) {
    // behind the middle: the first tour's photo if it is a landscape, else one from the pool
    const first = state.plan ? null : state.last?.cards[0];
    const cover = coverOf(first ?? undefined);
    const backdrop = pickBackdrop(cover ? [cover] : [], landscapes, first?.trail_id ?? state.plan?.plan.trail_id ?? "plan");
    return (
      <div className="grid flex-1 items-start gap-6 md:grid-cols-[24rem_1fr]">
        <Backdrop photo={backdrop} />
        <div className="flex flex-col gap-3 md:sticky md:top-4">
          <h1 className="schrift-feld font-serif text-2xl">{t.title}</h1>
          <ChatShell intro={t.intro} />
        </div>
        <div className="flex min-w-0 flex-col gap-4">
          <ResultsPane />
          {backdrop && (
            <div className="flex flex-wrap items-baseline gap-1 text-[11px] text-papier schrift-feld">
              <Attribution photo={backdrop} label={t.backdropCredit} />
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 py-4 sm:py-8">
        <section className="flex flex-col items-center gap-3 text-center">
          <h1 className="schrift-feld px-5 py-2 font-serif text-4xl leading-tight sm:text-6xl">{t.title}</h1>
          <p className="schrift-feld max-w-lg px-4 py-2 text-base text-papier sm:text-lg">
            {t.subtitle}
          </p>
        </section>
        <ChatShell intro={t.intro} />
      </div>
      <div className="flex justify-end">
        <PhotoSwitcher photos={photos} variant="backdrop" />
      </div>
    </>
  );
}
