"use client";

import { useMemo, useRef } from "react";
import type { MultidayPlan } from "../lib/chat";
import type { LodgingOnTrail, TrailPoi } from "../lib/data";
import { daySections, trailLine, type MapTrail } from "../lib/map";
import MapPanel from "./MapPanel";

/** Keeps the previous value while its cheap fingerprint is unchanged (equal content, new object identity). */
function useStable<T>(value: T, key: string): T {
  const ref = useRef({ key, value });
  if (ref.current.key !== key) ref.current = { key, value };
  return ref.current.value;
}

const trailKey = (t: MapTrail) => {
  const n = (g: { coordinates: unknown[] } | null | undefined) => (g ? `${g.coordinates.length}` : "-");
  return [t.name, n(t.geom), JSON.stringify(t.geom?.coordinates[0]), ...t.stages.map((s) => `${s.seq}:${n(s.geom)}:${s.start_name}:${s.end_name}`)].join("|");
};
const lodgingsKey = (l: LodgingOnTrail[] | null) => (l ? l.map((x) => `${x.id}:${x.name}:${x.dist_m}`).join("|") : "null");
const poisKey = (p: TrailPoi[] | undefined) => (p ? p.map((x) => `${x.id}:${x.kind}:${x.name}`).join("|") : "none");

/**
 * The trail map with the plan's days (alternating colours, day-end lodgings at their real positions).
 * Without a plan for this trail it is the plain map. `lengthKm` is the trail length the backend's along_km
 * refers to; a day-end lodging that is not among the loaded lodgings is named in the legend, never dropped silently.
 */
export default function PlanMap({
  trail: trailProp,
  lodgings: lodgingsProp,
  plan,
  lengthKm,
  pois: poisProp,
  embedded,
}: {
  trail: MapTrail;
  lodgings: LodgingOnTrail[] | null;
  plan: MultidayPlan | null;
  lengthKm?: number | null;
  pois?: TrailPoi[];
  embedded?: boolean;
}) {
  // a language switch refreshes the server parts and delivers equal data in new objects; the map must keep its view
  const trail = useStable(trailProp, trailKey(trailProp));
  const lodgings = useStable(lodgingsProp, lodgingsKey(lodgingsProp));
  const pois = useStable(poisProp, poisKey(poisProp));
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
  return <MapPanel trail={trail} lodgings={stops} days={days} pois={days ? undefined : pois} embedded={embedded} />;
}
