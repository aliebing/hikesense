import { render, screen } from "@testing-library/react";
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
    last: { cards, fallback, runWithoutPace: false, labels: {} },
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
  expect(screen.getByText("15 km statt 14 km")).toBeInTheDocument();
  expect(screen.getByText("16 km statt 14 km")).toBeInTheDocument();
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
