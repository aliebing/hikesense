import { chipsFor } from "./ChatMessages";
import type { HikeRequest } from "../lib/chat";

const base = { intent: "day_hike", activity: "hike", start_text: null, start: null, constraints: [], pace_min_per_km: null, unmatched: [] } as unknown as HikeRequest;

it("marks preferences from the saved Vorlieben, in both languages", () => {
  const r = {
    ...base,
    preferences: [
      { tag_id: "feature:einkehr", mode: "prefer", weight: 3 },
      { tag_id: "feature:aussicht", mode: "prefer", weight: 2, saved: true },
      { tag_id: "surface:naturweg", mode: "avoid", weight: 1, saved: true },
    ],
  } as HikeRequest;
  const labels = { "feature:einkehr": "Einkehr", "feature:aussicht": "Aussicht", "surface:naturweg": "Naturweg" };
  expect(chipsFor(r, labels, "de").map((c) => c.text)).toEqual(["Einkehr", "Aussicht (wäre schön) · Vorliebe", "Ohne Naturweg · Vorliebe"]);
  expect(chipsFor(r, labels, "en")[1].text).toBe("Aussicht (nice to have) · preference");
});
