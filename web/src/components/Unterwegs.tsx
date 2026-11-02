"use client";

import type { Position } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocale, useT } from "../i18n";
import { dateIn, num } from "../lib/format";
import { etaFromProfile, haversineKm, progressOnLine, upDown, type Profile } from "../lib/geo";
import type { DaySection, MapTrail } from "../lib/map";
import MapPanel from "./MapPanel";

/** Further from the line than this, there are no remaining kilometres (spec: position on the way). */
export const OFF_ROUTE_M = 200;

type Texts = ReturnType<typeof useT>["plan"];
const errorText = (code: number, t: Texts) => (code === 1 ? t.uwDenied : code === 3 ? t.uwTimeout : t.uwUnavailable);

type Fix = { lat: number; lon: number };

/**
 * „Unterwegs“: own position on the planned line (whole trail or one plan day), remaining km and arrival.
 * Everything is computed here in the browser from watchPosition; the position is never sent, stored or logged,
 * and the watch runs only while the page is open and started (no background location, no recording).
 * Remaining km = remaining share × the section's known length (the plan's own km, like the plan card), the
 * haversine length only when that is unknown. Ascent/descent of the rest come from the elevation profile
 * (same interpolation as the backend); without a profile there is no arrival, never a scaled guess.
 */
export default function Unterwegs({
  title,
  trail,
  days,
  line,
  profile,
  startKm = 0,
  lengthKm,
}: {
  title: string;
  trail: MapTrail;
  /** plan day: the section drawn instead of the whole trail */
  days?: DaySection[];
  /** the line to walk, [lon, lat] like GeoJSON */
  line: Position[];
  /** trails.profile: [km, elevation_m] along the whole trail */
  profile: Profile | null;
  /** trail km where the line starts (plan day: its start_km; whole trail: 0) */
  startKm?: number;
  /** known km of the line (plan day: its walk_km; trail: length_km); null: use the geometry */
  lengthKm: number | null;
}) {
  const { locale } = useLocale();
  const t = useT().plan;
  const n1 = (n: number) => num(n, locale, { min: 1 });
  const [watching, setWatching] = useState(false);
  const [fix, setFix] = useState<Fix | null>(null);
  const [error, setError] = useState<string | null>(null);
  const watchId = useRef<number | null>(null);

  const latLon = useMemo(() => line.map(([lon, lat]) => [lat, lon] as [number, number]), [line]);
  const totalKm = useMemo(() => latLon.slice(1).reduce((sum, p, i) => sum + haversineKm(latLon[i], p), 0), [latLon]);

  const stop = () => {
    if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    watchId.current = null;
    setWatching(false);
    setFix(null); // nothing stale after „Beenden“
    setError(null);
  };

  const start = () => {
    setError(null);
    setFix(null);
    if (!navigator.geolocation) {
      setError(t.uwUnsupported);
      return;
    }
    watchId.current = navigator.geolocation.watchPosition(
      (p) => {
        setError(null);
        setFix({ lat: p.coords.latitude, lon: p.coords.longitude });
      },
      (e) => setError(errorText(e.code, t)),
      { enableHighAccuracy: true, maximumAge: 10_000, timeout: 30_000 },
    );
    setWatching(true);
  };

  // leaving the page ends the watch
  useEffect(
    () => () => {
      if (watchId.current !== null) navigator.geolocation?.clearWatch(watchId.current);
    },
    [],
  );

  const progress = useMemo(() => (fix && latLon.length > 1 ? progressOnLine(latLon, fix) : null), [fix, latLon]);
  const onRoute = progress !== null && progress.distToLineM <= OFF_ROUTE_M;

  const known = lengthKm !== null && lengthKm > 0 ? lengthKm : null;
  const sectionKm = known ?? totalKm;
  const alongKm = progress ? (known ? progress.fraction * known : progress.alongKm) : 0;
  const remainingKm = progress ? (known ? (1 - progress.fraction) * known : progress.remainingKm) : 0;
  let arrival: string | null = null;
  if (onRoute && progress) {
    const rest = upDown(profile, startKm + alongKm, startKm + sectionKm);
    if (rest) arrival = dateIn(etaFromProfile(remainingKm, rest.up, rest.down, new Date()), locale, { hour: "2-digit", minute: "2-digit" });
  }

  return (
    <section aria-label={t.uwTitle} className="flex max-w-xl flex-col gap-3">
      <h2 className="font-serif text-xl">{title}</h2>
      <div className="flex flex-wrap items-center gap-3">
        {watching ? (
          <button type="button" onClick={stop} className="rounded-full bg-papier/90 px-4 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
            {t.uwStop}
          </button>
        ) : (
          <button type="button" onClick={start} className="rounded-full bg-papier/90 px-4 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
            {t.uwStart}
          </button>
        )}
        <MapPanel trail={trail} days={days} position={fix} />
      </div>
      <p className="text-xs text-papier/85">{t.uwPrivacy}</p>
      {error && (
        <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {error}
        </p>
      )}
      {watching && !fix && !error && <p role="status" className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">{t.uwLocating}</p>}
      {progress && !onRoute && (
        <p role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-950">
          {t.uwOffRoute(n1(progress.distToLineM / 1000))}
        </p>
      )}
      {progress && onRoute && (
        <div className="rounded-xl bg-papier/95 px-3 py-2 text-sm text-wald-dunkel shadow">
          <p className="font-medium">
            {t.uwRemaining(n1(remainingKm))} <span className="font-normal">{t.uwProgress(n1(alongKm), n1(sectionKm))}</span>
          </p>
          <p className="text-xs">
            {arrival ? t.uwArrival(arrival) : t.uwArrivalUnknown}
          </p>
        </div>
      )}
    </section>
  );
}
