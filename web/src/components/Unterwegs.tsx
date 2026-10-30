"use client";

import type { Position } from "geojson";
import { useEffect, useMemo, useRef, useState } from "react";
import { etaFromProfile, haversineKm, progressOnLine } from "../lib/geo";
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
 * Ascent/descent of the rest are the section's totals pro rata (the profile has no per-point elevation).
 */
export default function Unterwegs({
  title,
  trail,
  days,
  line,
  ascentM,
  descentM,
}: {
  title: string;
  trail: MapTrail;
  /** plan day: the section drawn instead of the whole trail */
  days?: DaySection[];
  /** the line to walk, [lon, lat] like GeoJSON */
  line: Position[];
  ascentM: number | null;
  descentM: number | null;
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

  let arrival: string | null = null;
  if (onRoute && ascentM !== null && descentM !== null && totalKm > 0) {
    const share = Math.min(1, progress.remainingKm / totalKm);
    arrival = clock.format(etaFromProfile(progress.remainingKm, ascentM * share, descentM * share, new Date()));
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
            Noch {de1.format(progress.remainingKm)} km <span className="font-normal">(bisher {de1.format(progress.alongKm)} km von {de1.format(totalKm)} km)</span>
          </p>
          <p className="text-xs">
            {arrival ? `Ankunft ca. ${arrival} Uhr (Gehzeit nach DIN 33466, ohne Pausen, Anstieg anteilig gerechnet)` : "Ankunft: unbekannt (Höhenmeter fehlen)"}
          </p>
        </div>
      )}
    </section>
  );
}
