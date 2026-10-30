"use client";

import { useMemo } from "react";
import type { MultidayPlan } from "../lib/chat";
import type { LodgingOnTrail } from "../lib/data";
import { daySections, trailLine, type MapTrail } from "../lib/map";
import MapPanel from "./MapPanel";

/**
 * The trail map with the plan's days (alternating colours, day-end lodgings). Without a plan for this
 * trail it is the plain map. `lengthKm` scales the line's own length to the plan's km.
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
  const days = useMemo(() => (plan && plan.days.length > 0 ? daySections(trailLine(trail), plan.days, lengthKm) : undefined), [plan, trail, lengthKm]);
  const stops = useMemo(() => {
    if (!days || !plan || !lodgings) return lodgings;
    const ids = new Set(plan.days.flatMap((d) => (d.stop ? [d.stop.lodging_id] : [])));
    return lodgings.filter((l) => ids.has(l.id));
  }, [days, plan, lodgings]);
  return <MapPanel trail={trail} lodgings={stops} days={days} />;
}
