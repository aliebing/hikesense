import { render, screen } from "@testing-library/react";
import type { TourCard } from "../lib/chat";
import TourResultCard from "./TourResultCard";

const card = (over: Partial<TourCard> = {}): TourCard => ({
  trail_id: "t1",
  name: "Feldsee-Runde",
  length_km: 12.3,
  ascent_m: 450,
  duration_h: 4.5,
  distance_km: 3.2,
  cover_thumb_url: null,
  results: [{ kind: "length_km", ok: true, actual: 12.3, bound: "≤ 15 km", deviation_rel: 0, bound_value: 15 }],
  deviation_text: null,
  preference: { score: 1, met: ["aussicht"], missing: ["see"], avoided_hit: [] },
  ...over,
});

it("shows figures, verdicts, preferences and the tour link", () => {
  render(<TourResultCard card={card()} />);
  expect(screen.getByRole("link", { name: "Feldsee-Runde" })).toHaveAttribute("href", "/t/t1");
  expect(screen.getByText(/12,3 km/)).toBeInTheDocument();
  expect(screen.getByLabelText("erfüllt")).toBeInTheDocument();
  expect(screen.getByText(/Erfüllte Vorlieben: aussicht/)).toBeInTheDocument();
  expect(screen.getByText(/Fehlende Vorlieben: see/)).toBeInTheDocument();
});

it("shows the deviation text for a violated condition", () => {
  const c = card({
    results: [{ kind: "radius_km", ok: false, actual: 18, bound: "≤ 15 km", deviation_rel: 0.2, bound_value: 15 }],
    deviation_text: "18 km entfernt statt ≤ 15 km",
  });
  render(<TourResultCard card={c} />);
  expect(screen.getByLabelText("verletzt")).toBeInTheDocument();
  expect(screen.getByText(/18 km entfernt statt ≤ 15 km/)).toBeInTheDocument();
});

it("never renders 0 for missing ascent", () => {
  const { container } = render(<TourResultCard card={card({ ascent_m: null })} />);
  expect(container).toHaveTextContent("↑ – m");
  expect(container).not.toHaveTextContent("↑ 0 m");
});

it("run without pace shows no walking time, only the pace hint", () => {
  const { container } = render(<TourResultCard card={card({ duration_h: null })} runWithoutPace />);
  expect(container).toHaveTextContent("Zeit: Tempo angeben");
  expect(container).not.toHaveTextContent(/\d:\d\d h/);
});

it("shows nothing about time when it is unknown (hike)", () => {
  const { container } = render(<TourResultCard card={card({ duration_h: null })} />);
  expect(container).not.toHaveTextContent("Zeit");
});
