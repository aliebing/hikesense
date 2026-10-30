import type { ChatEvent, HikeRequest, Labels, TourCard } from "./chat";
import type { Photo } from "./data";
import type { ChatItem } from "../components/ChatMessages";

export type LastResults = { cards: TourCard[]; fallback: string | null; runWithoutPace: boolean; labels: Labels };

export type ChatState = {
  threadId: string;
  items: ChatItem[];
  /** null: nothing found yet, or the last search found nothing */
  last: LastResults | null;
  /** the last understood request (for chips on /vorschlaege); null before the first */
  request: { request: HikeRequest; labels: Labels } | null;
  /** internal: activity "run" without pace, carried from "understood" to "results" */
  runWithoutPace: boolean;
};

export const STORAGE_KEY = "hikeall.chat.v1";

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

export function initialState(threadId: string): ChatState {
  return { threadId, items: [], last: null, request: null, runWithoutPace: false };
}

/** All labels seen so far in this conversation (later ones win). */
function labelsOf(items: ChatItem[]): Labels {
  let labels: Labels = {};
  for (const it of items) if (it.kind === "understood" || it.kind === "results") labels = { ...labels, ...it.labels };
  return labels;
}

const add = (s: ChatState, item: ChatItem): ChatState => ({ ...s, items: [...s.items, item] });

export function reduceEvent(s: ChatState, e: ChatEvent): ChatState {
  switch (e.type) {
    case "understood": {
      const labels = { ...labelsOf(s.items), ...e.labels };
      const runWithoutPace = e.request.activity === "run" && e.request.pace_min_per_km === null;
      return {
        ...add(s, { kind: "understood", text: e.text, request: e.request, labels }),
        request: { request: e.request, labels },
        runWithoutPace,
      };
    }
    case "clarify":
      return add(s, { kind: "clarify", question: e.question, options: e.options });
    case "results": {
      const labels = { ...labelsOf(s.items), ...e.labels };
      const item = {
        cards: e.cards,
        fallback: e.fallback_reason,
        runWithoutPace: s.runWithoutPace,
        labels,
      };
      // An empty result list clears "Passend": the page never shows stale tours.
      return { ...add(s, { kind: "results", ...item }), last: e.cards.length > 0 ? item : null };
    }
    case "token": {
      const last = s.items[s.items.length - 1];
      if (last?.kind === "assistant") {
        return { ...s, items: [...s.items.slice(0, -1), { kind: "assistant", text: last.text + e.text }] };
      }
      return add(s, { kind: "assistant", text: e.text });
    }
    case "sources":
      return e.sources.length > 0 ? add(s, { kind: "sources", sources: e.sources }) : s;
    case "error":
      return add(s, { kind: "error", text: e.message });
    case "done":
      return s;
  }
}

export const addUser = (s: ChatState, text: string): ChatState => add(s, { kind: "user", text });
export const addNotice = (s: ChatState, text: string): ChatState => add(s, { kind: "notice", text });

/** Never throws: unreadable, corrupt or foreign data starts a fresh conversation. */
export function loadState(storage: Storage | null, newId: () => string): ChatState {
  try {
    const raw = storage?.getItem(STORAGE_KEY);
    if (raw) {
      const v = JSON.parse(raw) as Partial<ChatState> & { v?: number };
      if (v && v.v === 1 && typeof v.threadId === "string" && Array.isArray(v.items)) {
        return { ...initialState(v.threadId), ...v, v: undefined } as ChatState;
      }
    }
  } catch {
    // fall through to a fresh conversation
  }
  return initialState(newId());
}

/** Never throws (quota, private mode): losing the history is better than breaking the chat. */
export function saveState(storage: Storage | null, s: ChatState): void {
  try {
    storage?.setItem(STORAGE_KEY, JSON.stringify({ v: 1, ...s }));
  } catch {
    // ignore
  }
}
