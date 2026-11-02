import { describe, expect, it } from "vitest";
import type { TrailPoi } from "./data";
import { describeTour, surfaceLine, tagLabels } from "./tour";

const poi = (kind: TrailPoi["kind"], id = 1): TrailPoi => ({ id, name: null, kind, dist_m: 50, along_km: 1, lon: 8, lat: 48 });

describe("describeTour", () => {
  it("describes a round trip with stops", () => {
    expect(
      describeTour({ roundtrip: true, length_km: 11.4, ascent_m: 389, time: "3:54 h", pois: [poi("food", 1), poi("hut", 2), poi("viewpoint", 3)] }),
    ).toBe("Rundweg, 11,4 km mit 389 m Aufstieg, Gehzeit etwa 3:54 h nach DIN 33466. Unterwegs 2 Einkehrmöglichkeiten und 1 Aussichtspunkt.");
  });

  it("leaves out what is missing and never says 0", () => {
    expect(describeTour({ roundtrip: false, length_km: 8, ascent_m: null, time: null, pois: [] })).toBe("Tour, 8,0 km.");
    expect(describeTour({ roundtrip: false, length_km: null, ascent_m: null, time: null, pois: [] })).toBeNull();
  });

  it("counts peaks as Aussichtspunkte and names waterfalls", () => {
    expect(describeTour({ roundtrip: false, length_km: 5, ascent_m: 100, time: null, pois: [poi("peak", 1), poi("waterfall", 2)] })).toBe(
      "Tour, 5,0 km mit 100 m Aufstieg. Unterwegs 1 Aussichtspunkt und 1 Wasserfall.",
    );
  });

  it("joins three groups with comma and und, plural forms", () => {
    expect(
      describeTour({
        roundtrip: false,
        length_km: 5,
        ascent_m: null,
        time: null,
        pois: [poi("food", 1), poi("viewpoint", 2), poi("peak", 3), poi("waterfall", 4), poi("waterfall", 5)],
      }),
    ).toBe("Tour, 5,0 km. Unterwegs 1 Einkehrmöglichkeit, 2 Aussichtspunkte und 2 Wasserfälle.");
  });
});

describe("surfaceLine", () => {
  it("sorts, rounds and drops small shares", () => {
    expect(surfaceLine({ paved: 0.2, gravel: 0.287, unknown: 0.368, unpaved: 0.15 })).toBe(
      "Belag: 37 % unbekannt · 29 % Schotter · 20 % Asphalt · 15 % naturbelassen",
    );
    expect(surfaceLine({ paved: 0.97, gravel: 0.03 })).toBe("Belag: 97 % Asphalt");
    expect(surfaceLine(null)).toBeNull();
    expect(surfaceLine({})).toBeNull();
  });
});

describe("tagLabels", () => {
  it("drops unknown ids", () => {
    expect(tagLabels(["feature:rundweg", "x:y", "surface:naturweg"])).toEqual(["Rundweg", "Naturweg"]);
  });
});

describe("English", () => {
  it("describes a round walk with stops", () => {
    expect(
      describeTour({ roundtrip: true, length_km: 11.4, ascent_m: 389, time: "3:54 h", pois: [poi("food", 1), poi("hut", 2), poi("viewpoint", 3)] }, "en"),
    ).toBe("Round walk, 11.4 km with 389 m ascent, walking time about 3:54 h to DIN 33466. Along the way: 2 refreshment stops and 1 viewpoint.");
    expect(describeTour({ roundtrip: false, length_km: 8, ascent_m: null, time: null, pois: [] }, "en")).toBe("Walk, 8.0 km.");
    expect(
      describeTour({ roundtrip: false, length_km: 5, ascent_m: null, time: null, pois: [poi("food", 1), poi("viewpoint", 2), poi("waterfall", 3), poi("waterfall", 4)] }, "en"),
    ).toBe("Walk, 5.0 km. Along the way: 1 refreshment stop, 1 viewpoint and 2 waterfalls.");
  });

  it("labels tags and surfaces in English", () => {
    expect(tagLabels(["feature:einkehr", "feature:aussicht", "x:y"], "en")).toEqual(["Inn / café stop", "Viewpoint"]);
    expect(surfaceLine({ paved: 0.2, unpaved: 0.8 }, "en")).toBe("Surface: 80% natural · 20% tarmac");
  });
});
