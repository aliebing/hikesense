"use client";

import { useLocale, useT } from "../i18n";
import { num } from "../lib/format";
import type { GroupBrief } from "../lib/chat";

import type { Messages } from "../i18n/en";

/** How the entries were checked: only status „geprüft“ counts as checked by hand (missing = automatic). */
function checkNote(groups: GroupBrief[], t: Messages["tour"]): { text: string; perRow: boolean } {
  const hand = groups.filter((g) => g.status === "geprüft").length;
  if (hand === groups.length) return { text: t.groupHand, perRow: false };
  if (hand === 0) return { text: t.groupAuto, perRow: false };
  return { text: t.groupMixed(t.groupHand, t.groupAuto), perRow: true };
}

/**
 * Groups of the curated list: name (link to the group's own page), kind, place, distance,
 * and the check date ("Stand: …", given by the backend). No persons, no event dates; entries
 * checked more than 180 days ago are marked „veraltet“ (the backend decides: `stale`).
 */
/** `inBlock`: inside a Block on the tour page, which already gives the light background. */
export default function GroupList({ groups, note, inBlock = false }: { groups: GroupBrief[]; note: string; inBlock?: boolean }) {
  const { locale } = useLocale();
  const t = useT().tour;
  if (groups.length === 0) return null;
  const check = checkNote(groups, t);
  return (
    <div className={`flex flex-col gap-1 text-sm text-wald-dunkel ${inBlock ? "" : "rounded-xl bg-papier/90 px-3 py-2"}`}>
      <ul aria-label={t.groups} className="flex flex-col gap-1">
        {groups.map((g) => (
          <li key={`${g.name}|${g.url}`} className="flex flex-wrap items-baseline gap-x-2">
            <a href={g.url} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2">
              {g.name}
            </a>
            <span className="text-xs">
              {(t.groupKinds as Record<string, string>)[g.kind] ?? t.group} · {g.place} · {num(g.dist_km, locale, { max: 1 })} km
            </span>
            {check.perRow && g.status === "geprüft" && <span className="text-xs">{t.groupHand}</span>}
            {g.stale && <span className="rounded bg-amber-200 px-1 text-xs text-amber-950">{t.stale}</span>}
          </li>
        ))}
      </ul>
      <p className="text-xs">
        {note} · {check.text}; {t.groupTail}
      </p>
    </div>
  );
}
