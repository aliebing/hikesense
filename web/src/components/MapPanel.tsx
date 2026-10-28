"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import type { FilterSpecification, GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LodgingOnTrail } from "../lib/data";
import {
  ATTRIBUTION,
  BASEMAP_STYLE,
  LODGING_MAX_DIST_M,
  OSM_RASTER_STYLE,
  bboxOf,
  lodgingKind,
  lodgingsNearby,
  safeWebsite,
  trailToFeatures,
  type MapTrail,
} from "../lib/map";

/** Two alternating reds so neighbouring stages stay distinguishable. */
const STAGE_RED = ["#d62839", "#8a1526"] as const;

type Status = "loading" | "ready" | "error";

/** Below this zoom lodgings are drawn as small dots. */
const LODGING_FULL_ZOOM = 11;

/**
 * „🗺 Karte“ button plus a full-screen overlay with the trail map
 * (basemap.de vector tiles, OSM raster as fallback). maplibre-gl is loaded
 * only in the browser, when the overlay opens.
 */
export default function MapPanel({ trail, lodgings }: { trail: MapTrail; lodgings: LodgingOnTrail[] }) {
  const [open, setOpen] = useState(false);
  const opener = useRef<HTMLButtonElement>(null);
  const closer = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  useEffect(() => {
    if (open) {
      closer.current?.focus();
      const onKey = (e: KeyboardEvent) => {
        if (e.key === "Escape") setOpen(false);
      };
      document.addEventListener("keydown", onKey);
      const overflow = document.body.style.overflow;
      document.body.style.overflow = "hidden";
      wasOpen.current = true;
      return () => {
        document.removeEventListener("keydown", onKey);
        document.body.style.overflow = overflow;
      };
    }
    if (wasOpen.current) opener.current?.focus();
  }, [open]);

  return (
    <>
      <button
        ref={opener}
        type="button"
        aria-haspopup="dialog"
        aria-label="Karte öffnen"
        onClick={() => setOpen(true)}
        className="self-start justify-self-start rounded-full border border-white/25 bg-papier/15 px-4 py-2 text-sm text-papier shadow-lg backdrop-blur-xl hover:bg-papier/25 focus-visible:outline-2 focus-visible:outline-papier md:justify-self-end"
      >
        <span aria-hidden="true">🗺 </span>Karte
      </button>
      {open && <MapOverlay trail={trail} lodgings={lodgings} closer={closer} onClose={() => setOpen(false)} />}
    </>
  );
}

