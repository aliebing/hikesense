"use client";

import type { Position } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { etaFromProfile, haversineKm, progressOnLine, upDown, type Profile } from "../lib/geo";
import type { DaySection, MapTrail } from "../lib/map";
import MapPanel from "./MapPanel";

/** Further from the line than this, there are no remaining kilometres (spec: position on the way). */
export const OFF_ROUTE_M = 200;

const de1 = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const clock = new Intl.DateTimeFormat("de-DE", { hour: "2-digit", minute: "2-digit" });

const MSG_DENIED = "Standortfreigabe verweigert – in den Browser-Einstellungen erlauben";
const MSG_UNAVAILABLE = "Standort nicht verfügbar – bitte im Freien mit Ortungsdienst erneut versuchen";
const MSG_TIMEOUT = "Zeitüberschreitung bei der Standortbestimmung – bitte erneut versuchen";
const MSG_UNSUPPORTED = "Standortbestimmung ist in diesem Browser nicht verfügbar";

const errorText = (code: number) => (code === 1 ? MSG_DENIED : code === 3 ? MSG_TIMEOUT : MSG_UNAVAILABLE);

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
      setError(MSG_UNSUPPORTED);
      return;
    }
    watchId.current = navigator.geolocation.watchPosition(
      (p) => {
        setError(null);
        setFix({ lat: p.coords.latitude, lon: p.coords.longitude });
      },
      (e) => setError(errorText(e.code)),
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
    if (rest) arrival = clock.format(etaFromProfile(remainingKm, rest.up, rest.down, new Date()));
  }

  return (
    <section aria-label="Unterwegs" className="flex max-w-xl flex-col gap-3">
      <h2 className="font-serif text-xl drop-shadow">{title}</h2>
      <div className="flex flex-wrap items-center gap-3">
        {watching ? (
          <button type="button" onClick={stop} className="rounded-full bg-papier/90 px-4 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
            Beenden
          </button>
        ) : (
          <button type="button" onClick={start} className="rounded-full bg-papier/90 px-4 py-2 text-sm font-medium text-wald-dunkel shadow hover:bg-white">
            Unterwegs starten
          </button>
        )}
        <MapPanel trail={trail} lodgings={null} days={days} position={fix} />
      </div>
      <p className="text-xs text-papier/85">Dein Standort bleibt auf diesem Gerät: Er wird weder gesendet noch gespeichert, und die Ortung läuft nur, solange diese Seite offen ist.</p>
      {error && (
        <p role="alert" className="rounded-xl bg-red-100 px-3 py-2 text-sm text-red-900">
          {error}
        </p>
      )}
      {watching && !fix && !error && <p role="status" className="rounded-xl bg-papier/90 px-3 py-2 text-sm text-wald-dunkel">Standort wird bestimmt …</p>}
      {progress && !onRoute && (
        <p role="note" className="rounded-xl border-l-4 border-amber-500 bg-amber-100 px-3 py-2 text-sm font-medium text-amber-950">
          Du bist {de1.format(progress.distToLineM / 1000)} km vom Weg entfernt – Restkilometer erst wieder am Weg
        </p>
      )}
      {progress && onRoute && (
        <div className="rounded-xl bg-papier/95 px-3 py-2 text-sm text-wald-dunkel shadow">
          <p className="font-medium">
            Noch {de1.format(remainingKm)} km <span className="font-normal">(bisher {de1.format(alongKm)} km von {de1.format(sectionKm)} km)</span>
          </p>
          <p className="text-xs">
            {arrival ? `Ankunft ca. ${arrival} Uhr (Gehzeit nach DIN 33466, ohne Pausen)` : "Ankunft: unbekannt (kein Höhenprofil)"}
          </p>
        </div>
      )}
    </section>
  );
}
