"use client";

import Link from "next/link";
import { useState } from "react";
import { useSession } from "../lib/auth";
import ChatMessages from "./ChatMessages";
import { useChat } from "./ChatProvider";

/** Planning chat: the conversation lives in ChatProvider; this is one view of it. */
export default function ChatShell({ intro, variant = "stage" }: { intro: string; variant?: "stage" | "drawer" }) {
  const { state, busy, send, abort } = useChat();
  const { session, loading } = useSession();
  const [text, setText] = useState("");

  const submit = (m: string) => {
    if (!m.trim() || busy) return;
    setText("");
    // an expired session (or an auth check that is down, 503) keeps the typed message in the field
    void send(m).then((r) => r.keepDraft && setText((t) => t || m));
  };

  const body = (
    <>
      <p className="rounded-xl rounded-tl-sm bg-papier/90 px-3 py-2 text-sm leading-relaxed text-wald-dunkel">{intro}</p>
      <ChatMessages items={state.items} onOption={(o) => void send(o)} disabled={busy} />
      {busy && (
        <p role="status" className="flex items-center gap-2 text-sm">
          denkt nach …
          <button
            type="button"
            onClick={abort}
            className="rounded-full border border-white/40 px-3 py-0.5 text-xs hover:bg-white/15"
          >
            Abbrechen
          </button>
        </p>
      )}
      {loading ? null : !session ? (
        <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          Zum Planen bitte{" "}
          <Link href="/anmelden" className="underline">
            anmelden
          </Link>
        </p>
      ) : (
      <form
        className="flex gap-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          submit(text);
        }}
      >
        <input
          type="text"
          value={text}
          onChange={(ev) => setText(ev.target.value)}
          maxLength={1000}
          placeholder="z. B. 12 km Rundweg ab Hinterzarten"
          aria-label="Nachricht"
          className="min-w-0 flex-1 rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70"
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className="rounded-full bg-wald px-4 py-2 text-sm text-papier disabled:cursor-not-allowed disabled:opacity-60"
        >
          Senden
        </button>
      </form>
      )}
    </>
  );

  if (variant === "drawer") {
    return (
      <aside aria-label="Planungs-Chat" className="w-full rounded-2xl bg-wald-flaeche p-3 text-papier ring-1 ring-white/10">
        <details>
          <summary className="cursor-pointer font-serif text-lg">Chat</summary>
          <div className="mt-3 flex flex-col gap-3">{body}</div>
        </details>
      </aside>
    );
  }

  return (
    <aside
      aria-label="Planungs-Chat"
      className="flex w-full flex-col gap-3 rounded-2xl bg-wald-flaeche p-4 text-papier ring-1 ring-white/10 sm:max-w-sm md:max-w-md"
    >
      <h2 className="font-serif text-lg">Planungs-Chat</h2>
      {body}
    </aside>
  );
}
