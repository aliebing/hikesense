"use client";

import { chipsFor } from "./ChatMessages";
import { useChat } from "./ChatProvider";
import PlanPreview from "./PlanPreview";
import TourPreview from "./TourPreview";
import TourResultCard from "./TourResultCard";

const MAX_TILES = 6;

/** Right of the chat on the home page: the plan, the one tour, or the tiles of the last search. */
export default function ResultsPane() {
  const { state } = useChat();
  if (state.plan) return <PlanPreview data={state.plan} />;
  const last = state.last;
  if (!last || last.cards.length === 0) return null;
  if (last.cards.length === 1) return <TourPreview card={last.cards[0]} runWithoutPace={last.runWithoutPace} labels={last.labels} />;

  // chips belong to the search that produced these cards, not to a later question
  const chips = last.request ? chipsFor(last.request.request, last.request.labels) : [];
  const cards = last.cards.slice(0, MAX_TILES);
  return (
    <section className="flex flex-col gap-4">
      <h2 className="font-serif text-2xl sm:text-3xl">{last.cards.length} Touren gefunden</h2>
      {chips.length > 0 && (
        <ul aria-label="Erkannte Wünsche" className="flex flex-wrap gap-1.5">
          {chips.map((c, i) => (
            <li key={i} className={`rounded-full px-3 py-1 text-sm ${c.warn ? "bg-amber-200 text-amber-950" : "bg-wald-flaeche text-papier ring-1 ring-white/15"}`}>
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
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {cards.map((c) => (
          <TourResultCard key={c.trail_id} card={c} runWithoutPace={last.runWithoutPace} labels={last.labels} size="large" from="chat" />
        ))}
      </div>
      <p className="text-sm text-papier/85">Zu viele? Schreib z. B. „mit Einkehr“ oder „unter 300 Hm“.</p>
    </section>
  );
}
