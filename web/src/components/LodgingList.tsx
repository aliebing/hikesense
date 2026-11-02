"use client";

import { useLocale, useT } from "../i18n";
import { num } from "../lib/format";
import type { LodgingOnTrail } from "../lib/data";
import { lodgingKind } from "../lib/map";
import { lodgingLink } from "../lib/planView";

const MAX_LODGINGS = 5;

/** The nearest lodgings to the trail (dist_m as imported), with a link to their website or a search. */
export default function LodgingList({ lodgings, place }: { lodgings: LodgingOnTrail[]; /** shown with the name in the web search */ place?: string }) {
  const { locale } = useLocale();
  const t = useT().tour;
  if (lodgings.length === 0) return null;
  const nearest = [...lodgings]
    .sort((a, b) => (a.dist_m ?? Infinity) - (b.dist_m ?? Infinity) || a.id - b.id)
    .slice(0, MAX_LODGINGS);
  return (
    <div className="flex flex-col gap-2 text-sm">
      <ul className="flex flex-col divide-y divide-wald-dunkel/10">
        {nearest.map((l) => {
          const name = l.name ?? lodgingKind(l.kind, locale);
          const link = lodgingLink({ name, website: l.website }, place, locale);
          return (
            <li key={l.id} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1.5">
              <span className="min-w-0">
                {name}
                <span className="text-xs text-wald-dunkel/70"> · {lodgingKind(l.kind, locale)}</span>
              </span>
              <span className="flex shrink-0 items-baseline gap-2 text-xs text-wald-dunkel/70">
                {l.dist_m !== null && <span className="tabular-nums">{t.lodgingFromTrail(num(l.dist_m, locale))}</span>}
                {link && (
                  <a href={link.href} target="_blank" rel="noopener noreferrer" className="text-wald underline underline-offset-2">
                    {link.label}
                  </a>
                )}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-wald-dunkel/70">{t.lodgingCheck}</p>
    </div>
  );
}
