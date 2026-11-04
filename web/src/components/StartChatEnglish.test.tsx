import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatProvider } from "./ChatProvider";
import ChatShell from "./ChatShell";
import HomeStage from "./HomeStage";
import ResultsPane from "./ResultsPane";
import TourResultCard from "./TourResultCard";
import LanguageFlags from "./LanguageFlags";
import { initialState, saveState } from "../lib/chatState";
import { renderWithLocale } from "../test-utils";
import type { HikeRequest, TourCard } from "../lib/chat";

const auth = vi.hoisted(() => ({ session: { access_token: "tok", user: { email: "a@b.de" } } as object | null }));
vi.mock("../lib/auth", async (orig) => ({
  ...(await orig<typeof import("../lib/auth")>()),
  useSession: () => ({ session: auth.session, loading: false }),
  getAccessToken: async () => (auth.session ? "tok" : null),
}));

const tour = (over: Partial<TourCard> = {}): TourCard =>
  ({
    trail_id: "t1", name: "Feldsee-Runde", length_km: 12.3, ascent_m: 1450, duration_h: 4.5, distance_km: 3.2,
    cover_thumb_url: null, cover_author: null, cover_license: null, cover_license_url: null, cover_page_url: null,
    results: [{ kind: "roundtrip", ok: true, actual: 1, bound: "Rundweg", deviation_rel: 0, bound_value: 1 }, { kind: "ascent_m", ok: false, actual: 1450, bound: "höchstens 1400", deviation_rel: 0.04, bound_value: 1400 }],
    deviation_text: "50 m zu viel Anstieg", near_miss: true,
    preference: { score: 0, met: ["aussicht"], missing: [], avoided_hit: [] }, ...over,
  }) as unknown as TourCard;

const request = {
  constraints: [
    { kind: "roundtrip", required: true, min: null, max: null, approx: null },
    { kind: "length_km", required: null, min: 10, max: 14, approx: null },
  ],
  preferences: [],
  unmatched: [],
} as unknown as HikeRequest;

const seed = () =>
  saveState(sessionStorage, {
    ...initialState("th"),
    request: { request, labels: {} },
    last: { cards: [tour(), tour({ trail_id: "t2", name: "Zweite", near_miss: false })], fallback: null, runWithoutPace: false, labels: {}, request: { request, labels: {} } },
    items: [
      { kind: "user", text: "Rundweg" },
      { kind: "results", cards: [tour(), tour({ trail_id: "t2", name: "Zweite", near_miss: false })], fallback: null, runWithoutPace: false, labels: {} },
      { kind: "assistant", text: "Antwort vom Backend" },
    ],
  });

beforeEach(() => {
  sessionStorage.clear();
  auth.session = { access_token: "tok", user: { email: "a@b.de" } };
});

it("start page: English heading and chat placeholder", () => {
  renderWithLocale(<ChatProvider><HomeStage /></ChatProvider>, "en");
  expect(screen.getByRole("heading", { level: 1, name: "HikeSense" })).toBeInTheDocument();
  expect(screen.getByText("Your smart hiking planner for routes, places to stay and everything that makes your tour special.")).toBeInTheDocument();
  expect(screen.getByRole("complementary", { name: "Planning chat" })).toBeInTheDocument();
  expect(screen.getByPlaceholderText("Where, how far, what matters to you?")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Send" })).toBeInTheDocument();
});

it("signed out: a guest gets the English input, no sign-in gate", () => {
  auth.session = null;
  renderWithLocale(<ChatProvider><ChatShell intro="Hi" /></ChatProvider>, "en");
  expect(screen.getByLabelText("Message")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "sign in" })).toBeNull();
});

it("result tile: round walk, ascent, Near miss and Save result", () => {
  auth.session = { access_token: "tok", user: { email: "a@b.de" } };
  renderWithLocale(<TourResultCard card={tour()} />, "en");
  const tile = screen.getByRole("article");
  expect(within(tile).getByText("Near miss")).toBeInTheDocument();
  // backend deviation text stays as delivered, only the suffix is English
  expect(within(tile).getByText("50 m zu viel Anstieg – everything else fits")).toBeInTheDocument();
  expect(within(tile).getByText(/Round walk/)).toBeInTheDocument();
  expect(within(tile).getByText(/Ascent/)).toBeInTheDocument();
  expect(tile).toHaveTextContent("12.3 km · ↑ 1,450 m · Time: 4:30 h · Distance: 3.2 km");
});

it("results pane: Save result, English found text and hint", () => {
  seed();
  renderWithLocale(<ChatProvider><ResultsPane /></ChatProvider>, "en");
  expect(screen.getByRole("button", { name: "Save result" })).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "1 tour found, 1 near miss" })).toBeInTheDocument();
  expect(screen.getByRole("list", { name: "Your criteria" })).toHaveTextContent("Round walk");
  expect(screen.getByText(/Too many\?/)).toBeInTheDocument();
});

it("switching the language mid-chat keeps messages and results", async () => {
  seed();
  renderWithLocale(<ChatProvider><LanguageFlags /><ChatShell intro="Hi" /><ResultsPane /></ChatProvider>, "en");
  expect(await screen.findByText("Antwort vom Backend")).toBeInTheDocument();
  expect(screen.getByLabelText("Message")).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  expect(screen.getByLabelText("Nachricht")).toBeInTheDocument();
  expect(screen.getByText("Antwort vom Backend")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "1 Tour gefunden, 1 knapp daneben" })).toBeInTheDocument();
  expect(screen.getAllByText("Zweite").length).toBeGreaterThan(0);
});
