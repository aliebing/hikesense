import { render, screen, within } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";
import { ChatProvider } from "./ChatProvider";
import HomeStage from "./HomeStage";
import { initialState, saveState } from "../lib/chatState";
import type { TourCard } from "../lib/chat";

vi.mock("./ResultsPane", () => ({ default: () => <p>results pane</p> }));

const card = { trail_id: "t1", name: "Tour 1", deviation_text: null, cover_url: "https://img/k.jpg", cover_thumb_url: "https://img/k-thumb.jpg", cover_author: "Karl", cover_license: "CC BY 4.0", cover_license_url: null, cover_page_url: "https://commons.wikimedia.org/wiki/File:Blick_ins_Tal.jpg" } as unknown as TourCard;
const lake = { url: "https://img/see.jpg", thumb_url: "https://img/see-t.jpg", author: "Sina", license: "CC BY 4.0", license_url: null, page_url: "https://commons.wikimedia.org/wiki/File:Teufensee.jpg" };

const withLast = (cards: TourCard[] | null) =>
  saveState(sessionStorage, {
    ...initialState("th"),
    last: cards ? { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } : null,
  });
const show = () =>
  render(
    <ChatProvider>
      <HomeStage landscapes={[lake]} />
    </ChatProvider>,
  );

beforeEach(() => sessionStorage.clear());

it("before results: HikeSense hero on the start photo, with the chat as main control", () => {
  const { container } = show();
  const h1 = screen.getByRole("heading", { level: 1, name: "HikeSense" });
  expect(within(h1).getByText("Sense")).toHaveClass("text-sense");
  expect(container.querySelector("svg[data-logo-mark='light']")).not.toBeNull();
  expect(screen.getByText("Plan. Hike. Stay. Explore.")).toBeInTheDocument();
  expect(screen.getByText("Deine intelligente Wanderplattform für Routen, Unterkünfte und alles, was deine Tour besonders macht.")).toBeInTheDocument();
  expect(screen.getByRole("complementary", { name: "Planungs-Chat" })).toBeInTheDocument();
  expect(screen.queryByText("results pane")).toBeNull();
  // the owner's own photo: no credit line, no photo switcher
  expect(container.querySelector("[data-hero-backdrop] img")).toHaveAttribute("src", "/hero/start-1920.webp");
  expect(container.querySelector("[data-hero-backdrop] source")).toHaveAttribute("srcset", "/hero/start-900.webp");
  expect(screen.queryByText(/Foto:/)).toBeNull();
});

it("shows the four features in German", () => {
  show();
  const list = screen.getByRole("list", { name: "Was HikeSense kann" });
  expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    "Wanderrouten entdecken",
    "Passende Unterkünfte finden",
    "Wetter & Bedingungen im Blick",
    "KI-gestützte Tourenempfehlungen",
  ]);
});

it("hero in English", () => {
  renderWithLocale(<ChatProvider><HomeStage /></ChatProvider>, "en");
  expect(screen.getByRole("heading", { level: 1, name: "HikeSense" })).toBeInTheDocument();
  expect(screen.getByText("Your smart hiking planner for routes, places to stay and everything that makes your tour special.")).toBeInTheDocument();
  const list = screen.getByRole("list", { name: "What HikeSense does" });
  expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual([
    "Discover hiking routes",
    "Find matching places to stay",
    "Weather & conditions at a glance",
    "AI-powered tour recommendations",
  ]);
  expect(screen.getByRole("complementary", { name: "Planning chat" })).toBeInTheDocument();
});

it("after results: chat left, results right, no extra button", async () => {
  withLast([card]);
  const { container } = show();
  expect(await screen.findByText("results pane")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: /Vorschläge zeigen/ })).toBeNull();
  expect(container.querySelector("[class*='md:grid-cols-[24rem_1fr]']")).not.toBeNull();
  expect(container.querySelector("[data-hero-backdrop]")).toBeNull();
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

it("after results the first tour's large photo (not the 400 px thumbnail) lies behind the middle, with its credit", async () => {
  withLast([card]);
  const { container } = show();
  await screen.findByText("results pane");
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/k.jpg']")).not.toBeNull();
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/k-thumb.jpg']")).toBeNull();
  expect(screen.getByText(/Hintergrundbild:/)).toHaveTextContent("Hintergrundbild: Karl");
});

it("a card from before cover_url existed still gets its thumbnail as background", async () => {
  withLast([{ ...card, cover_url: undefined } as unknown as TourCard]);
  const { container } = show();
  await screen.findByText("results pane");
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/k-thumb.jpg']")).not.toBeNull();
});

it("a tile photo that is no landscape is not used as background; a pool landscape is", async () => {
  withLast([{ ...card, cover_page_url: "https://commons.wikimedia.org/wiki/File:N26_Maestro.jpg" } as TourCard]);
  const { container } = show();
  await screen.findByText("results pane");
  expect(container.querySelector("[aria-hidden='true'] img[src^='https://img/k']")).toBeNull();
  expect(container.querySelector("[aria-hidden='true'] img[src='https://img/see.jpg']")).not.toBeNull();
});
