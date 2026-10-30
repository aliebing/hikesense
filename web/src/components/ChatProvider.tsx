"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getAccessToken, onSignedOut } from "../lib/auth";
import { streamChat } from "../lib/chat";
import { addNotice, addUser, initialState, loadState, reduceEvent, saveState, STORAGE_KEY, type ChatState } from "../lib/chatState";

/** Same origin by default: next.config.ts proxies /api/chat to the backend (one tunnel for the phone). */
const API_URL = process.env.NEXT_PUBLIC_API_URL || "/api";

type Chat = { state: ChatState; busy: boolean; hydrated: boolean; /** resolves to { auth: true } when the turn ended because the session is missing or expired */
  send(text: string): Promise<{ auth: boolean }>; abort(): void;
  /** drops the conversation (new thread id, stored copy removed), e.g. on sign-out */
  reset(): void };

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
  const generation = useRef(0); // bumped by reset: a stream of the old conversation writes nothing
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
      if (!m || busyRef.current) return { auth: false };
      busyRef.current = true;
      setBusy(true);
      setState((s) => addUser(s, m));
      const c = new AbortController();
      ctrl.current = c;
      const gen = generation.current;
      let auth = false;
      const token = await getAccessToken();
      await streamChat(
        apiUrl,
        stateRef.current.threadId,
        m,
        (e) => {
          if (generation.current !== gen) return;
          if (e.type === "auth") auth = true;
          setState((s) => reduceEvent(s, e));
        },
        c.signal,
        token,
      );
      if (ctrl.current === c) ctrl.current = null;
      if (unmounted.current) return { auth };
      if (c.signal.aborted && generation.current === gen) setState((s) => addNotice(s, "Abgebrochen."));
      busyRef.current = false;
      setBusy(false);
      return { auth };
    },
    [apiUrl],
  );

  const abort = useCallback(() => ctrl.current?.abort(), []);

  // Shared device: after sign-out the next person must not see (or continue) this conversation.
  const reset = useCallback(() => {
    generation.current += 1;
    ctrl.current?.abort();
    try {
      storage()?.removeItem(STORAGE_KEY);
    } catch {
      // storage blocked: the fresh state below is saved over it anyway
    }
    setState(initialState(newId()));
  }, []);

  useEffect(() => onSignedOut(reset), [reset]);

  const value = useMemo(() => ({ state, busy, hydrated, send, abort, reset }), [state, busy, hydrated, send, abort, reset]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** The provider's reset, or undefined outside a ChatProvider (e.g. the header in isolation). */
export function useResetChat(): (() => void) | undefined {
  return useContext(Ctx)?.reset;
}

export function useChat(): Chat {
  const chat = useContext(Ctx);
  if (!chat) throw new Error("useChat needs a ChatProvider");
  return chat;
}
