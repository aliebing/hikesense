"use client";

import { useLocale, useT } from "../i18n";
import { chipsFor, foundText } from "./ChatMessages";
import { useChat } from "./ChatProvider";
import MerkenButton from "./MerkenButton";
import PlanPreview from "./PlanPreview";
import TourPreview from "./TourPreview";
import TourResultCard from "./TourResultCard";
import { savedSearchOf, searchTitle } from "../lib/plans";

const MAX_TILES = 6;

/** Right of the chat on the home page: the plan, the one tour, or the tiles of the last search. */
export default function ResultsPane() {
  const { state, busy } = useChat();
  const t = useT();
  const { locale } = useLocale();
  if (state.plan) return <PlanPreview data={state.plan} />;
  const last = state.last;
  if (!last || last.cards.length === 0) return null;
  // chips belong to the search that produced these cards, not to a later question
  const chips = last.request ? chipsFor(last.request.request, last.request.labels, locale) : [];
  const one = last.cards.length === 1;
  const cards = last.cards.slice(0, MAX_TILES);
  const saved = savedSearchOf(state);
  // every new search appends a results item, so its index tells searches apart
  const searchIndex = state.items.map((it) => it.kind).lastIndexOf("results");
  const merken = saved && (
    <MerkenButton
      key={searchIndex}
      kind="search"
      title={searchTitle(saved, locale)}
      payload={saved}
      label={t.results.save}
      onPhoto
      disabled={busy}
    />
  );
  return (
    <section className="flex flex-col gap-4">
      {one ? (
        merken
      ) : (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          <h2 className="schrift-feld font-serif text-2xl sm:text-3xl">{foundText(last.cards, locale)}</h2>
          {merken}
        </div>
      )}
      {chips.length > 0 && (
        <ul aria-label={t.chat.understood} className="flex flex-wrap gap-1.5">
          {chips.map((c, i) => (
            <li key={i} className={`rounded-full px-3 py-1 text-sm ${c.warn ? "bg-amber-200 text-amber-950" : "bg-panel/55 text-papier ring-1 ring-white/15 backdrop-blur-sm"}`}>
              {c.text}
            </li>
          ))}
        </ul>
      )}
      {last.fallback && (
        <p role="note" className="max-w-2xl rounded-xl border-l-4 border-amber-500 bg-amber-100 px-4 py-3 text-sm font-medium text-amber-950">
          {last.fallback}
        </p>
      )}
      {one ? (
        <TourPreview card={last.cards[0]} runWithoutPace={last.runWithoutPace} labels={last.labels} fallback={!!last.fallback} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {cards.map((c) => (
              <TourResultCard key={c.trail_id} card={c} runWithoutPace={last.runWithoutPace} labels={last.labels} size="large" from="chat" />
            ))}
          </div>
          <p className="schrift-feld text-sm font-medium text-papier">{t.results.tooMany}</p>
        </>
      )}
    </section>
  );
}
