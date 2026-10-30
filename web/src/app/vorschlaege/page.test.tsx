import { render, screen, within } from "@testing-library/react";
import { ChatProvider } from "../../components/ChatProvider";
import { initialState, saveState } from "../../lib/chatState";
import type { HikeRequest, TourCard } from "../../lib/chat";
import Vorschlaege from "./page";

const mk = (n: number, over: Partial<TourCard> = {}) =>
  ({ trail_id: `t${n}`, name: `Tour ${n}`, length_km: 12, ascent_m: 100, duration_h: 4, distance_km: null,
    cover_thumb_url: null, cover_author: null, cover_license: null, cover_license_url: null, cover_page_url: null,
    results: [], deviation_text: null, preference: { score: 0, met: [], missing: [], avoided_hit: [] }, ...over }) as TourCard;

const request = {
  constraints: [
    { kind: "roundtrip", required: true, min: null, max: null, approx: null },
    { kind: "length_km", required: null, min: 10, max: 14, approx: null },
  ],
  preferences: [],
  unmatched: [],
} as unknown as HikeRequest;

const seed = (cards: TourCard[], fallback: string | null = null, text = "Hier sind drei Touren.") =>
  saveState(sessionStorage, {
    ...initialState("th"),
    request: { request, labels: {} },
    last: { cards, fallback, runWithoutPace: false, labels: {}, request: { request, labels: {} } },
    items: [
      { kind: "user", text: "Rundweg" },
      { kind: "results", cards, fallback, runWithoutPace: false, labels: {} },
      { kind: "assistant", text },
    ],
  });
const show = () =>
  render(
    <ChatProvider>
      <Vorschlaege />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("shows chips, sentence and cards", () => {
  seed([mk(1), mk(2), mk(3)]);
  show();
  expect(screen.getByRole("list", { name: "Erkannte Wünsche" })).toHaveTextContent("Rundweg");
  expect(screen.getByRole("list", { name: "Erkannte Wünsche" })).toHaveTextContent("Länge 10–14 km");
  expect(screen.getAllByText("Hier sind drei Touren.").length).toBeGreaterThan(0);
  const links = screen.getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/t/"));
  expect(links.map((l) => l.getAttribute("href"))).toEqual(["/t/t1?von=vorschlaege", "/t/t2?von=vorschlaege", "/t/t3?von=vorschlaege"]);
});

it("fallback note first, each card shows its deviation", () => {
  const bad = [{ kind: "length_km", ok: false, actual: 15, bound: "≤ 14 km", deviation_rel: 0.1, bound_value: 14 }];
  const fb = "Keine Tour erfüllt alle Wünsche, weil die Länge abweicht";
  seed([mk(1, { results: bad, deviation_text: "15 km statt 14 km" }), mk(2, { results: bad, deviation_text: "16 km statt 14 km" })], fb);
  show();
  const note = screen.getAllByRole("note")[0]; // the drawer history repeats it further down
  expect(note).toHaveTextContent(fb);
  const first = screen.getAllByRole("article")[0];
  expect(note.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText(/15 km statt 14 km/)).toBeInTheDocument();
  expect(screen.getByText(/16 km statt 14 km/)).toBeInTheDocument();
});

it("without results shows a hint", () => {
  show();
  expect(screen.getByText("Noch keine Vorschläge.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zur Startseite" })).toHaveAttribute("href", "/");
  expect(screen.queryAllByRole("article")).toHaveLength(0);
});

it("chat drawer is present", () => {
  seed([mk(1)]);
  const { container } = show();
  expect(container.querySelector("details > summary")).toHaveTextContent("Chat");
});

it("keeps the chips and sentence of its own search after a later knowledge question", () => {
  const cards = [mk(1)];
  const other = { constraints: [], preferences: [], unmatched: [] } as unknown as HikeRequest;
  saveState(sessionStorage, {
    ...initialState("th"),
    request: { request: other, labels: {} },
    last: { cards, fallback: null, runWithoutPace: false, labels: {}, request: { request, labels: {} } },
    items: [
      { kind: "user", text: "Rundweg" },
      { kind: "results", cards, fallback: null, runWithoutPace: false, labels: {} },
      { kind: "assistant", text: "Hier ist eine Tour." },
      { kind: "user", text: "Wie ist der Westweg markiert?" },
      { kind: "understood", text: "t", request: other, labels: {} },
      { kind: "assistant", text: "Der Westweg ist rot markiert." },
    ],
  });
  show();
  const main = screen.getByRole("main");
  expect(within(main).getByRole("list", { name: "Erkannte Wünsche" })).toHaveTextContent("Rundweg");
  expect(main).toHaveTextContent("Hier ist eine Tour.");
  expect(main).not.toHaveTextContent("Der Westweg ist rot markiert.");
});

it("shows the plan days instead of tour cards when a plan is set", () => {
  const day = { day: 1, date: null, start_km: 0, end_km: 15, walk_km: 15, access_km: 0, length_km: 15, ascent_m: 1, descent_m: 1, duration_h: 4, start_time: "09:00:00", arrival: "13:00:00", stop: null, gap: null, within_band: true };
  const plan = { plan: { trail_id: "t", trail_name: "Westweg", target_km: 15, days: [day], notes: ["Der Weg endet hier."], source_ids: [] }, weather: {}, rain: {} };
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  expect(screen.getByRole("list", { name: "Tage" })).toHaveTextContent("Tag 1");
  expect(screen.getByRole("note")).toHaveTextContent("Der Weg endet hier.");
  expect(screen.queryByText("Noch keine Vorschläge.")).toBeNull();
});
