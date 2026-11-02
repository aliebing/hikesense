import { stripFallback } from "../../components/ChatMessages";
import { render, screen } from "@testing-library/react";

const h = vi.hoisted(() => ({ id: "s1" as string | null, session: null as null | object, row: null as unknown, error: null as unknown }));
vi.mock("next/navigation", () => ({ useSearchParams: () => ({ get: () => h.id }) }));
vi.mock("../../lib/auth", () => ({
  useSession: () => ({ session: h.session, loading: false }),
  getBrowserSupabase: () => ({
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: h.row, error: h.error }) }) }) }),
  }),
}));
vi.mock("../../components/AccountMenu", () => ({ default: () => null }));
vi.mock("../../components/TourPreview", () => ({ default: ({ card }: { card: { name: string } }) => <p data-testid="preview">{card.name}</p> }));
vi.mock("../../components/MerkenButton", () => ({ default: () => null }));

import GemerktPage from "./page";

const card = (id: string, name: string) => ({
  trail_id: id, name, length_km: 10, ascent_m: 100, duration_h: 3, distance_km: null, cover_thumb_url: null, cover_author: null,
  cover_license: null, cover_license_url: null, cover_page_url: null, results: [], deviation_text: null, preference: { met: [], missing: [], avoided_hit: [] },
});
const payload = (over = {}) => ({
  v: 1, messages: ["Rundweg mit Einkehr"], answer: "Hier sind **zwei** Touren.",
  results: { cards: [card("a", "Feldsee"), card("b", "Titisee")], fallback: null, runWithoutPace: false, labels: {}, request: null }, ...over,
});
const row = (p: unknown, kind = "search") => ({ title: "t", kind, payload: p, created_at: "2026-10-31T10:00:00Z" });

beforeEach(() => {
  h.id = "s1";
  h.session = { user: {} };
  h.row = row(payload());
  h.error = null;
});

it("shows messages, answer and tiles", async () => {
  render(<GemerktPage />);
  expect(await screen.findByText("Rundweg mit Einkehr")).toBeInTheDocument();
  expect(screen.getByText("zwei")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Feldsee" })).toHaveAttribute("href", "/t/a");
  expect(screen.getByRole("link", { name: "Titisee" })).toHaveAttribute("href", "/t/b");
  expect(screen.getByText("Gemerkt am 31.10.2026")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "← Meine Pläne" })).toHaveAttribute("href", "/meine-plaene");
});

it("shows fallback note", async () => {
  h.row = row(payload({ results: { ...payload().results, fallback: "Nichts passt genau" } }));
  render(<GemerktPage />);
  expect(await screen.findByRole("note")).toHaveTextContent("Nichts passt genau");
});

it("shows not found when the row is missing", async () => {
  h.row = null;
  render(<GemerktPage />);
  expect(await screen.findByText("Diese gemerkte Suche gibt es nicht (mehr).")).toBeInTheDocument();
});

it("reports payloads it cannot show", async () => {
  h.row = row({ v: 2 });
  render(<GemerktPage />);
  expect(await screen.findByText("Diese gemerkte Suche lässt sich nicht anzeigen.")).toBeInTheDocument();
});

it("survives malformed content", async () => {
  h.row = row(payload({ messages: [1, "ok"], answer: 5, results: { cards: [null, 3, { ...card("x", "Ohne"), trail_id: undefined }, card("a", "Feldsee"), card("b", "Titisee")], labels: null } }));
  render(<GemerktPage />);
  expect(await screen.findByText("ok")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Feldsee" })).toBeInTheDocument();
});

it("asks to sign in when signed out", () => {
  h.session = null;
  render(<GemerktPage />);
  expect(screen.getByRole("link", { name: "Anmelden" })).toHaveAttribute("href", "/anmelden");
});

it("signed out after loading: the previous search is gone", async () => {
  const { rerender } = render(<GemerktPage />);
  expect(await screen.findByText("Rundweg mit Einkehr")).toBeInTheDocument();
  h.session = null;
  rerender(<GemerktPage />);
  expect(screen.queryByText("Rundweg mit Einkehr")).toBeNull();
  expect(screen.getByRole("link", { name: "Anmelden" })).toBeInTheDocument();
});

it("one card: shows the tour preview, not the grid", async () => {
  h.row = row(payload({ results: { ...payload().results, cards: [card("a", "Feldsee")] } }));
  render(<GemerktPage />);
  expect(await screen.findByTestId("preview")).toHaveTextContent("Feldsee");
  expect(screen.queryByRole("link", { name: "Feldsee" })).toBeNull();
});

it("no usable cards: says so", async () => {
  h.row = row(payload({ results: { ...payload().results, cards: [null] } }));
  render(<GemerktPage />);
  expect(await screen.findByText("Diese gemerkte Suche enthält keine Touren.")).toBeInTheDocument();
});

it("an invalid date does not crash and omits the line", async () => {
  h.row = { ...row(payload()), created_at: "kaputt" };
  render(<GemerktPage />);
  expect(await screen.findByText("Rundweg mit Einkehr")).toBeInTheDocument();
  expect(screen.queryByText(/Gemerkt am/)).toBeNull();
});

it("strips the fallback sentence from the answer", async () => {
  h.row = row(payload({ answer: "Nichts passt genau. Aber das hier.", results: { ...payload().results, fallback: "Nichts passt genau" } }));
  render(<GemerktPage />);
  expect(await screen.findByText("Aber das hier.")).toBeInTheDocument();
  expect(screen.queryByText(/Nichts passt genau\. Aber/)).toBeNull();
});

it("stripFallback handles full, partial and absent sentences", () => {
  expect(stripFallback("A b. Rest", "A b")).toBe("Rest");
  expect(stripFallback("A", "A b")).toBe("");
  expect(stripFallback("Anderes", "A b")).toBe("Anderes");
});
