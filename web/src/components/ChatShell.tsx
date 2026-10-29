"use client";

import { useEffect, useRef, useState } from "react";
import { streamChat, type ChatEvent, type Labels, type TourCard } from "../lib/chat";
import type { Photo } from "../lib/data";
import ChatMessages, { type ChatItem } from "./ChatMessages";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** The cover of a tour as a Photo; null unless author and licence are known (never shown unattributed). */
export function coverOf(card: TourCard | undefined): Photo | null {
  if (!card?.cover_thumb_url || !card.cover_author || !card.cover_license) return null;
  return {
    url: card.cover_thumb_url,
    thumb_url: card.cover_thumb_url,
    author: card.cover_author,
    license: card.cover_license,
    license_url: card.cover_license_url,
    page_url: card.cover_page_url,
  };
}

/** Planning chat of layout A: streams the agent's answer, result cards and sources. */
export default function ChatShell({
  intro,
  apiUrl = API_URL,
  onCover,
}: {
  intro: string;
  apiUrl?: string;
  /** Called with the cover of the first tour of a result set (null: no cover). */
  onCover?: (cover: Photo | null) => void;
}) {
  const [threadId] = useState(() => crypto.randomUUID());
  const [items, setItems] = useState<ChatItem[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const runWithoutPace = useRef(false);
  const labels = useRef<Labels>({});
  const unmounted = useRef(false);

  useEffect(() => {
    unmounted.current = false;
    return () => {
      unmounted.current = true;
      abort.current?.abort();
    };
  }, []);

  const apply = (e: ChatEvent) => {
    switch (e.type) {
      case "understood":
        runWithoutPace.current = e.request.activity === "run" && e.request.pace_min_per_km === null;
        labels.current = { ...labels.current, ...e.labels };
        setItems((l) => [...l, { kind: "understood", text: e.text, request: e.request, labels: labels.current }]);
        break;
      case "clarify":
        setItems((l) => [...l, { kind: "clarify", question: e.question, options: e.options }]);
        break;
      case "results":
        labels.current = { ...labels.current, ...e.labels };
        setItems((l) => [
          ...l,
          {
            kind: "results",
            cards: e.cards,
            fallback: e.fallback_reason,
            runWithoutPace: runWithoutPace.current,
            labels: labels.current,
          },
        ]);
        onCover?.(coverOf(e.cards[0]));
        break;
      case "token":
        setItems((l) => {
          const last = l[l.length - 1];
          if (last?.kind === "assistant") return [...l.slice(0, -1), { kind: "assistant", text: last.text + e.text }];
          return [...l, { kind: "assistant", text: e.text }];
        });
        break;
      case "sources":
        if (e.sources.length > 0) setItems((l) => [...l, { kind: "sources", sources: e.sources }]);
        break;
      case "error":
        setItems((l) => [...l, { kind: "error", text: e.message }]);
        break;
      case "done":
        break;
    }
  };

  const send = async (message: string) => {
    const m = message.trim();
    if (!m || busy) return;
    setText("");
    setItems((l) => [...l, { kind: "user", text: m }]);
    setBusy(true);
    const ctrl = new AbortController();
    abort.current = ctrl;
    await streamChat(apiUrl, threadId, m, apply, ctrl.signal);
    abort.current = null;
    if (unmounted.current) return;
    if (ctrl.signal.aborted) setItems((l) => [...l, { kind: "notice", text: "Abgebrochen." }]);
    setBusy(false);
  };

  return (
    <aside
      aria-label="Planungs-Chat"
      className="flex w-full flex-col gap-3 rounded-2xl border border-white/15 bg-papier/15 p-4 text-papier shadow-xl backdrop-blur-xl sm:max-w-sm md:max-w-md"
    >
      <h2 className="font-serif text-lg">Planungs-Chat</h2>
      <p className="rounded-xl rounded-tl-sm bg-papier/90 px-3 py-2 text-sm leading-relaxed text-wald-dunkel">{intro}</p>
      <ChatMessages items={items} onOption={send} disabled={busy} />
      {busy && (
        <p role="status" className="flex items-center gap-2 text-sm">
          denkt nach …
          <button
            type="button"
            onClick={() => abort.current?.abort()}
            className="rounded-full border border-white/40 px-3 py-0.5 text-xs hover:bg-white/15"
          >
            Abbrechen
          </button>
        </p>
      )}
      <form
        className="flex gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          void send(text);
        }}
      >
        <input
          type="text"
          value={text}
          onChange={(ev) => setText(ev.target.value)}
          maxLength={1000}
          placeholder="z. B. 12 km Rundweg ab Hinterzarten"
          aria-label="Nachricht"
          className="min-w-0 flex-1 rounded-full border border-white/25 bg-black/20 px-4 py-2 text-sm text-papier placeholder:text-papier/70"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:cursor-not-allowed disabled:opacity-60"
        >
          Senden
        </button>
      </form>
    </aside>
  );
}
