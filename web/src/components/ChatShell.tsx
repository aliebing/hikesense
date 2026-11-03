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
  const inputRef = useRef<HTMLInputElement>(null);
  // after sending or picking an option the cursor goes back to the field (not on touch screens:
  // that would pop up the keyboard)
  const refocus = () => {
    if (typeof window !== "undefined" && window.matchMedia?.("(pointer: fine)").matches) {
      inputRef.current?.focus({ preventScroll: true });
    }
  };
  // intro, history and status scroll together inside the box (thin light-green bar at its right
  // edge); the input stays below. Sending scrolls to the end; when the answer arrives, the newest
  // exchange is read from its start (your last message at the top) -- unless you scrolled up.
  const scroller = useRef<HTMLDivElement>(null);
  const lastKind = state.items.at(-1)?.kind;
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    const turns = el.querySelectorAll<HTMLElement>("[data-turn]");
    const turn = turns[turns.length - 1];
    if (lastKind !== "user" && turn && !busy) {
      el.scrollTop = turn.offsetTop - el.offsetTop - 8;
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [state.items.length, busy, lastKind]);
  const body = (
    <>
      <div
        ref={scroller}
        data-chat-scroll
        className={`scrollbar-sense flex min-h-0 flex-col gap-3 overflow-y-auto scroll-smooth motion-reduce:scroll-auto ${
          variant === "stage"
            ? "-mr-4 max-h-[50vh] pr-3 md:max-h-none md:flex-1"
            : variant === "hero"
              ? "-mr-4 max-h-[35vh] pr-3 sm:-mr-5 sm:pr-4 md:max-h-[max(10rem,calc(100dvh-55rem))]"
              : "-mr-3 max-h-[50vh] pr-2"
        }`}
      >
        {/* start page: the example is a light hint in a sense-green frame; in the results view
            a short line on how to go on */}
        <p
          data-chat-intro
          className={
            hero
              ? "rounded-xl rounded-tl-md border border-sense px-4 py-3 text-[15px] leading-relaxed text-papier sm:text-base"
              : "text-[13px] text-papier/80"
          }
        >
          {hero ? intro : t.introShort}
        </p>
        <ChatMessages
          items={state.items}
          onOption={(o) => {
            void send(o);
            refocus();
          }}
          disabled={busy}
        />
        {busy && (
          <p role="status" className="flex items-center gap-3 pl-3 text-sm text-papier/85">
            <span aria-hidden="true" className="flex gap-1">
              <span className="size-1.5 animate-pulse rounded-full bg-sense motion-reduce:animate-none" />
              <span className="size-1.5 animate-pulse rounded-full bg-sense [animation-delay:150ms] motion-reduce:animate-none" />
              <span className="size-1.5 animate-pulse rounded-full bg-sense [animation-delay:300ms] motion-reduce:animate-none" />
            </span>
            {t.thinking}
            <button
              type="button"
              onClick={abort}
              className="rounded-full border border-white/30 px-3 py-1 text-[13px] hover:border-sense hover:text-sense focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sense"
            >
              {t.cancel}
            </button>
          </p>
        )}
      </div>
      {loading ? null : !session ? (
        <p className="rounded-2xl border border-white/15 bg-white/5 px-3.5 py-2.5 text-sm text-papier">
          {t.signInBefore}
          <Link href="/anmelden" className="font-semibold text-sense underline-offset-2 hover:underline">
            {t.signInLink}
          </Link>
        </p>
      ) : (
        <form
          className="flex items-center gap-2"
          onSubmit={(ev) => {
            ev.preventDefault();
            submit(text);
            refocus();
          }}
        >
          <input
            ref={inputRef}
            type="text"
            value={text}
            onChange={(ev) => setText(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Escape" && busy) abort();
            }}
            maxLength={1000}
            placeholder={t.placeholder}
            aria-label={t.message}
            enterKeyHint="send"
            autoComplete="off"
            className={`min-w-0 flex-1 rounded-full border-2 border-sense bg-white text-wald-dunkel shadow-lg placeholder:text-wald-dunkel/70 focus:outline-none focus:ring-4 focus:ring-sense/40 ${
              hero ? "px-5 py-3 text-base" : "px-4 py-2.5 text-base sm:text-[15px]"
            }`}
          />
          <button
            type="submit"
            disabled={busy || !text.trim()}
            aria-label={hero ? undefined : t.send}
            className={`shrink-0 rounded-full bg-sense font-semibold text-wald-dunkel shadow-lg transition hover:brightness-110 focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-sense/40 disabled:cursor-not-allowed disabled:bg-white/15 disabled:text-papier/60 disabled:shadow-none disabled:hover:brightness-100 ${
              hero ? "px-6 py-3 text-base" : "grid size-11 place-items-center"
            }`}
          >
            {hero ? (
              t.send
            ) : (
              <svg aria-hidden="true" viewBox="0 0 20 20" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 10h11M11 5l5 5-5 5" />
              </svg>
            )}
          </button>
        </form>
      )}
    </>
  );

  if (variant === "drawer") {
    return (
      <aside aria-label={t.title} className="w-full rounded-2xl bg-panel/85 p-3 text-papier ring-1 ring-white/10">
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
      className={`flex w-full flex-col gap-3 p-4 text-left text-papier ring-1 backdrop-blur-md ${
        variant === "hero"
          ? "max-w-2xl rounded-3xl bg-panel/80 shadow-[0_12px_40px_rgb(0_0_0/0.45)] ring-sense/30 sm:p-5"
          : "rounded-2xl bg-panel/85 ring-white/10 sm:max-w-sm md:min-h-0 md:max-w-md md:flex-1"
      }`}
    >
      {hero ? (
        <h2 className="sr-only">{t.title}</h2>
      ) : (
        <div className="flex items-center justify-between gap-2 border-b border-white/10 pb-2">
          <h2 className="font-serif text-lg">{t.title}</h2>
          {/* start over: clears this tab's conversation, the home page shows its start view again */}
          {variant === "stage" && (state.items.length > 0 || !!state.last || !!state.plan) && (
            <button
              type="button"
              onClick={reset}
              className="rounded-full border border-white/30 px-3 py-1 text-[13px] text-papier hover:border-sense hover:text-sense focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sense"
            >
              <span aria-hidden="true">↺ </span>
              {t.newSearch}
            </button>
          )}
        </div>
      )}
      {body}
    </aside>
  );
}
