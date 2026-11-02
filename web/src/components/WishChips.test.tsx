import { renderWithLocale } from "../test-utils";
import { render, screen } from "@testing-library/react";
import type { TourCard } from "../lib/chat";
import { initialState, saveState } from "../lib/chatState";
import { ChatProvider } from "./ChatProvider";
import WishChips from "./WishChips";

const card = (trail_id: string): TourCard => ({
  trail_id,
  name: "T",
  length_km: 10,
  ascent_m: 200,
  duration_h: 3,
  distance_km: 1,
  cover_thumb_url: null,
  cover_author: null,
  cover_license: null,
  cover_license_url: null,
  cover_page_url: null,
  results: [
    { kind: "roundtrip", ok: true, actual: null, bound: "Rundweg", deviation_rel: null, bound_value: null },
    { kind: "ascent_m", ok: false, actual: 450, bound: "höchstens 400", deviation_rel: 0.12, bound_value: 400 },
  ],
  deviation_text: null,
  preference: { met: [], missing: [], avoided_hit: [] },
} as unknown as TourCard);

const show = (cards: TourCard[] | null) => {
  sessionStorage.clear();
  saveState(sessionStorage, { ...initialState("th"), last: cards && { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } });
  return render(
    <ChatProvider>
      <WishChips trailId="t1" />
    </ChatProvider>,
  );
};

it("shows the verdicts of the chat card for this tour", async () => {
  show([card("t1")]);
  expect(await screen.findByText("✓ Rundweg")).toBeInTheDocument();
  expect(screen.getByText("✗ Höhenmeter: höchstens 400 Hm")).toBeInTheDocument();
});

it("shows nothing when the tour is not in the chat (shared link)", () => {
  const { container } = show([card("other")]);
  expect(container).toBeEmptyDOMElement();
  show(null);
});

it("English: a round walk chip is label and tick without the German bound", async () => {
  sessionStorage.clear();
  saveState(sessionStorage, { ...initialState("th"), last: { cards: [card("t1")], fallback: null, runWithoutPace: false, labels: {}, request: null } });
  renderWithLocale(<ChatProvider><WishChips trailId="t1" /></ChatProvider>, "en");
  expect(await screen.findByText("✓ Round walk")).toBeInTheDocument();
  expect(screen.queryByText(/Rundweg/)).toBeNull();
});
