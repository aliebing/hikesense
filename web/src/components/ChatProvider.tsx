"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { streamChat } from "../lib/chat";
import { addNotice, addUser, initialState, loadState, reduceEvent, saveState, type ChatState } from "../lib/chatState";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type Chat = { state: ChatState; busy: boolean; hydrated: boolean; send(text: string): Promise<void>; abort(): void };

const Ctx = createContext<Chat | null>(null);

/** crypto.randomUUID only exists in secure contexts (not over plain HTTP on the LAN). */
function newId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}${Math.random().toString(36).slice(2)}`;
}

const storage = () => {
  try {
    return window.sessionStorage;
  } catch {
    return null;
  }
};

/** One conversation per browser tab: shared by all pages, kept in sessionStorage across reloads. */
export function ChatProvider({ children, apiUrl = API_URL }: { children: React.ReactNode; apiUrl?: string }) {
  const [state, setState] = useState(() => initialState(newId()));
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const stateRef = useRef(state);
  const busyRef = useRef(false);
  const ctrl = useRef<AbortController | null>(null);
  const unmounted = useRef(false);
  stateRef.current = state;

  // Loaded after mount (not in the initial state) so server and client render the same markup.
  useEffect(() => {
    setState(loadState(storage(), newId));
    setHydrated(true);
  }, []);

  // busy is not part of the stored state: a reload never resumes a stream.
  useEffect(() => {
    if (hydrated) saveState(storage(), state);
  }, [hydrated, state]);

  useEffect(() => {
    unmounted.current = false;
    return () => {
      unmounted.current = true;
      ctrl.current?.abort();
    };
  }, []);

  const send = useCallback(
    async (message: string) => {
      const m = message.trim();
      if (!m || busyRef.current) return;
      busyRef.current = true;
      setBusy(true);
      setState((s) => addUser(s, m));
      const c = new AbortController();
      ctrl.current = c;
      await streamChat(apiUrl, stateRef.current.threadId, m, (e) => setState((s) => reduceEvent(s, e)), c.signal);
      ctrl.current = null;
      if (unmounted.current) return;
      if (c.signal.aborted) setState((s) => addNotice(s, "Abgebrochen."));
      busyRef.current = false;
      setBusy(false);
    },
    [apiUrl],
  );

  const abort = useCallback(() => ctrl.current?.abort(), []);

  const value = useMemo(() => ({ state, busy, hydrated, send, abort }), [state, busy, hydrated, send, abort]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useChat(): Chat {
  const chat = useContext(Ctx);
  if (!chat) throw new Error("useChat needs a ChatProvider");
  return chat;
}
