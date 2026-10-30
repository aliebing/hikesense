import type { ChatEvent, TourCard } from "./chat";
import { addNotice, addUser, initialState, loadState, reduceEvent, saveState, STORAGE_KEY, type ChatState } from "./chatState";

const card = (id: string): TourCard =>
  ({
    trail_id: id, name: id, length_km: 1, ascent_m: 1, duration_h: 1, distance_km: null,
    cover_thumb_url: null, cover_author: null, cover_license: null, cover_license_url: null, cover_page_url: null,
    results: [], deviation_text: null, preference: { score: 0, met: [], missing: [], avoided_hit: [] },
  }) as unknown as TourCard;
const results = (ids: string[]): ChatEvent => ({ type: "results", cards: ids.map(card), fallback_reason: null });
const request = (over: object = {}) =>
  ({
    intent: "day_hike", activity: "hike", start_text: null, start: null, constraints: [], preferences: [],
    pace_min_per_km: null, unmatched: [], question: null, ...over,
  }) as never;
const run = (events: ChatEvent[], s: ChatState = initialState("t")) => events.reduce(reduceEvent, s);

function fakeStorage(over: Partial<Storage> = {}): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
    clear: () => m.clear(),
    key: () => null,
    length: 0,
    ...over,
  } as Storage;
}

it("results replaces last", () => {
  const s = run([results(["a"]), results(["b", "c"])]);
  expect(s.last?.cards.map((c) => c.trail_id)).toEqual(["b", "c"]);
});

it("empty results clear last", () => {
  const s = run([results(["a"]), results([])]);
  expect(s.last).toBeNull();
});

it("clarify, token, sources and error keep last", () => {
  const s = run([
    results(["a"]),
    { type: "clarify", question: "?", options: ["x"] },
    { type: "token", text: "hi" },
    { type: "sources", sources: [{ id: "s", name: "S", url: null, license: null, status: null }] },
    { type: "error", message: "boom" },
  ]);
  expect(s.last?.cards.map((c) => c.trail_id)).toEqual(["a"]);
  expect(addNotice(addUser(s, "x"), "Abgebrochen.").last).toBe(s.last);
});

it("understood sets request and runWithoutPace", () => {
  const s = run([
    { type: "understood", text: "t", request: request({ activity: "run" }), labels: { a: "A" } },
    results(["a"]),
  ]);
  expect(s.request?.labels).toEqual({ a: "A" });
  expect(s.last?.runWithoutPace).toBe(true);
  const hike = run([{ type: "understood", text: "t", request: request(), labels: {} }, results(["a"])]);
  expect(hike.last?.runWithoutPace).toBe(false);
});

it("token appends to the last assistant item", () => {
  const s = run([{ type: "token", text: "Der " }, { type: "token", text: "Feldberg." }]);
  expect(s.items).toEqual([{ kind: "assistant", text: "Der Feldberg." }]);
});

it("starts fresh on corrupt storage", () => {
  const id = () => "fresh";
  expect(loadState(fakeStorage({ getItem: () => "{kaputt" }), id)).toEqual(initialState("fresh"));
  expect(loadState(fakeStorage({ getItem: () => '{"v":0}' }), id)).toEqual(initialState("fresh"));
  expect(
    loadState(fakeStorage({ getItem: () => { throw new Error("denied"); } }), id),
  ).toEqual(initialState("fresh"));
  expect(loadState(null, id)).toEqual(initialState("fresh"));
});

it("round trip", () => {
  const storage = fakeStorage();
  const s = run(
    [{ type: "understood", text: "t", request: request(), labels: { a: "A" } }, results(["a"]), { type: "token", text: "x" }],
    initialState("thread-1"),
  );
  saveState(storage, s);
  expect(storage.getItem(STORAGE_KEY)).toContain('"v":1');
  expect(loadState(storage, () => "other")).toEqual(s);
});

