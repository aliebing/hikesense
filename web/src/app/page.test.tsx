import { render, screen, within } from "@testing-library/react";
import { renderWithLocale } from "../test-utils";
import type { TrailSummary } from "../lib/data";
import { ChatProvider } from "../components/ChatProvider";

const mockGetTrails = vi.fn();
vi.mock("../lib/data", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../lib/data")>();
  return { ...actual, getTrails: () => mockGetTrails() };
});

// server components read the language from a cookie; there is no request in unit tests
const cookie = vi.hoisted(() => ({ lang: "de" }));
vi.mock("next/headers", () => ({ cookies: async () => ({ get: () => ({ value: cookie.lang }) }) }));

import Home from "./page";

const auth = vi.hoisted(() => ({ session: { access_token: "tok", user: { email: "a@b.de" } } as object | null }));
vi.mock("../lib/auth", async (orig) => ({
  ...(await orig<typeof import("../lib/auth")>()),
  useSession: () => ({ session: auth.session, loading: false }),
  getAccessToken: async () => (auth.session ? "tok" : null),
}));


const trail = (id: string, kind: TrailSummary["kind"], lat: number): TrailSummary => ({
  id,
  name: `Weg ${id}`,
  kind,
  length_km: 10,
  ascent_m: 300,
  descent_m: 300,
  stage_count: kind === "long_distance" ? 25 : 0,
  center_lat: lat,
  cover: {
    url: `https://upload.example/${id}.jpg`,
    thumb_url: `https://upload.example/${id}-t.jpg`,
    author: `Autor ${id}`,
    license: "CC BY 4.0",
    license_url: null,
    page_url: null,
  },
});

beforeEach(() => {
  cookie.lang = "de";
  mockGetTrails.mockReset();
});

test("home shows a clear message when data cannot be loaded", async () => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrails.mockRejectedValue(new Error("no supabase"));
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText(/Daten konnten nicht geladen werden/)).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Nachricht" })).toBeInTheDocument();
  expect(screen.queryAllByRole("link", { hidden: true }).filter((l) => l.getAttribute("href")?.startsWith("/t/"))).toHaveLength(0);
});

test("home explains an empty database", async () => {
  mockGetTrails.mockResolvedValue([]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText(/Noch keine Wege/)).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Nachricht" })).toBeInTheDocument();
  expect(screen.queryAllByRole("link", { hidden: true }).filter((l) => l.getAttribute("href")?.startsWith("/t/"))).toHaveLength(0);
});

test("renders the HikeSense hero and the chat, no tour tiles", async () => {
  mockGetTrails.mockResolvedValue([
    trail("westweg-west", "long_distance", 48.5),
    trail("day-1", "day_hike", 48.1),
  ]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByRole("heading", { level: 1, name: "HikeSense" })).toBeInTheDocument();
  expect(screen.getByRole("textbox", { name: "Nachricht" })).toBeInTheDocument();
  expect(screen.queryAllByRole("link").filter((l) => l.getAttribute("href") === "/t/day-1")).toHaveLength(0);
});

test("menu lists long-distance trails", async () => {
  mockGetTrails.mockResolvedValue([
    trail("westweg-west", "long_distance", 48.5),
    trail("day-1", "day_hike", 48.1),
  ]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  expect(screen.getByText("Fernwege")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Weg westweg-west", hidden: true })).toHaveAttribute("href", "/t/westweg-west");
});

test("home footer: one short line with OSM and elevation credits and a link to all sources", async () => {
  mockGetTrails.mockResolvedValue([trail("day-1", "day_hike", 48.1)]);
  render(<ChatProvider>{await Home()}</ChatProvider>);
  const footer = screen.getByRole("contentinfo");
  expect(footer).toHaveTextContent(/© OpenStreetMap-Mitwirkende\s*Höhen: Copernicus DEM\s*Quellen & Lizenzen/);
  expect(footer).toHaveClass("min-h-10", "w-full", "text-xs", "font-normal", "text-papier/70"); // header width, quiet text
  expect(within(footer).getByRole("link", { name: "© OpenStreetMap-Mitwirkende" })).toHaveAttribute("href", "https://www.openstreetmap.org/copyright");
  expect(within(footer).getByRole("link", { name: "Quellen & Lizenzen" })).toHaveAttribute("href", "/quellen");
});

test("English: heading, footer and data error come in English", async () => {
  cookie.lang = "en";
  mockGetTrails.mockResolvedValue([trail("w", "long_distance", 48), trail("a", "day_hike", 47.9)]);
  renderWithLocale(<ChatProvider>{await Home()}</ChatProvider>, "en");
  expect(screen.getByRole("heading", { level: 1, name: "HikeSense" })).toBeInTheDocument();
  expect(screen.getByText("Discover hiking routes")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Sources & licences" })).toHaveAttribute("href", "/quellen");
  expect(screen.getByRole("textbox", { name: "Message" })).toHaveAttribute("placeholder", "Where, how far, what matters to you?");

  vi.spyOn(console, "error").mockImplementation(() => {});
  mockGetTrails.mockRejectedValue(new Error("no supabase"));
  renderWithLocale(<ChatProvider>{await Home()}</ChatProvider>, "en");
  expect(screen.getByText("Data could not be loaded.")).toBeInTheDocument();
  expect(screen.getByText(/The database cannot be reached/)).toBeInTheDocument();
});
