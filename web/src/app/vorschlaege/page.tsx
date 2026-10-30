"use client";

import Link from "next/link";
import { chipsFor, withoutFallback } from "../../components/ChatMessages";
import ChatShell from "../../components/ChatShell";
import { useChat } from "../../components/ChatProvider";
import HeroBackdrop from "../../components/HeroBackdrop";
import Panorama from "../../components/Panorama";
import TourResultCard from "../../components/TourResultCard";
import { coverOf } from "../../lib/chatState";
import type { Photo } from "../../lib/data";

const MAX_CARDS = 5;

/** Suggestions: understood wishes, the answer sentence, the honest fallback note and large tour cards. */
export default function Vorschlaege() {
  const { state, hydrated } = useChat();
  const last = state.last;
  const cards = last?.cards.slice(0, MAX_CARDS) ?? [];
  // chips belong to the search that produced these cards, not to a later question
  const chips = last?.request ? chipsFor(last.request.request, last.request.labels) : [];

  // the last assistant sentence between the last results event and the next user turn, without the fallback sentence
  const lastResults = state.items.map((it) => it.kind).lastIndexOf("results");
  let sentence = "";
  for (let i = lastResults + 1; lastResults >= 0 && i < state.items.length; i++) {
    const it = state.items[i];
    if (it.kind === "user") break;
    if (it.kind === "assistant") sentence = withoutFallback(state.items, i, it.text);
  }

  const photos = cards
    .map(coverOf)
    .filter((p, i, all): p is Photo => !!p && all.findIndex((q) => q?.url === p.url) === i);

  return (
    <Panorama back={{ href: "/", label: "← Zum Chat" }}>
      <HeroBackdrop photos={photos} />
      <main className="flex flex-1 flex-col gap-5 pb-4">
        <h1 className="font-serif text-3xl drop-shadow-md sm:text-4xl">Vorschläge</h1>
        {!hydrated ? null : cards.length === 0 ? (
          <div className="flex flex-col items-start gap-3 text-papier">
            <p>Noch keine Vorschläge.</p>
            <Link href="/" className="rounded-full bg-papier px-5 py-2 text-sm font-medium text-wald-dunkel shadow-lg hover:bg-white">
              Zur Startseite
            </Link>
          </div>
        ) : (
          <>
            {chips.length > 0 && (
              <ul aria-label="Erkannte Wünsche" className="flex flex-wrap gap-1.5">
                {chips.map((c, i) => (
                  <li
                    key={i}
                    className={`rounded-full px-3 py-1 text-sm ${c.warn ? "bg-amber-200 text-amber-950" : "bg-papier/85 text-wald-dunkel"}`}
                  >
                    {c.text}
                  </li>
                ))}
              </ul>
            )}
            {last?.fallback && (
              <p role="note" className="max-w-2xl rounded-xl border-l-4 border-amber-500 bg-amber-100 px-4 py-3 text-sm font-medium text-amber-950">
                {last.fallback}
              </p>
            )}
            {sentence && <p className="max-w-2xl text-lg drop-shadow">{sentence}</p>}
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {cards.map((c) => (
                <TourResultCard
                  key={c.trail_id}
                  card={c}
                  runWithoutPace={last!.runWithoutPace}
                  labels={last!.labels}
                  size="large"
                  from="vorschlaege"
                />
              ))}
            </div>
          </>
        )}
      </main>
      <div className="sticky bottom-12 z-10 ml-auto w-full max-w-md">
        <ChatShell variant="drawer" intro="Möchtest du etwas anpassen? Schreib mir, was anders sein soll." />
      </div>
    </Panorama>
  );
}
