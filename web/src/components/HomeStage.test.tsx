import { render, screen } from "@testing-library/react";
import { ChatProvider } from "./ChatProvider";
import HomeStage from "./HomeStage";
import { initialState, saveState } from "../lib/chatState";
import type { TourCard } from "../lib/chat";

vi.mock("./ResultsPane", () => ({ default: () => <p>results pane</p> }));

const card = { trail_id: "t1", name: "Tour 1", deviation_text: null } as unknown as TourCard;
const photo = { url: "https://img/a.jpg", thumb_url: "https://img/a-t.jpg", author: "Anna", license: "CC BY 4.0", license_url: null, page_url: null };

const withLast = (cards: TourCard[] | null) =>
  saveState(sessionStorage, {
    ...initialState("th"),
    last: cards ? { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } : null,
  });
const show = () =>
  render(
    <ChatProvider>
      <HomeStage photos={[photo]} />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("before results: title, chat and the photo with its credit, no results pane", async () => {
  const { container } = show();
  expect(screen.getByRole("heading", { name: "Wandern im Schwarzwald" })).toBeInTheDocument();
  expect(screen.getByRole("complementary", { name: "Planungs-Chat" })).toBeInTheDocument();
  expect(screen.getByText(/Foto: Anna/)).toBeInTheDocument();
  expect(screen.queryByText("results pane")).toBeNull();
  expect(container.querySelector(".fixed")).toBeNull();
});

it("after results: chat left, results right, no extra button", async () => {
  withLast([card]);
  const { container } = show();
  expect(await screen.findByText("results pane")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Vorschläge zeigen/ })).toBeNull();
  expect(container.querySelector("[class*='md:grid-cols-[24rem_1fr]']")).not.toBeNull();
  expect(screen.queryByText(/Foto: Anna/)).toBeNull();
});

it("empty results keep the start view", () => {
  withLast(null);
  show();
  expect(screen.queryByText("results pane")).toBeNull();
});

it("a plan, also an empty one, shows the results pane", async () => {
  const plan = { plan: { trail_id: "t", trail_name: "T", target_km: 15, days: [], notes: ["x"], source_ids: [] }, weather: {}, rain: {} };
  saveState(sessionStorage, { ...initialState("th"), plan });
  show();
  expect(await screen.findByText("results pane")).toBeInTheDocument();
});
