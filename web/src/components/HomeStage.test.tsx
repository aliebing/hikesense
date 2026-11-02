import { render, screen } from "@testing-library/react";
import { ChatProvider } from "./ChatProvider";
import HomeStage from "./HomeStage";
import { initialState, saveState } from "../lib/chatState";
import type { TourCard } from "../lib/chat";

vi.mock("./ResultsPane", () => ({ default: () => <p>results pane</p> }));

const card = { trail_id: "t1", name: "Tour 1", deviation_text: null, cover_thumb_url: "https://img/k.jpg", cover_author: "Karl", cover_license: "CC BY 4.0", cover_license_url: null, cover_page_url: "https://commons.wikimedia.org/wiki/File:Blick_ins_Tal.jpg" } as unknown as TourCard;
const lake = { url: "https://img/see.jpg", thumb_url: "https://img/see-t.jpg", author: "Sina", license: "CC BY 4.0", license_url: null, page_url: "https://commons.wikimedia.org/wiki/File:Teufensee.jpg" };
const photo = { url: "https://img/a.jpg", thumb_url: "https://img/a-t.jpg", author: "Anna", license: "CC BY 4.0", license_url: null, page_url: null };

const withLast = (cards: TourCard[] | null) =>
  saveState(sessionStorage, {
    ...initialState("th"),
    last: cards ? { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } : null,
  });
const show = () =>
  render(
    <ChatProvider>
      <HomeStage photos={[photo]} landscapes={[lake]} />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("before results: title and chat on the full-screen background photo, with its credit", async () => {
  const { container } = show();
  // white text on the photo gets a dark green field behind it so it stays readable
  expect(screen.getByRole("heading", { name: "Wandern im Schwarzwald" })).toHaveClass("schrift-feld");
  expect(screen.getByRole("complementary", { name: "Planungs-Chat" })).toBeInTheDocument();
  expect(screen.getByText(/Foto: Anna/)).toBeInTheDocument();
  expect(screen.queryByText("results pane")).toBeNull();
  expect(container.querySelector(".fixed img")).toHaveAttribute("src", "https://img/a.jpg");
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

it("after results the first tour's photo lies behind the middle, with its credit", async () => {
  withLast([card]);
  const { container } = show();
  await screen.findByText("results pane");
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/k.jpg']")).not.toBeNull();
  expect(screen.getByText(/Hintergrundbild:/)).toHaveTextContent("Foto: Karl");
});

it("a tile photo that is no landscape is not used as background; a pool landscape is", async () => {
  withLast([{ ...card, cover_page_url: "https://commons.wikimedia.org/wiki/File:N26_Maestro.jpg" } as TourCard]);
  const { container } = show();
  await screen.findByText("results pane");
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/k.jpg']")).toBeNull();
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/see.jpg']")).not.toBeNull();
});
