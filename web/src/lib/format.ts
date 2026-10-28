const de1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const de0 = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 0 });

/** 14.83 → "14,8 km" */
export function km(n: number): string {
  return `${de1.format(n)} km`;
}

/** 720 → "↑ 720 m" */
export function hm(n: number): string {
  return `↑ ${de0.format(n)} m`;
}

/** 700 → "↓ 700 m" */
export function hmDown(n: number): string {
  return `↓ ${de0.format(n)} m`;
}

/** 5.17 → "5:10 h" (rounded to whole minutes) */
export function duration(hours: number): string {
  const minutes = Math.round(hours * 60);
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${h}:${String(m).padStart(2, "0")} h`;
}

/**
 * DIN 33466 hiking time in hours (guidance, no breaks) — same formula as
 * backend/src/hikeall/hiking_time.py: max(h, v) + min(h, v) / 2 with
 * h = km / 4 and v = ascent / 300 + descent / 500, rounded to 2 decimals.
 */
export function din33466Hours(distanceKm: number, ascentM: number, descentM: number): number {
  if (Math.min(distanceKm, ascentM, descentM) < 0) {
    throw new Error("distance, ascent and descent must be >= 0");
  }
  const horizontal = distanceKm / 4;
  const vertical = ascentM / 300 + descentM / 500;
  const hours = Math.max(horizontal, vertical) + Math.min(horizontal, vertical) / 2;
  return Math.round(hours * 100) / 100;
}
