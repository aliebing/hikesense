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
  cover_author: null,
  cover_license: null,
  cover_license_url: null,
  cover_page_url: null,
  results: [{ kind: "length_km", ok: true, actual: 12.3, bound: "höchstens 15", deviation_rel: 0, bound_value: 15 }],
  deviation_text: null,
  preference: { score: 1, met: ["aussicht"], missing: ["see"], avoided_hit: [] },
  ...over,
});

it("missing length shows unbekannt, never 0", () => {
  const { container } = render(<TourResultCard card={card({ length_km: null })} />);
  expect(container).toHaveTextContent("Länge: unbekannt");
  expect(container).not.toHaveTextContent("0 km");
});

it("uses vocabulary labels for preferences, tag id only as fallback", () => {
  render(<TourResultCard card={card()} labels={{ aussicht: "Aussicht" }} />);
  expect(screen.getByText(/Erfüllte Vorlieben: Aussicht/)).toBeInTheDocument();
  expect(screen.getByText(/Fehlende Vorlieben: see/)).toBeInTheDocument();
});

it("shows the cover with author and licence, but not without attribution data", () => {
  const withCover = card({
    cover_thumb_url: "https://img/t.jpg",
    cover_author: "Anna",
    cover_license: "CC BY 4.0",
    cover_license_url: "https://cc/by",
    cover_page_url: "https://commons/p",
  });
  const { container, unmount } = render(<TourResultCard card={withCover} />);
  expect(container.querySelector("img")).toHaveAttribute("src", "https://img/t.jpg");
  expect(screen.getByText(/Anna/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "CC BY 4.0" })).toHaveAttribute("href", "https://cc/by");
  unmount();
  const noAttr = render(<TourResultCard card={card({ cover_thumb_url: "https://img/t.jpg" })} />);
  expect(noAttr.container.querySelector("img")).toBeNull();
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
  expect(container).toHaveTextContent("Höhenmeter: unbekannt");
  expect(container).not.toHaveTextContent(/↑ 0|0 m/);
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

it("area start: says 'im Gebiet' instead of a distance", () => {
  const { container } = render(<TourResultCard card={card({ distance_km: null })} />);
  expect(container).toHaveTextContent("im Gebiet");
  expect(container).not.toHaveTextContent("Entfernung");
});

it("verdict rows carry the unit of the bound", () => {
  const results = [
    { kind: "length_km", ok: true, actual: 12, bound: "mindestens 10 und höchstens 14", deviation_rel: 0, bound_value: null },
    { kind: "ascent_m", ok: null, actual: null, bound: "höchstens 400", deviation_rel: 1, bound_value: null },
    { kind: "roundtrip", ok: true, actual: true, bound: "Rundweg", deviation_rel: 0, bound_value: null },
  ];
  const { container } = render(<TourResultCard card={card({ results })} />);
  expect(container).toHaveTextContent("Länge: mindestens 10 und höchstens 14 km");
  expect(container).toHaveTextContent("Höhenmeter: unbekannt, nicht prüfbar (höchstens 400 Hm)");
  expect(container).toHaveTextContent("Rundweg: Rundweg");
  expect(container).not.toHaveTextContent("Rundweg km");
});

it("from=vorschlaege links with ?von and makes the whole card clickable, large has a bigger image", () => {
  const withCover = card({ cover_thumb_url: "https://img/t.jpg", cover_author: "Anna", cover_license: "CC BY 4.0" });
  const { container } = render(<TourResultCard card={withCover} size="large" from="vorschlaege" />);
  const link = screen.getByRole("link", { name: "Feldsee-Runde" });
  expect(link).toHaveAttribute("href", "/t/t1?von=vorschlaege");
  expect(link.className).toContain("after:inset-0");
  expect(container.querySelector("img")?.className).toContain("h-48");
});
