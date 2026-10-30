import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatProvider } from "./ChatProvider";
import HomeStage from "./HomeStage";
import { initialState, saveState } from "../lib/chatState";
import type { TrailSummary } from "../lib/data";
import type { TourCard } from "../lib/chat";

const trail = (n: number): TrailSummary => ({
  id: `t${n}`,
  name: `Tour ${n}`,
  kind: "day_hike",
  length_km: 10,
  ascent_m: 100,
  descent_m: 100,
  stage_count: 1,
  center_lat: 48,
  cover: { url: `/p${n}.jpg`, thumb_url: `/t${n}.jpg`, author: `Autor ${n}`, license: `Lizenz ${n}`, license_url: `https://l/${n}`, page_url: `https://c/${n}` },
});
const pool = Array.from({ length: 24 }, (_, i) => trail(i));
const card = { trail_id: "t1", name: "Tour 1", deviation_text: null } as unknown as TourCard;

const withLast = (cards: TourCard[] | null) =>
  saveState(sessionStorage, {
    ...initialState("th"),
    last: cards ? { cards, fallback: null, runWithoutPace: false, labels: {}, request: null } : null,
  });
const show = () =>
  render(
    <ChatProvider>
      <HomeStage pool={pool} />
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

it("credits list visible tile photos", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Bildnachweise" }));
  const dialog = screen.getByRole("dialog", { name: "Bildnachweise" });
  expect(dialog).toHaveTextContent("Autor 0");
  expect(dialog).toHaveTextContent("Lizenz 0");
  expect(screen.getByRole("link", { name: "Lizenz 0" })).toHaveAttribute("href", "https://l/0");
  await userEvent.keyboard("{Escape}");
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("credits dialog takes focus and gives it back on close", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Bildnachweise" }));
  expect(screen.getByRole("button", { name: "Schließen" })).toHaveFocus();
  await userEvent.keyboard("{Escape}");
  expect(screen.getByRole("button", { name: "Bildnachweise" })).toHaveFocus();
});

it("credits dialog closes on a click on the backdrop", async () => {
  show();
  await userEvent.click(screen.getByRole("button", { name: "Bildnachweise" }));
  await userEvent.click(screen.getByRole("dialog").parentElement!);
  expect(screen.queryByRole("dialog")).toBeNull();
});
