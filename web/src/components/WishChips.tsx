"use client";

import type { ConstraintResult } from "../lib/chat";
import { useChat } from "./ChatProvider";
import { LABEL, UNIT } from "./TourResultCard";

function chip(r: ConstraintResult): { text: string; tone: string } {
  const label = LABEL[r.kind] ?? r.kind;
  const raw = UNIT[r.kind] && r.bound ? `${r.bound} ${UNIT[r.kind]}` : r.bound;
  const bound = raw === label ? "" : raw; // „Rundweg: Rundweg“ says it twice
  if (r.ok === true) return { text: `✓ ${label}${bound ? `: ${bound}` : ""}`, tone: "bg-wald/15 text-wald-dunkel" };
  if (r.ok === false) return { text: `✗ ${label}${bound ? `: ${bound}` : ""}`, tone: "bg-red-100 text-red-900" };
  return { text: `? ${label}: unbekannt`, tone: "bg-wald-dunkel/10 text-wald-dunkel" };
}

/**
 * The chat's verdicts for this tour (✓/✗/? per wish). Only when the tour is among the current chat
 * results; a shared link without that chat shows nothing.
 */
export default function WishChips({ trailId }: { trailId: string }) {
  const { state } = useChat();
  const card = state.last?.cards.find((c) => c.trail_id === trailId);
  return card ? <VerdictChips results={card.results} /> : null;
}

/** ✓/✗/? per wish as chips; nothing without results. */
export function VerdictChips({ results }: { results: ConstraintResult[] }) {
  if (results.length === 0) return null;
  return (
    <ul aria-label="Deine Wünsche" className="flex flex-wrap gap-1.5">
      {results.map((r, i) => {
        const c = chip(r);
        return (
          <li key={r.kind + i} className={`rounded-full px-2.5 py-0.5 text-xs ${c.tone}`}>
            {c.text}
          </li>
        );
      })}
    </ul>
  );
}