it("saveState swallows quota errors", () => {
  const storage = fakeStorage({ setItem: () => { throw new DOMException("full", "QuotaExceededError"); } });
  expect(() => saveState(storage, initialState("t"))).not.toThrow();
});

it("survives repeated load and save cycles", () => {
  const storage = fakeStorage();
  const s = run([results(["a"]), { type: "token", text: "x" }], initialState("thread-1"));
  saveState(storage, s);
  const once = loadState(storage, () => "other");
  saveState(storage, once);
  const twice = loadState(storage, () => "other");
  expect(twice.threadId).toBe("thread-1");
  expect(twice.items).toEqual(s.items);
  expect(twice.last).toEqual(s.last);
});

it("drops a malformed last or request but keeps the rest", () => {
  const storage = fakeStorage();
  storage.setItem(STORAGE_KEY, JSON.stringify({ v: 1, threadId: "t1", items: [{ kind: "user", text: "hi" }], last: "x", request: 5 }));
  const s = loadState(storage, () => "other");
  expect(s.threadId).toBe("t1");
  expect(s.items).toHaveLength(1);
  expect(s.last).toBeNull();
  expect(s.request).toBeNull();
});

const planEvent = (days: number): ChatEvent =>
  ({ type: "plan", plan: { trail_id: "t", trail_name: "T", target_km: 15, days: Array.from({ length: days }, (_, i) => ({ day: i + 1 })), notes: days ? [] : ["Ab hier endet der Weg."], source_ids: [] }, weather: {}, rain: {} }) as unknown as ChatEvent;

it("plan event sets plan, clears last, adds a one-line item; results clears plan", () => {
  let s = reduceEvent(initialState("t"), results(["a"]));
  s = reduceEvent(s, planEvent(3));
  expect(s.last).toBeNull();
  expect(s.plan?.plan.days).toHaveLength(3);
  expect(s.items[s.items.length - 1]).toEqual({ kind: "plan", summary: "Plan mit 3 Tagen erstellt" });
  s = reduceEvent(s, results(["b"]));
  expect(s.plan).toBeNull();
  expect(s.last?.cards).toHaveLength(1);
});

it("a plan without days keeps the plan (notes) and shows the dead-end note", () => {
  const s = reduceEvent(initialState("t"), planEvent(0));
  expect(s.plan).not.toBeNull();
  expect(s.items[0]).toEqual({ kind: "plan", summary: "Ab hier endet der Weg." });
});

it("plan survives a reload; a corrupt plan is dropped", () => {
  const s = reduceEvent(initialState("t"), planEvent(2));
  const store = new Map<string, string>();
  const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) } as unknown as Storage;
  saveState(storage, s);
  expect(loadState(storage, () => "n").plan?.plan.days).toHaveLength(2);
  store.set(STORAGE_KEY, JSON.stringify({ ...s, v: 1, plan: { plan: "x" } }));
  expect(loadState(storage, () => "n").plan).toBeNull();
});

it("the plan keeps the start of the request at that moment", () => {
  let s = reduceEvent(initialState("t"), { type: "understood", text: "x", request: { ...(request() as object), start: { label: "Hausach" } } as never });
  s = reduceEvent(s, planEvent(1));
  s = reduceEvent(s, { type: "understood", text: "y", request: { ...(request() as object), start: { label: "Kandern" } } as never });
  expect(s.plan?.start_name).toBe("Hausach");
});

it("an old stored state without plan loads with plan null; a plan without notes gets []", () => {
  const store = new Map<string, string>([[STORAGE_KEY, JSON.stringify({ v: 1, threadId: "t", items: [], last: null, request: null })]]);
  const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: () => {} } as unknown as Storage;
  expect(loadState(storage, () => "n").plan).toBeNull();
  store.set(STORAGE_KEY, JSON.stringify({ v: 1, threadId: "t", items: [], plan: { plan: { days: [] } } }));
  expect(loadState(storage, () => "n").plan?.plan.notes).toEqual([]);
});
