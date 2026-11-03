"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useT } from "../i18n";
import { useSession } from "../lib/auth";
import ChatMessages from "./ChatMessages";
import { useChat } from "./ChatProvider";

/** Planning chat: the conversation lives in ChatProvider; this is one view of it. */
export default function ChatShell({ intro, variant = "stage" }: { intro: string; variant?: "stage" | "hero" | "drawer" }) {
  const { state, busy, send, abort, reset } = useChat();
  const { session, loading } = useSession();
  const t = useT().chat;
  const [text, setText] = useState("");

  const submit = (m: string) => {
    if (!m.trim() || busy) return;
    setText("");
    // an expired session (or an auth check that is down, 503) keeps the typed message in the field
    void send(m).then((r) => r.keepDraft && setText((t) => t || m));
  };

  const hero = variant === "hero";
  // intro, history and status scroll together inside the box (thin light-green bar at its right
  // edge); the input stays below. Keep the newest message in view.
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [state.items.length, busy]);
  const body = (
    <>
      <div
        ref={scroller}
        data-chat-scroll
        className={`scrollbar-sense flex min-h-0 flex-col gap-3 overflow-y-auto ${
          variant === "stage"
            ? "-mr-4 max-h-[50vh] pr-3 md:max-h-none md:flex-1"
            : variant === "hero"
              ? "-mr-4 max-h-[35vh] pr-3 sm:-mr-5 sm:pr-4 md:max-h-[max(10rem,calc(100dvh-57.5rem))]"
              : "-mr-3 max-h-[50vh] pr-2"
        }`}
      >
      {/* start page: the example is a light hint on the green, the input field is what stands out */}
      <p
        data-chat-intro
        className={
          hero
            ? "rounded-xl rounded-tl-sm border border-sense px-3 py-2 text-sm leading-relaxed text-papier sm:text-base"
            : "rounded-xl rounded-tl-sm bg-papier/90 px-3 py-2 text-sm leading-relaxed text-wald-dunkel"
        }
      >
        {intro}
      </p>
      <ChatMessages items={state.items} onOption={(o) => void send(o)} disabled={busy} />
      {busy && (
        <p role="status" className="flex items-center gap-2 text-sm">
          {t.thinking}
          <button
            type="button"
            onClick={abort}
            className="rounded-full border border-white/40 px-3 py-0.5 text-xs hover:bg-white/15"
          >
            {t.cancel}
          </button>
        </p>
      )}
      </div>
      {loading ? null : !session ? (
        <p className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
          {t.signInBefore}
          <Link href="/anmelden" className="underline">
            {t.signInLink}
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
          placeholder={t.placeholder}
          aria-label={t.message}
          className={
            hero
              ? "min-w-0 flex-1 rounded-full border-2 border-sense bg-white px-5 py-3 text-base text-wald-dunkel shadow-lg placeholder:text-wald-dunkel/60 focus:outline-none focus:ring-4 focus:ring-sense/40"
              : "min-w-0 flex-1 rounded-full border border-white/25 bg-wald-dunkel px-4 py-2 text-sm text-papier placeholder:text-papier/70"
          }
        />
        <button
          type="submit"
          disabled={busy || !text.trim()}
          className={`rounded-full bg-wald text-papier disabled:cursor-not-allowed disabled:opacity-60 ${
            hero ? "px-6 py-3 text-base font-medium shadow-lg" : "px-4 py-2 text-sm"
          }`}
        >
          {t.send}
        </button>
      </form>
      )}
    </>
  );

  if (variant === "drawer") {
    return (
      <aside aria-label={t.title} className="w-full rounded-2xl bg-wald-flaeche p-3 text-papier ring-1 ring-white/10">
        <details>
          <summary className="cursor-pointer font-serif text-lg">{t.drawerTitle}</summary>
          <div className="mt-3 flex flex-col gap-3">{body}</div>
        </details>
      </aside>
    );
  }

  return (
    <aside
      aria-label={t.title}
      className={`flex w-full flex-col gap-3 rounded-2xl p-4 text-left text-papier ring-1 backdrop-blur-md ${
        variant === "hero"
          ? "max-w-2xl bg-wald-dunkel/70 shadow-[0_12px_40px_rgb(0_0_0/0.45)] ring-sense/25 sm:p-5"
          : "bg-wald-flaeche/60 ring-white/15 sm:max-w-sm md:min-h-0 md:max-w-md md:flex-1"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-serif text-lg">{t.title}</h2>
        {/* start over: clears this tab's conversation, the home page shows its start view again */}
        {variant === "stage" && (state.items.length > 0 || !!state.last || !!state.plan) && (
          <button
            type="button"
            onClick={reset}
            className="rounded-full border border-white/40 px-3 py-0.5 text-xs hover:bg-white/15"
          >
            {t.newSearch}
          </button>
        )}
      </div>
      {body}
    </aside>
  );
}
