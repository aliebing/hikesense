"use client";

import { useRef, useState } from "react";
import { streamChat, type ChatEvent } from "../lib/chat";
import ChatMessages, { type ChatItem } from "./ChatMessages";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** Planning chat of layout A: streams the agent's answer, result cards and sources. */
export default function ChatShell({
  intro,
  apiUrl = API_URL,
  onCover,
}: {
  intro: string;
  apiUrl?: string;
  /** Called with the cover of the first tour of a result set (null: no cover). */
  onCover?: (url: string | null) => void;
}) {
  const [threadId] = useState(() => crypto.randomUUID());
  const [items, setItems] = useState<ChatItem[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const runWithoutPace = useRef(false);

  const apply = (e: ChatEvent) => {
    switch (e.type) {
      case "understood":
        runWithoutPace.current = e.request.activity === "run" && e.request.pace_min_per_km === null;
        setItems((l) => [...l, { kind: "understood", text: e.text, request: e.request }]);
        break;
      case "clarify":
        setItems((l) => [...l, { kind: "clarify", question: e.question, options: e.options }]);
        break;
      case "results":
        setItems((l) => [
          ...l,
          { kind: "results", cards: e.cards, fallback: e.fallback_reason, runWithoutPace: runWithoutPace.current },
        ]);
        onCover?.(e.cards[0]?.cover_thumb_url ?? null);
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
    if (ctrl.signal.aborted) setItems((l) => [...l, { kind: "error", text: "Abgebrochen." }]);
    abort.current = null;
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
