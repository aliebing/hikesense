import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithLocale } from "../test-utils";
import LanguageFlags from "./LanguageFlags";
import type { TourCard } from "../lib/chat";
import type { TrailDetail } from "../lib/data";

const h = vi.hoisted(() => ({ getTrail: vi.fn(), getLodgings: vi.fn(), getPois: vi.fn(), getTags: vi.fn() }));
vi.mock("../lib/data", async (orig) => ({
  ...(await orig<typeof import("../lib/data")>()),
  getTrail: h.getTrail,
  getLodgings: h.getLodgings,
  getTrailPois: h.getPois,
  getTrailTags: h.getTags,
}));
vi.mock("./TrailMap", () => ({ default: (p: { embedded?: boolean }) => <p>map {p.embedded ? "embedded" : ""}</p> }));
vi.mock("../lib/auth", () => ({
  checkBlocked: async () => false,
  onBlocked: () => () => {},
  reportBlocked: () => {}, useSession: () => ({ session: null, loading: false }) }));

import TourPreview from "./TourPreview";

const card = {
  trail_id: "day-1", name: "Feldsee-Runde", length_km: 10, ascent_m: 300, duration_h: 3.3, distance_km: 1.2,
  cover_thumb_url: null, cover_author: null, cover_license: null, cover_license_url: null, cover_page_url: null,
  results: [], deviation_text: null, preference: { met: [], missing: [], avoided_hit: [] },
} as unknown as TourCard;

const detail = {
  id: "day-1", name: "Feldsee-Runde", kind: "day_hike", length_km: 10, ascent_m: 300, descent_m: 300, stage_count: 0,
  center_lat: 48, cover: null, stages: [], photos: [], geom: { type: "LineString", coordinates: [[8, 48], [8.1, 48.1]] }, sources: [],
} as TrailDetail;

beforeEach(() => {
  vi.spyOn(console, "error").mockImplementation(() => {});
  h.getTrail.mockReset().mockResolvedValue(detail);
  h.getLodgings.mockReset().mockResolvedValue([]);
  h.getPois.mockReset().mockResolvedValue([{ id: 1, name: "Café", kind: "food", dist_m: 10, along_km: 2, lon: 8, lat: 48 }]);
  h.getTags.mockReset().mockResolvedValue(["feature:rundweg"]);
});

it("shows the tour with description from data, an embedded map and the way to the tour page", async () => {
  render(<TourPreview card={card} runWithoutPace={false} labels={{}} />);
  expect(screen.getByRole("heading", { name: "Feldsee-Runde" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zur Tour →" })).toHaveAttribute("href", "/t/day-1?von=chat");
  expect(await screen.findByText("Rundweg, 10,0 km mit 300 m Aufstieg, Gehzeit etwa 3:18 h nach DIN 33466. Unterwegs 1 Einkehrmöglichkeit.")).toBeInTheDocument();
  expect(screen.getByText("map embedded")).toBeInTheDocument();
});

it("when the trail does not load: says so and keeps the link", async () => {
  h.getTrail.mockRejectedValue(new Error("down"));
  render(<TourPreview card={card} runWithoutPace={false} labels={{}} />);
  expect(await screen.findByText("Karte konnte nicht geladen werden.")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Zur Tour →" })).toBeInTheDocument();
});

it("after a relaxed search it does not claim the tour fits", () => {
  render(<TourPreview card={card} runWithoutPace={false} labels={{}} fallback />);
  expect(screen.queryByText("Eine Tour passt")).toBeNull();
  expect(screen.getByText("Nächstbeste Tour")).toBeInTheDocument();
});

it("a language switch rewrites the sentence without fetching again", async () => {
  renderWithLocale(<><LanguageFlags /><TourPreview card={card} runWithoutPace={false} labels={{}} /></>, "en");
  expect(await screen.findByText(/^Round walk, 10\.0 km with 300 m ascent/)).toBeInTheDocument();
  await userEvent.click(screen.getByRole("button", { name: "Deutsch" }));
  await waitFor(() => expect(screen.getByText(/^Rundweg, 10,0 km mit 300 m Aufstieg/)).toBeInTheDocument());
  expect(h.getTrail).toHaveBeenCalledTimes(1);
  expect(h.getPois).toHaveBeenCalledTimes(1);
});
