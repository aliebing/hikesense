import { render, screen } from "@testing-library/react";
import { ChatProvider } from "./ChatProvider";
import HomeStage from "./HomeStage";
import { initialState, saveState } from "../lib/chatState";
import type { TourCard } from "../lib/chat";

const card = { trail_id: "t1", name: "Tour 1", deviation_text: null } as unknown as TourCard;

const withLast = (cards: TourCard[] | null) =>
  saveState(sessionStorage, {
    ...initialState("th"),
    last: cards ? { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } : null,
  });
const show = () =>
  render(
    <ChatProvider>
      <HomeStage />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("no button before results", () => {
  show();
  expect(screen.queryByRole("link", { name: "Vorschläge zeigen →" })).toBeNull();
});

it("button after results", () => {
  withLast([card]);
  show();
  expect(screen.getByRole("link", { name: "Vorschläge zeigen →" })).toHaveAttribute("href", "/vorschlaege");
});

it("empty results hide the button", () => {
  withLast(null);
  show();
  expect(screen.queryByRole("link", { name: "Vorschläge zeigen →" })).toBeNull();
});

it("button for a plan, also an empty one", () => {
  const plan = { plan: { trail_id: "t", trail_name: "T", target_km: 15, days: [], notes: ["x"], source_ids: [] }, weather: {}, rain: {} };
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  expect(screen.getByRole("link", { name: "Vorschläge zeigen →" })).toBeInTheDocument();
});
