import { render, screen } from "@testing-library/react";
import StageCards from "./StageCards";
import type { TrailDetail } from "../lib/data";

const trail: TrailDetail = {
  id: "w", name: "W", kind: "long_distance", length_km: 50, ascent_m: 900, descent_m: 900,
  stage_count: 2, center_lat: 48, cover: null, geom: null, photos: [], sources: [],
  stages: [
    { id: "w-01", seq: 1, name: "A – B", start_name: "A", end_name: "B", length_km: 12, ascent_m: 600, descent_m: 600, geom: null, photos: [] },
    { id: "w-02", seq: 2, name: "B – C", start_name: "B", end_name: "C", length_km: null, ascent_m: 300, descent_m: null, geom: null, photos: [] },
  ],
};

test("stage with missing numbers shows dashes and no walking time", () => {
  render(<StageCards trail={trail} />);
  const [full, partial] = screen.getAllByRole("article");
  expect(full).toHaveTextContent("12,0 km · ↑ 600 m · ↓ 600 m · 4:42 h");
  expect(partial).toHaveTextContent("– km · ↑ 300 m · ↓ – m");
  expect(partial).not.toHaveTextContent(/\d:\d\d h/);
  expect(partial).not.toHaveTextContent("0,0 km");
});
