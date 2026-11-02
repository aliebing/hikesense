"use client";

import type { ConstraintResult } from "../lib/chat";
import { useChat } from "./ChatProvider";
import { useT } from "../i18n";
import type { Messages } from "../i18n/en";
import { kindLabel, kindUnit } from "./TourResultCard";

function chip(r: ConstraintResult, t: Messages): { text: string; tone: string } {
  const label = kindLabel(r.kind, t);
  const raw = kindUnit(r.kind, t) && r.bound ? `${r.bound} ${kindUnit(r.kind, t)}` : r.bound;
  const bound = raw === label ? "" : raw; // „Rundweg: Rundweg“ says it twice
  if (r.ok === true) return { text: `✓ ${label}${bound ? `: ${bound}` : ""}`, tone: "bg-wald/15 text-wald-dunkel" };
  if (r.ok === false) return { text: `✗ ${label}${bound ? `: ${bound}` : ""}`, tone: "bg-red-100 text-red-900" };
  return { text: `? ${label}: ${t.results.unknown}`, tone: "bg-wald-dunkel/10 text-wald-dunkel" };
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
  const t = useT();
  if (results.length === 0) return null;
  return (
    <ul aria-label={t.results.wishes} className="flex flex-wrap gap-1.5">
      {results.map((r, i) => {
        const c = chip(r, t);
        return (
          <li key={r.kind + i} className={`rounded-full px-2.5 py-0.5 text-xs ${c.tone}`}>
            {c.text}
          </li>
        );
      })}
    </ul>
  );
}
