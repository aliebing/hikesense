import { render, screen, within } from "@testing-library/react";
import { ChatProvider } from "./ChatProvider";
import { initialState, saveState } from "../lib/chatState";
import type { HikeRequest, TourCard } from "../lib/chat";
import ResultsPane from "./ResultsPane";

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

vi.mock("./TourPreview", () => ({ default: ({ card, fallback }: { card: TourCard; fallback?: boolean }) => <p>{fallback ? "fallback " : ""}preview {card.name}</p> }));
vi.mock("./PlanPreview", () => ({ default: () => <p>plan preview</p> }));

const show = () =>
  render(
    <ChatProvider>
      <ResultsPane />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("several tours: heading, chips, tiles linking with von=chat and the narrowing hint", () => {
  seed([mk(1), mk(2), mk(3), mk(4)]);
  show();
  expect(screen.getByRole("heading", { name: "4 Touren gefunden" })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Erkannte Wünsche" })).toHaveTextContent("Länge 10–14 km");
  const links = screen.getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/t/"));
  expect(links.map((l) => l.getAttribute("href"))).toEqual(["/t/t1?von=chat", "/t/t2?von=chat", "/t/t3?von=chat", "/t/t4?von=chat"]);
  expect(screen.getByText(/Zu viele\? Schreib z\. B\./)).toBeInTheDocument();
});

it("at most 6 tiles", () => {
  seed([1, 2, 3, 4, 5, 6, 7, 8].map((n) => mk(n)));
  show();
  expect(screen.getAllByRole("article")).toHaveLength(6);
});

it("fallback note comes before the tiles, each tile shows its deviation", () => {
  const bad = [{ kind: "length_km", ok: false, actual: 15, bound: "≤ 14 km", deviation_rel: 0.1, bound_value: 14 }];
  const fb = "Keine Tour erfüllt alle Wünsche, weil die Länge abweicht";
  seed([mk(1, { results: bad, deviation_text: "15 km statt 14 km" }), mk(2, { results: bad, deviation_text: "16 km statt 14 km" })], fb);
  show();
  const note = screen.getByRole("note");
  expect(note).toHaveTextContent(fb);
  const first = screen.getAllByRole("article")[0];
  expect(note.compareDocumentPosition(first) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  expect(screen.getByText(/16 km statt 14 km/)).toBeInTheDocument();
});

it("exactly one tour: the preview instead of a tile, no narrowing hint", () => {
  seed([mk(1)]);
  show();
  expect(screen.getByText("preview Tour 1")).toBeInTheDocument();
  expect(screen.queryByText(/Zu viele\?/)).toBeNull();
});

it("a plan: the plan preview", () => {
  const plan = { plan: { trail_id: "t", trail_name: "W", target_km: 15, days: [], notes: [], source_ids: [] }, weather: {}, rain: {} };
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  expect(screen.getByText("plan preview")).toBeInTheDocument();
});

it("keeps the chips of its own search after a later knowledge question", () => {
  const cards = [mk(1), mk(2)];
  const other = { constraints: [], preferences: [], unmatched: [] } as unknown as HikeRequest;
  saveState(sessionStorage, {
    ...initialState("th"),
    request: { request: other, labels: {} },
    last: { cards, fallback: null, runWithoutPace: false, labels: {}, request: { request, labels: {} } },
    items: [],
  });
  show();
  expect(within(screen.getByRole("list", { name: "Erkannte Wünsche" })).getByText("Rundweg")).toBeInTheDocument();
});

it("one tour after relaxing a wish: the honest note stays and nothing claims it fits", () => {
  const fb = "Keine Tour erfüllt alle Wünsche, weil die Höhenmeter abweichen";
  seed([mk(1)], fb);
  show();
  expect(screen.getByRole("note")).toHaveTextContent(fb);
  expect(screen.getByText("fallback preview Tour 1")).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Erkannte Wünsche" })).toBeInTheDocument();
});
