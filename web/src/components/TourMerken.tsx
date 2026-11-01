"use client";

import { useChat } from "./ChatProvider";
import MerkenButton from "./MerkenButton";

/** „Merken“ on the trail page: saves the chat's card for this tour; without one (shared link) there is nothing to save. */
export default function TourMerken({ trailId }: { trailId: string }) {
  const { state } = useChat();
  const card = state.last?.cards.find((c) => c.trail_id === trailId);
  if (!card) return null;
  return <MerkenButton kind="day_hike" title={card.name} payload={card} />;
}
