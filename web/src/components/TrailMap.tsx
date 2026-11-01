"use client";

import type { LodgingOnTrail, TrailPoi } from "../lib/data";
import type { MapTrail } from "../lib/map";
import { useChat } from "./ChatProvider";
import PlanMap from "./PlanMap";

/** Map of the trail page: when coming from the chat (`von=chat`) and a plan for this trail in the chat, the plan's days are drawn. */
export default function TrailMap({
  trailId,
  fromChat,
  trail,
  lodgings,
  lengthKm,
  pois,
  embedded,
}: {
  trailId: string;
  fromChat: boolean;
  trail: MapTrail;
  lodgings: LodgingOnTrail[] | null;
  lengthKm: number | null;
  pois?: TrailPoi[];
  embedded?: boolean;
}) {
  const { state } = useChat();
  const plan = fromChat && state.plan?.plan.trail_id === trailId ? state.plan.plan : null;
  return <PlanMap trail={trail} lodgings={lodgings} plan={plan} lengthKm={lengthKm} pois={pois} embedded={embedded} />;
}
