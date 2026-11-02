"use client";

import { useLocale, useT } from "../i18n";
import { num } from "../lib/format";

const W = 300;
const H = 60;

/** Elevation profile as a filled area ([km, m] from the import), labelled with its lowest and highest point. */
export default function ElevationProfile({ profile }: { profile: [number, number][] }) {
  const { locale } = useLocale();
  const t = useT().plan;
  const kms = profile.map((p) => p[0]);
  const ms = profile.map((p) => p[1]);
  const [k0, k1, m0, m1] = [Math.min(...kms), Math.max(...kms), Math.min(...ms), Math.max(...ms)];
  const x = (k: number) => (k1 > k0 ? ((k - k0) / (k1 - k0)) * W : 0);
  const y = (m: number) => (m1 > m0 ? H - ((m - m0) / (m1 - m0)) * (H - 4) - 2 : H / 2);
  const line = profile.map(([k, m]) => `${x(k).toFixed(1)},${y(m).toFixed(1)}`).join(" L");
  const label = t.elevation(num(m0, locale), num(m1, locale));
  return (
    <figure className="flex flex-col gap-1">
      <svg role="img" aria-label={label} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="h-16 w-full">
        <path d={`M${line} L${W},${H} L0,${H} Z`} fill="currentColor" fillOpacity="0.18" />
        <path d={`M${line}`} fill="none" stroke="currentColor" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
      </svg>
      <figcaption className="text-xs opacity-75">{label}</figcaption>
    </figure>
  );
}
