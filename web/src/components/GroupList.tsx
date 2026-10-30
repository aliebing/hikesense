import type { GroupBrief } from "../lib/chat";

const KIND: Record<string, string> = {
  wanderverein: "Wanderverein",
  lauftreff: "Lauftreff",
  alpenverein: "Alpenverein",
  sonstige: "Gruppe",
};

const de1 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 1 });

export const GROUP_AUTO = "automatisch geprüft (Seite und Name abgerufen), noch nicht von Hand bestätigt";
export const GROUP_HAND = "von Hand geprüft";

/** How the entries were checked: only status „geprüft“ counts as checked by hand (missing = automatic). */
function checkNote(groups: GroupBrief[]): { text: string; perRow: boolean } {
  const hand = groups.filter((g) => g.status === "geprüft").length;
  if (hand === groups.length) return { text: GROUP_HAND, perRow: false };
  if (hand === 0) return { text: GROUP_AUTO, perRow: false };
  return { text: `ohne Vermerk „${GROUP_HAND}“: ${GROUP_AUTO}`, perRow: true };
}

/**
 * Groups of the curated list: name (link to the group's own page), kind, place, distance,
 * and the check date ("Stand: …", given by the backend). No persons, no event dates; entries
 * checked more than 180 days ago are marked „veraltet“ (the backend decides: `stale`).
 */
export default function GroupList({ groups, note }: { groups: GroupBrief[]; note: string }) {
  if (groups.length === 0) return null;
  const check = checkNote(groups);
  return (
    <div className="flex flex-col gap-1 rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">
      <ul aria-label="Gruppen" className="flex flex-col gap-1">
        {groups.map((g) => (
          <li key={`${g.name}|${g.url}`} className="flex flex-wrap items-baseline gap-x-2">
            <a href={g.url} target="_blank" rel="noopener noreferrer" className="font-medium underline underline-offset-2">
              {g.name}
            </a>
            <span className="text-xs">
              {KIND[g.kind] ?? "Gruppe"} · {g.place} · {de1.format(g.dist_km)} km
            </span>
            {check.perRow && g.status === "geprüft" && <span className="text-xs">{GROUP_HAND}</span>}
            {g.stale && <span className="rounded bg-amber-200 px-1 text-xs text-amber-950">veraltet</span>}
          </li>
        ))}
      </ul>
      <p className="text-xs">
        {note} · {check.text}; Treffzeiten und Ansprechpersonen stehen auf den Seiten der Gruppen.
      </p>
    </div>
  );
}
