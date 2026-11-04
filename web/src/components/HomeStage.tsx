"use client";

import { useEffect, useRef } from "react";
import { useT } from "../i18n";
import { pickBackdrop } from "../lib/backdrop";
import { coverOf } from "../lib/chatState";
import type { Photo } from "../lib/data";
import Attribution from "./Attribution";
import Backdrop from "./Backdrop";
import ChatShell from "./ChatShell";
import { useChat } from "./ChatProvider";
import { HeroBackdrop, HeroBrand, HeroFeatures } from "./HomeHero";
import ResultsPane from "./ResultsPane";

/**
 * Home content. Before any result: the HikeSense hero (logo, tagline, what the app does) on the
 * landscape photo, with the chat as the main control. After a search or plan: chat on the left,
 * the tiles (or the one tour, or the plan) on the right.
 */
export default function HomeStage({ landscapes = [] }: { /** background pool for the results view */ landscapes?: Photo[] }) {
  const { state, hydrated } = useChat();
  const t = useT().home;
  const hasResults = hydrated && ((state.last && state.last.cards.length > 0) || !!state.plan);
  // a new search or plan starts at the top of the results column
  const results = useRef<HTMLDivElement>(null);
  const shownFor = state.plan ? state.plan.plan.trail_id : state.last?.cards.map((c) => c.trail_id).join();
  useEffect(() => {
    results.current?.scrollTo?.({ top: 0 });
  }, [shownFor]);

  if (hasResults) {
    // behind the middle: the first tour's photo if it is a landscape, else one from the pool
    const first = state.plan ? null : state.last?.cards[0];
    const cover = coverOf(first ?? undefined);
    const backdrop = pickBackdrop(cover ? [cover] : [], landscapes, first?.trail_id ?? state.plan?.plan.trail_id ?? "plan");
    return (
      <div className="grid flex-1 items-start gap-6 md:grid-cols-[24rem_1fr]">
        <Backdrop photo={backdrop} />
        {/* from md on the chat column fits the window between header and footer; its history
            scrolls inside the box, so the page itself does not need a scrollbar */}
        <div className="flex flex-col gap-3 md:sticky md:top-4 md:max-h-[calc(100dvh-10rem)]">
          <h1 className="schrift-feld text-sm font-medium tracking-wide">{t.title}</h1>
          <ChatShell intro={t.intro} />
        </div>
        {/* the results scroll inside their column like the chat history, so two rows of tiles
            or a long plan do not make the page taller than the window */}
        <div ref={results} data-results-scroll className="scrollbar-sense flex min-w-0 flex-col gap-4 md:sticky md:top-4 md:-mr-3 md:max-h-[calc(100dvh-10rem)] md:overflow-y-auto md:pr-3">
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

  // phone: chat right under the brand (it is the main control), the four features below it;
  // from md on as in the mock-up: features under the subtitle, chat below them.
  // Until the tab's saved conversation is read (hydrated) it is unknown whether this or the
  // results view belongs here: keep both photo and hero invisible, then fade them in, so a
  // reload with results does not flash the start photo first.
  return (
    <>
      <HeroBackdrop shown={hydrated} />
      <div
        data-hero-content
        className={`mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-6 pt-1 pb-6 transition-opacity duration-500 sm:pt-4 md:gap-8 ${hydrated ? "" : "opacity-0"}`}
      >
        <HeroBrand />
        <HeroFeatures className="order-3 md:order-none" />
        <ChatShell intro={t.intro} variant="hero" />
      </div>
    </>
  );
}
