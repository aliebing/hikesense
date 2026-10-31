"use client";

import Link from "next/link";
import ChatShell from "./ChatShell";
import { useChat } from "./ChatProvider";

/** Home content: title and the chat in the middle; the suggestions button appears once the chat found tours. */
export default function HomeStage() {
  const { state } = useChat();

  return (
    <div className="mx-auto flex w-full max-w-xl flex-1 flex-col items-center justify-center gap-6 py-4 sm:py-8">
      <section className="text-center">
        <h1 className="font-serif text-4xl leading-tight drop-shadow-md sm:text-6xl">Wandern im Schwarzwald</h1>
        <p className="mx-auto mt-3 max-w-lg text-base text-papier/90 drop-shadow sm:text-lg">
          Fernweg-Etappen (Westweg, Mittelweg, Ostweg) und Tagestouren mit echten Strecken, Höhenmetern und Gehzeiten – im Gespräch geplant.
        </p>
      </section>

      <ChatShell intro="Hallo! Beschreibe deine Tagestour – zum Beispiel „Rundweg ab Hinterzarten, 10 bis 15 km, wenig Höhenmeter, mit Aussicht“." />

      {((state.last && state.last.cards.length > 0) || state.plan) && (
        <Link
          href="/vorschlaege"
          className="rounded-full bg-papier px-5 py-2 text-sm font-medium text-wald-dunkel shadow-lg hover:bg-white"
        >
          Vorschläge zeigen →
        </Link>
      )}
    </div>
  );
}
