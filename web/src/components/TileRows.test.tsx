import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TileRows from "./TileRows";
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
  cover: { url: `/p${n}.jpg`, thumb_url: `/t${n}.jpg`, author: "A", license: "CC", license_url: null, page_url: null },
});
const pool = Array.from({ length: 30 }, (_, i) => trail(i));
const card = (id: string, deviation: string | null = null): TourCard => ({
  trail_id: id,
  name: `Name ${id}`,
  length_km: 10,
  ascent_m: 100,
  duration_h: 3,
  distance_km: null,
  cover_thumb_url: "/c.jpg",
  cover_author: "Autor",
  cover_license: "CC BY",
  cover_license_url: null,
  cover_page_url: null,
  results: [],
  deviation_text: deviation,
  preference: { score: 0, met: [], missing: [], avoided_hit: [] },
});

describe("TileRows", () => {
  it("pale tiles are not interactive", () => {
    const { container } = render(<TileRows pool={pool} matches={[]} />);
    expect(screen.queryAllByRole("link", { hidden: true })).toHaveLength(0);
    const tiles = container.querySelectorAll("li");
    expect(tiles.length).toBeGreaterThan(0);
    tiles.forEach((li) => expect(li.closest("[aria-hidden='true']")).not.toBeNull());
  });

  it("matches are links", () => {
    render(<TileRows pool={pool} matches={[card("t2")]} />);
    const link = screen.getByRole("link", { name: "Tour 2" });
    expect(link).toHaveAttribute("href", "/t/t2");
    expect(link.closest("[aria-hidden='true']")).toBeNull();
    // the twin copy is hidden and not focusable
    const twins = screen.getAllByRole("link", { hidden: true });
    expect(twins).toHaveLength(2);
    expect(twins[1]).toHaveAttribute("tabindex", "-1");
  });

  it("fallback tile shows the deviation", () => {
    render(<TileRows pool={pool} matches={[card("neu", "340 Hm statt < 200")]} />);
    expect(screen.getAllByText("340 Hm statt < 200").length).toBeGreaterThan(0);
  });
});
