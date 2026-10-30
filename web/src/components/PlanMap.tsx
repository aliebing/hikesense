"use client";

import { useMemo } from "react";
import type { MultidayPlan } from "../lib/chat";
import type { LodgingOnTrail } from "../lib/data";
import { daySections, trailLine, type MapTrail } from "../lib/map";
import MapPanel from "./MapPanel";

/**
 * The trail map with the plan's days (alternating colours, day-end lodgings at their real positions).
 * Without a plan for this trail it is the plain map. `lengthKm` is the trail length the backend's along_km
 * refers to; a day-end lodging that is not among the loaded lodgings is named in the legend, never dropped silently.
 */
export default function PlanMap({
  trail,
  lodgings,
  plan,
  lengthKm,
}: {
  trail: MapTrail;
  lodgings: LodgingOnTrail[] | null;
  plan: MultidayPlan | null;
  lengthKm?: number | null;
}) {
  const byId = useMemo(() => new Map((lodgings ?? []).map((l) => [l.id, l])), [lodgings]);
  const days = useMemo(() => {
    if (!plan || plan.days.length === 0) return undefined;
    const s = daySections(trailLine(trail), plan.days, lengthKm, (id) => {
      const l = byId.get(id);
      return l ? [l.lon, l.lat] : null;
    });
    return s.length > 0 ? s : undefined;
  }, [plan, trail, lengthKm, byId]);
  const stops = useMemo(() => {
    if (!days || !plan || !lodgings) return lodgings;
    const ids = new Set(plan.days.flatMap((d) => (d.stop ? [d.stop.lodging_id] : [])));
    return lodgings.filter((l) => ids.has(l.id));
  }, [days, plan, lodgings]);
  return <MapPanel trail={trail} lodgings={stops} days={days} />;
}
