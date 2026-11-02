const h = vi.hoisted(() => ({
  insert: vi.fn(),
  order: vi.fn(),
  eq: vi.fn(),
  from: vi.fn(),
}));
vi.mock("./auth", () => ({ getBrowserSupabase: () => ({ from: h.from }) }));

import { deletePlan, isSavedSearch, listPlans, savePlan, savedSearchOf, searchTitle } from "./plans";
import { initialState, type ChatState, type LastResults } from "./chatState";
import type { ChatItem } from "../components/ChatMessages";
import type { TourCard } from "./chat";

beforeEach(() => {
  vi.clearAllMocks();
  h.from.mockImplementation(() => ({
    insert: h.insert,
    select: () => ({ order: h.order }),
    delete: () => ({ eq: h.eq }),
  }));
});

it("saves the card payload unchanged", async () => {
  h.insert.mockResolvedValue({ error: null });
  const payload = { trail_id: "t1", name: "Feldsee-Runde", length_km: 12.3 };
  expect(await savePlan("day_hike", "Feldsee-Runde", payload)).toEqual({ error: null });
  expect(h.from).toHaveBeenCalledWith("saved_plans");
  expect(h.insert).toHaveBeenCalledWith({ kind: "day_hike", title: "Feldsee-Runde", payload });
  expect(h.insert.mock.calls[0][0].payload).toBe(payload);
});

it("reports a German error when saving fails", async () => {
  h.insert.mockResolvedValue({ error: { message: "boom" } });
  expect((await savePlan("multiday", "x", {})).error).toMatch(/Merken/);
  h.insert.mockRejectedValue(new Error("offline"));
  expect((await savePlan("multiday", "x", {})).error).toMatch(/Merken/);
});

it("lists and deletes own plans", async () => {
  const rows = [{ id: "p1", kind: "day_hike", title: "A", payload: {}, created_at: "2026-10-30T10:00:00Z" }];
  h.order.mockResolvedValue({ data: rows, error: null });
  expect(await listPlans()).toEqual({ plans: rows, error: null });
  expect(h.order).toHaveBeenCalledWith("created_at", { ascending: false });
  h.eq.mockResolvedValue({ error: null });
  expect(await deletePlan("p1")).toEqual({ error: null });
  expect(h.eq).toHaveBeenCalledWith("id", "p1");
});

it("list failure gives an empty list and a message", async () => {
  h.order.mockResolvedValue({ data: null, error: { message: "x" } });
  const r = await listPlans();
  expect(r.plans).toEqual([]);
  expect(r.error).toMatch(/geladen/);
});

const card = (id: string) => ({ trail_id: id, name: id }) as unknown as TourCard;
const res = (n: number): ChatItem => ({ kind: "results", cards: Array.from({ length: n }, (_, i) => card("t" + i)), fallback: null, runWithoutPace: false, labels: {} });
const stateOf = (items: ChatItem[], last: Partial<LastResults> | null = {}): ChatState => ({
  ...initialState("th"),
  items,
  last: last && { cards: [card("a"), card("b")], fallback: null, runWithoutPace: false, labels: {}, request: null, ...last },
});

it("savedSearchOf returns null without results", () => {
  expect(savedSearchOf(stateOf([{ kind: "user", text: "x" }], null))).toBeNull();
});

it("savedSearchOf collects the messages including refinements", () => {
  const s = savedSearchOf(
    stateOf([
      { kind: "user", text: "Feldberg 15 km" }, res(1), { kind: "assistant", text: "Eine" },
      { kind: "user", text: "mit Einkehr" }, res(2), { kind: "assistant", text: "Zwei Touren …" },
    ]),
  )!;
  expect(s.v).toBe(1);
  expect(s.messages).toEqual(["Feldberg 15 km", "mit Einkehr"]);
  expect(s.answer).toBe("Zwei Touren …");
  expect(s.results.cards.length).toBe(2);
});

it("savedSearchOf ignores messages after the last result", () => {
  const s = savedSearchOf(
    stateOf([
      { kind: "user", text: "Feldberg" }, res(2), { kind: "assistant", text: "Antwort" },
      { kind: "user", text: "Was ist der Schwarzwaldverein?" }, { kind: "assistant", text: "Verein" },
    ]),
  )!;
  expect(s.messages).toEqual(["Feldberg"]);
  expect(s.answer).toBe("Antwort");
});

it("savedSearchOf keeps fallback", () => {
  const f = "Keine Tour erfüllt alle Wünsche …";
  expect(savedSearchOf(stateOf([{ kind: "user", text: "x" }, res(1)], { fallback: f }))!.results.fallback).toBe(f);
});

it("searchTitle joins, truncates and falls back", () => {
  const r = {} as LastResults;
  expect(searchTitle({ v: 1, messages: ["Feldberg 15 km", "mit Einkehr"], answer: "", results: r })).toBe("Feldberg 15 km · mit Einkehr");
  const t = searchTitle({ v: 1, messages: ["x".repeat(200)], answer: "", results: r });
  expect(t.length).toBe(80);
  expect(t.endsWith("…")).toBe(true);
  expect(searchTitle({ v: 1, messages: [], answer: "", results: r })).toBe("Gemerkte Suche");
});

it("isSavedSearch rejects day_hike payloads", () => {
  expect(isSavedSearch({ trail_id: "t1" })).toBe(false);
  expect(isSavedSearch(null)).toBe(false);
  expect(isSavedSearch({ v: 1, messages: [], answer: "", results: { cards: [] } })).toBe(true);
});

it("savePlan inserts kind search", async () => {
  h.insert.mockResolvedValue({ error: null });
  await savePlan("search", "t", { v: 1 });
  expect(h.insert).toHaveBeenCalledWith({ kind: "search", title: "t", payload: { v: 1 } });
});