function MapOverlay({
  trail,
  lodgings,
  closer,
  onClose,
}: {
  trail: MapTrail;
  lodgings: LodgingOnTrail[];
  closer: React.RefObject<HTMLButtonElement | null>;
  onClose: () => void;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [status, setStatus] = useState<Status>("loading");
  const features = useMemo(() => trailToFeatures(trail), [trail]);
  const nearby = useMemo(() => lodgingsNearby(lodgings), [lodgings]);

  useEffect(() => {
    let cancelled = false;
    let map: MapLibreMap | undefined;
    const markers: Marker[] = [];

    import("maplibre-gl")
      .then((ml) => {
        if (cancelled || !container.current) return;
        // The bundler does not see maplibre's own worker lookup; this emits the
        // worker file as an asset and tells maplibre where it is.
        ml.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href);
        const bbox = bboxOf(features);
        map = new ml.Map({
          container: container.current,
          style: BASEMAP_STYLE,
          attributionControl: false, // shown below the map, always visible
          ...(bbox ? { bounds: bbox, fitBoundsOptions: { padding: 40 } } : { center: [8.1, 48.3], zoom: 8 }),
        });
        map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
        // Zoomed out (whole Westweg), full 🛏 markers would cover the line: show dots.
        const markDots = () => container.current?.classList.toggle("map-lodging-dots", map!.getZoom() < LODGING_FULL_ZOOM);
        map.on("zoomend", markDots);
        markDots();

        let styleLoaded = false;
        let fellBack = false;
        map.on("style.load", () => {
          styleLoaded = true;
          addTrailLayers(map!, features);
          setStatus("ready");
        });
        map.on("error", (e) => {
          // A failing basemap.de style: switch to OSM raster tiles once.
          if (!styleLoaded && !fellBack) {
            fellBack = true;
            console.warn("basemap.de style failed, using OSM raster tiles:", e.error?.message);
            map!.setStyle(OSM_RASTER_STYLE);
          }
        });
        map.on("click", "trail-boundaries", (e) => {
          const name = e.features?.[0]?.properties?.name;
          if (!name) return;
          const el = document.createElement("strong");
          el.textContent = String(name);
          new ml.Popup({ offset: 8 }).setLngLat(e.lngLat).setDOMContent(el).addTo(map!);
        });
        map.on("mouseenter", "trail-boundaries", () => (map!.getCanvas().style.cursor = "pointer"));
        map.on("mouseleave", "trail-boundaries", () => (map!.getCanvas().style.cursor = ""));

        for (const l of nearby) {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "map-lodging";
          el.textContent = "🛏";
          el.setAttribute("aria-label", `${lodgingName(l)}, ${distance(l)}`);
          markers.push(
            new ml.Marker({ element: el })
              .setLngLat([l.lon, l.lat])
              .setPopup(new ml.Popup({ offset: 14, maxWidth: "260px" }).setDOMContent(lodgingPopup(l)))
              .addTo(map),
          );
        }
      })
      .catch((e) => {
        console.error("map failed:", e);
        if (!cancelled) setStatus("error");
      });

    return () => {
      cancelled = true;
      markers.forEach((m) => m.remove());
      map?.remove();
    };
  }, [features, nearby]);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="map-title"
      className="fixed inset-0 z-50 flex bg-black/55 p-2 backdrop-blur-sm sm:p-6"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="flex min-h-0 w-full flex-col overflow-hidden rounded-2xl bg-wald-dunkel shadow-2xl ring-1 ring-white/15">
        <div className="flex items-center gap-3 px-4 py-2">
          <h2 id="map-title" className="min-w-0 flex-1 truncate font-serif text-lg text-papier">
            Karte: {trail.name}
          </h2>
          <button
            ref={closer}
            type="button"
            onClick={onClose}
            aria-label="Karte schließen"
            className="rounded-full px-3 py-1 text-sm text-papier/90 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-papier"
          >
            Schließen <span aria-hidden="true">✕</span>
          </button>
        </div>

        <div className="relative min-h-0 flex-1 bg-papier/10">
          {/* maplibre's CSS makes its container position: relative, so it fills an absolute wrapper. */}
          <div className="absolute inset-0">
            <div ref={container} data-map-status={status} className="h-full w-full bg-[#eef0ea]" />
          </div>
          {status !== "ready" && (
            <p className="absolute inset-0 grid place-items-center p-4 text-center text-sm text-papier/85" role="status">
              {status === "loading" ? "Karte wird geladen …" : "Die Karte konnte nicht geladen werden."}
            </p>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-[11px] text-papier/85">
          <span className="flex items-center gap-1">
            <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: `linear-gradient(90deg, ${STAGE_RED[0]} 50%, ${STAGE_RED[1]} 50%)` }} />
            {trail.stages.length > 0 ? "Etappen" : "Tour"}
          </span>
          <span>
            <span aria-hidden="true">🛏 </span>
            {nearby.length} Unterkünfte ≤ {LODGING_MAX_DIST_M.toLocaleString("de-DE")} m vom Weg
          </span>
          <span className="ml-auto">{ATTRIBUTION.join(" · ")}</span>
        </div>
      </div>
    </div>
  );
}

function addTrailLayers(map: MapLibreMap, features: FeatureCollection) {
  if (map.getSource("trail")) (map.getSource("trail") as GeoJSONSource).setData(features);
  else map.addSource("trail", { type: "geojson", data: features });
  const isStage: FilterSpecification = ["==", ["get", "kind"], "stage"];
  map.addLayer({
    id: "trail-casing",
    type: "line",
    source: "trail",
    filter: isStage,
    layout: { "line-join": "round", "line-cap": "round" },
    paint: { "line-color": "#ffffff", "line-width": 7, "line-opacity": 0.85 },
  });
  map.addLayer({
    id: "trail-stages",
    type: "line",
    source: "trail",
    filter: isStage,
    layout: { "line-join": "round", "line-cap": "round" },
    paint: {
      "line-color": ["case", ["==", ["%", ["get", "seq"], 2], 1], STAGE_RED[0], STAGE_RED[1]],
      "line-width": 4,
    },
  });
  map.addLayer({
    id: "trail-boundaries",
    type: "circle",
    source: "trail",
    filter: ["==", ["get", "kind"], "boundary"],
    paint: {
      "circle-radius": 6,
      "circle-color": "#ffffff",
      "circle-stroke-color": STAGE_RED[1],
      "circle-stroke-width": 3,
    },
  });
}

function lodgingName(l: LodgingOnTrail): string {
  return l.name ?? lodgingKind(l.kind);
}

/** dist_m as imported — never estimated. */
function distance(l: LodgingOnTrail): string {
  return `${l.dist_m!.toLocaleString("de-DE")} m vom Weg`;
}

function lodgingPopup(l: LodgingOnTrail): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = lodgingName(l);
  const meta = document.createElement("div");
  meta.textContent = `${lodgingKind(l.kind)} · ${distance(l)}`;
  root.append(title, meta);
  const href = safeWebsite(l.website);
  if (href) {
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = "Website";
    root.append(a);
  }
  return root;
}
