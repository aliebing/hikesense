import type { TrailPoi } from "../lib/data";
import { POI_KIND } from "../lib/tour";

const de1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });

/** Food, huts, viewpoints, peaks and waterfalls along the trail, in the order given (along the trail). */
export default function PoiList({ pois }: { pois: TrailPoi[] }) {
  if (pois.length === 0) return null;
  return (
    <ul className="scrollbar-schmal flex max-h-80 flex-col divide-y divide-wald-dunkel/10 overflow-y-auto pr-1 text-sm">
      {pois.map((p) => (
        <li key={p.id} className="flex items-baseline justify-between gap-3 py-1.5">
          <span className="min-w-0">
            <span aria-hidden="true">{POI_KIND[p.kind].icon} </span>
            {p.name ?? POI_KIND[p.kind].label}
            {p.name && <span className="text-xs text-wald-dunkel/70"> · {POI_KIND[p.kind].label}</span>}
          </span>
          {p.along_km !== null && <span className="shrink-0 text-xs tabular-nums text-wald-dunkel/70">km {de1.format(p.along_km)}</span>}
        </li>
      ))}
    </ul>
  );
}
