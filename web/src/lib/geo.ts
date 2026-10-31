import { din33466Hours } from "./format";

const R_KM = 6371.0088;
const rad = (d: number) => (d * Math.PI) / 180;

/** Great-circle distance in km between two [lat, lon] points. */
export function haversineKm(a: [number, number], b: [number, number]): number {
  const dLat = rad(b[0] - a[0]);
  const dLon = rad(b[1] - a[1]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[0])) * Math.cos(rad(b[0])) * Math.sin(dLon / 2) ** 2;
  return 2 * R_KM * Math.asin(Math.min(1, Math.sqrt(h)));
}

export type Progress = {
  alongKm: number;
  distToLineM: number;
  remainingKm: number;
  /** 0..1 along the line by its geodesic length — the metric share daySections and the backend's along_km use */
  fraction: number;
};

/**
 * Own position on a line of [lat, lon] points: foot of the perpendicular on the nearest segment
 * (local flat projection around the position), distances by haversine. Pure, runs in the browser only.
 */
export function progressOnLine(line: [number, number][], pos: { lat: number; lon: number }): Progress {
  if (line.length === 0) return { alongKm: 0, distToLineM: Infinity, remainingKm: 0, fraction: 0 };
  const kx = Math.cos(rad(pos.lat)); // lon degrees shrink with latitude
  let bestM = Infinity;
  let bestAlong = 0;
  let cum = 0;
  let total = 0;
  for (let i = 1; i < line.length; i++) total += haversineKm(line[i - 1], line[i]);
  if (line.length === 1) bestM = haversineKm(line[0], [pos.lat, pos.lon]) * 1000;
  for (let i = 1; i < line.length; i++) {
    const [aLat, aLon] = line[i - 1];
    const [bLat, bLon] = line[i];
    const seg = haversineKm(line[i - 1], line[i]);
    // segment in a local frame (degrees, lon scaled), position relative to its start
    const dx = (bLon - aLon) * kx;
    const dy = bLat - aLat;
    const px = (pos.lon - aLon) * kx;
    const py = pos.lat - aLat;
    const len2 = dx * dx + dy * dy;
    const t = len2 > 0 ? Math.min(1, Math.max(0, (px * dx + py * dy) / len2)) : 0;
    const foot: [number, number] = [aLat + dy * t, aLon + (bLon - aLon) * t];
    const distM = haversineKm(foot, [pos.lat, pos.lon]) * 1000;
    if (distM < bestM) {
      bestM = distM;
      bestAlong = cum + seg * t;
    }
    cum += seg;
  }
  return { alongKm: bestAlong, distToLineM: bestM, remainingKm: Math.max(0, total - bestAlong), fraction: total > 0 ? bestAlong / total : 0 };
}

/** Arrival = now + DIN 33466 time of the rest (same formula as the backend, no breaks). */
export function etaFromProfile(remainingKm: number, remainingAscentM: number, remainingDescentM: number, now: Date): Date {
  const hours = din33466Hours(remainingKm, remainingAscentM, remainingDescentM);
  return new Date(now.getTime() + Math.round(hours * 3600) * 1000);
}

/** [km, elevation_m] points of trails.profile / stages.profile */
export type Profile = [number, number][];

function elevationAt(profile: Profile, km: number): number {
  if (km <= profile[0][0]) return profile[0][1];
  for (let i = 1; i < profile.length; i++) {
    const [k0, e0] = profile[i - 1];
    const [k1, e1] = profile[i];
    if (km <= k1) return k1 === k0 ? e0 : e0 + ((e1 - e0) * (km - k0)) / (k1 - k0);
  }
  return profile[profile.length - 1][1];
}

/**
 * Ascent/descent between km a and b, profile linearly interpolated at the cut points
 * (port of _up_down in backend/src/hikeall/agent/multiday.py). null without a usable profile.
 */
export function upDown(profile: Profile | null | undefined, a: number, b: number): { up: number; down: number } | null {
  if (!profile || profile.length < 2) return null;
  const pts = [elevationAt(profile, a)];
  for (const [k, e] of profile) if (k > a && k < b) pts.push(e);
  pts.push(elevationAt(profile, b));
  let up = 0;
  let down = 0;
  for (let i = 1; i < pts.length; i++) {
    up += Math.max(0, pts[i] - pts[i - 1]);
    down += Math.max(0, pts[i - 1] - pts[i]);
  }
  return { up, down };
}
