"use client";

import { useLocale } from "../i18n";
import { num } from "../lib/format";
import type { TrailPoi } from "../lib/data";
import { POI_KIND, poiKindLabel } from "../lib/tour";

/** Food, huts, viewpoints, peaks and waterfalls along the trail, in the order given (along the trail). */
export default function PoiList({ pois }: { pois: TrailPoi[] }) {
  const { locale } = useLocale();
  if (pois.length === 0) return null;
  return (
    <ul className="scrollbar-schmal flex max-h-80 flex-col divide-y divide-wald-dunkel/10 overflow-y-auto pr-1 text-sm">
      {pois.map((p) => (
        <li key={p.id} className="flex items-baseline justify-between gap-3 py-1.5">
          <span className="min-w-0">
            <span aria-hidden="true">{POI_KIND[p.kind].icon} </span>
            {p.name ?? poiKindLabel(p.kind, locale)}
            {p.name && <span className="text-xs text-wald-dunkel/70"> · {poiKindLabel(p.kind, locale)}</span>}
          </span>
          {p.along_km !== null && <span className="shrink-0 text-xs tabular-nums text-wald-dunkel/70">km {num(p.along_km, locale, { min: 1 })}</span>}
        </li>
      ))}
    </ul>
  );
}
