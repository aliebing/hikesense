"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import type { FeatureCollection } from "geojson";
import type { FilterSpecification, GeoJSONSource, Map as MapLibreMap, Marker } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import type { LodgingOnTrail, TrailPoi } from "../lib/data";
import { messagesFor, useLocale, useT, type Locale } from "../i18n";
import { num } from "../lib/format";
import { POI_KIND, poiKindLabel } from "../lib/tour";
import {
  attribution,
  BASEMAP_STYLE,
  LODGING_MAX_DIST_M,
  OSM_RASTER_STYLE,
  bboxOf,
  dayFeatures,
  lodgingKind,
  lodgingsNearby,
  safeWebsite,
  trailToFeatures,
  type DaySection,
  type MapTrail,
} from "../lib/map";

/** Two alternating reds so neighbouring stages stay distinguishable. */
const STAGE_RED = ["#d62839", "#8a1526"] as const;

type Status = "loading" | "ready" | "error" | "no-webgl";

/** maplibre throws (or fires) this when no WebGL2 context can be created. */
const isNoWebGL = (e: unknown) => (e as { name?: unknown } | null)?.name === "GPUInitializationError";

/** Below this zoom lodgings are drawn as small dots. */
const LODGING_FULL_ZOOM = 11;

/**
 * „🗺 Karte“ button plus a full-screen overlay with the trail map
 * (basemap.de vector tiles, OSM raster as fallback). maplibre-gl is loaded
 * only in the browser, when the overlay opens.
 */
export default function MapPanel({
  trail,
  lodgings,
  days,
  position,
  pois,
  embedded = false,
}: {
  trail: MapTrail;
  /** null when the lodgings could not be loaded — then the legend says so instead of „0“;
   *  omitted: no lodging layer at all (e.g. „Unterwegs“), and the legend names none */
  lodgings?: LodgingOnTrail[] | null;
  /** plan days: drawn instead of the stages, alternating colours; `lodgings` are then the day-end lodgings */
  days?: DaySection[];
  /** own position (Unterwegs): shown as a dot, never sent anywhere */
  position?: { lat: number; lon: number } | null;
  /** food, huts, viewpoints, peaks, waterfalls along the trail: drawn as markers */
  pois?: TrailPoi[];
  /** the map sits in the page (no click needed); full screen stays available as an extra button */
  embedded?: boolean;
}) {
  const t = useT().map;
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

  const view = { trail, lodgings, days, position, pois };
  const overlay = open && <MapOverlay {...view} closer={closer} onClose={() => setOpen(false)} />;

  if (embedded) {
    return (
      <section aria-label={t.mapOf(trail.name)} className="flex flex-col overflow-hidden rounded-2xl bg-wald-flaeche ring-1 ring-white/10">
        <div className="relative h-[55vh] min-h-80">
          {/* the overlay draws its own map; this one stays mounted underneath */}
          <MapView {...view} cooperative />
          <button
            ref={opener}
            type="button"
            aria-haspopup="dialog"
            onClick={() => setOpen(true)}
            className="absolute top-2 left-2 rounded-full bg-wald-dunkel/90 px-3 py-1 text-sm text-papier shadow hover:bg-wald-dunkel focus-visible:outline-2 focus-visible:outline-papier"
          >
            {t.fullscreen}
          </button>
        </div>
        <MapLegend {...view} />
        {overlay}
      </section>
    );
  }

  return (
    <>
      <button
        ref={opener}
        type="button"
        aria-haspopup="dialog"
        aria-label={t.open}
        onClick={() => setOpen(true)}
        className="self-start justify-self-start rounded-full border border-white/25 bg-wald-flaeche px-4 py-2 text-sm text-papier hover:bg-wald focus-visible:outline-2 focus-visible:outline-papier md:justify-self-end"
      >
        <span aria-hidden="true">🗺 </span>{t.openLabel}
      </button>
      {overlay}
    </>
  );
}

type ViewProps = {
  trail: MapTrail;
  lodgings?: LodgingOnTrail[] | null;
  days?: DaySection[];
  position?: { lat: number; lon: number } | null;
  pois?: TrailPoi[];
};

/** Lodgings drawn on the map: with plan days the day-end lodgings (up to 2 km off, all shown), else those near the trail. */
function useNearby(lodgings: LodgingOnTrail[] | null | undefined, days: DaySection[] | undefined) {
  const planDays = !!days && days.length > 0;
  return useMemo(() => (lodgings ? (planDays ? lodgings : lodgingsNearby(lodgings)) : []), [lodgings, planDays]);
}

/** `cooperative`: an embedded map lets one finger scroll the page (two fingers / Ctrl+wheel move the map). */
function MapView({ trail, lodgings, days, position, pois, cooperative = false }: ViewProps & { cooperative?: boolean }) {
  const { locale } = useLocale();
  const t = useT().map;
  // the map outlives a language switch: the effect reads texts through refs and relabels the markers separately
  const localeRef = useRef(locale);
  localeRef.current = locale;
  const textsRef = useRef(t);
  textsRef.current = t;
  const relabel = useRef<((l: Locale) => void)[]>([]);
  const container = useRef<HTMLDivElement>(null);
  const live = useRef<{ map: MapLibreMap; ml: typeof import("maplibre-gl"); me?: Marker } | null>(null);
  const posRef = useRef(position);
  posRef.current = position;
  const [status, setStatus] = useState<Status>("loading");
  const features = useMemo(() => (days && days.length > 0 ? dayFeatures(days) : trailToFeatures(trail)), [trail, days]);
  const nearby = useNearby(lodgings, days);
  const poiList = useMemo(() => pois ?? [], [pois]);

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
          cooperativeGestures: cooperative,
          // maplibre's own hints are English; both languages come from the catalog
          locale: {
            "CooperativeGesturesHandler.WindowsHelpText": textsRef.current.gestureWin,
            "CooperativeGesturesHandler.MacHelpText": textsRef.current.gestureMac,
            "CooperativeGesturesHandler.MobileHelpText": textsRef.current.gestureMobile,
          },
          ...(bbox ? { bounds: bbox, fitBoundsOptions: { padding: 40 } } : { center: [8.7, 48.55], zoom: 6.5 }),
        });
        map.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
        live.current = { map, ml };
        showPosition(live.current, posRef.current, textsRef.current.yourPosition);
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
          if (isNoWebGL(e.error)) {
            // WebGL context lost and not recreated: nothing can be drawn any more.
            console.error("map failed:", e.error);
            setStatus("no-webgl");
          } else if (styleLoaded) {
            // A single tile or image failing later: the map stays usable.
          } else if (!fellBack) {
            // A failing basemap.de style: switch to OSM raster tiles once.
            fellBack = true;
            console.warn("basemap.de style failed, using OSM raster tiles:", e.error?.message);
            map!.setStyle(OSM_RASTER_STYLE);
          } else {
            // The OSM fallback failed as well: say so instead of loading forever.
            console.error("map failed (OSM fallback):", e.error);
            setStatus("error");
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

        relabel.current = [];
        const loc = localeRef.current;
        for (const l of nearby) {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "map-lodging";
          el.textContent = "🛏";
          el.setAttribute("aria-label", `${lodgingName(l, loc)}, ${distance(l, loc)}`);
          const popup = new ml.Popup({ offset: 14, maxWidth: "260px" }).setDOMContent(lodgingPopup(l, loc));
          relabel.current.push((x) => {
            el.setAttribute("aria-label", `${lodgingName(l, x)}, ${distance(l, x)}`);
            popup.setDOMContent(lodgingPopup(l, x));
          });
          markers.push(new ml.Marker({ element: el }).setLngLat([l.lon, l.lat]).setPopup(popup).addTo(map));
        }
        for (const q of poiList) {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "map-poi";
          el.textContent = POI_KIND[q.kind].icon;
          el.setAttribute("aria-label", poiLabel(q, loc));
          const popup = new ml.Popup({ offset: 14, maxWidth: "240px" }).setDOMContent(poiPopup(q, loc));
          relabel.current.push((x) => {
            el.setAttribute("aria-label", poiLabel(q, x));
            popup.setDOMContent(poiPopup(q, x));
          });
          markers.push(new ml.Marker({ element: el }).setLngLat([q.lon, q.lat]).setPopup(popup).addTo(map));
        }
      })
      .catch((e) => {
        console.error("map failed:", e);
        if (!cancelled) setStatus(isNoWebGL(e) ? "no-webgl" : "error");
      });

    return () => {
      cancelled = true;
      live.current = null;
      markers.forEach((m) => m.remove());
      map?.remove();
    };
  }, [features, nearby, poiList, cooperative]);

  // a language switch only relabels markers and popups; the map instance (viewport, open popups) stays
  useEffect(() => {
    for (const f of relabel.current) f(locale);
  }, [locale]);

  useEffect(() => {
    if (live.current) showPosition(live.current, position, t.yourPosition);
  }, [position, t.yourPosition]);

  return (
    <div className="relative h-full min-h-0 flex-1 bg-papier/10">
      {/* maplibre's CSS makes its container position: relative, so it fills an absolute wrapper. */}
      <div className="absolute inset-0">
        <div ref={container} data-map-status={status} className="h-full w-full bg-[#eef0ea]" />
      </div>
      {status !== "ready" && (
        // Dark box on the light map background, so the text stays readable.
        <div className="absolute inset-0 grid place-items-center p-4">
          <p
            role={status === "loading" ? "status" : "alert"}
            className="max-w-md rounded-xl bg-wald-dunkel/90 px-4 py-3 text-center text-sm text-papier shadow-lg"
          >
            {status === "loading" ? t.loading : status === "error" ? t.error : t.noWebgl}
          </p>
        </div>
      )}
    </div>
  );
}

function MapLegend({ trail, lodgings, days, pois }: ViewProps) {
  const { locale } = useLocale();
  const t = useT().map;
  const pg = useT().tour.poiGroups;
  const nearby = useNearby(lodgings, days);
  const planDays = !!days && days.length > 0;
  const groups = new Set((pois ?? []).map((q) => POI_KIND[q.kind].group));
  return (
    <div data-testid="map-legend" className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-2 text-[11px] text-papier/85">
      <span className="flex items-center gap-1">
        <span aria-hidden="true" className="inline-block h-1 w-5 rounded" style={{ background: `linear-gradient(90deg, ${STAGE_RED[0]} 50%, ${STAGE_RED[1]} 50%)` }} />
        {planDays ? t.days : trail.stages.length > 0 ? t.stages : t.tour}
      </span>
      {lodgings !== undefined && (lodgings === null || planDays || nearby.length > 0) && (
        <span>
          <span aria-hidden="true">🛏 </span>
          {lodgings === null
            ? t.lodgingsFailed
            : planDays
              ? t.lodgingsDayEnd
              : t.lodgingsNear(nearby.length, num(LODGING_MAX_DIST_M, locale))}
        </span>
      )}
      {lodgings !== undefined && days?.filter((d) => d.lodging_missing).map((d) => (
        <span key={d.day}>{t.lodgingMissing(d.day)}</span>
      ))}
      {groups.has("einkehr") && <span><span aria-hidden="true">☕ </span>{pg.einkehr}</span>}
      {groups.has("aussicht") && <span><span aria-hidden="true">👁 </span>{pg.aussicht}</span>}
      {groups.has("wasserfall") && <span><span aria-hidden="true">💧 </span>{pg.wasserfall}</span>}
      <span className="ml-auto">{attribution(locale).join(" · ")}</span>
    </div>
  );
}

function MapOverlay({ closer, onClose, ...view }: ViewProps & { closer: React.RefObject<HTMLButtonElement | null>; onClose: () => void }) {
  const t = useT().map;
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
            {t.mapOf(view.trail.name)}
          </h2>
          <button
            ref={closer}
            type="button"
            onClick={onClose}
            aria-label={t.close}
            className="rounded-full px-3 py-1 text-sm text-papier/90 hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-papier"
          >
            {t.closeText} <span aria-hidden="true">✕</span>
          </button>
        </div>
        <MapView {...view} />
        <MapLegend {...view} />
      </div>
    </div>
  );
}

/** The own-position dot: created on the first fix, moved afterwards, removed when the position is gone. */
function showPosition(l: { map: MapLibreMap; ml: typeof import("maplibre-gl"); me?: Marker }, pos: { lat: number; lon: number } | null | undefined, label: string) {
  if (!pos) {
    l.me?.remove();
    l.me = undefined;
    return;
  }
  if (!l.me) {
    const el = document.createElement("div");
    el.className = "map-me";
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", label);
    l.me = new l.ml.Marker({ element: el }).setLngLat([pos.lon, pos.lat]).addTo(l.map);
  } else {
    l.me.setLngLat([pos.lon, pos.lat]);
  }
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

function lodgingName(l: LodgingOnTrail, locale: Locale): string {
  return l.name ?? lodgingKind(l.kind, locale);
}

/** dist_m as imported — never estimated. */
function distance(l: LodgingOnTrail, locale: Locale): string {
  return messagesFor(locale).map.fromTrail(num(l.dist_m!, locale));
}

function lodgingPopup(l: LodgingOnTrail, locale: Locale): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const title = document.createElement("strong");
  title.textContent = lodgingName(l, locale);
  const meta = document.createElement("div");
  meta.textContent = `${lodgingKind(l.kind, locale)} · ${distance(l, locale)}`;
  root.append(title, meta);
  const href = safeWebsite(l.website);
  if (href) {
    const a = document.createElement("a");
    a.href = href;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.textContent = messagesFor(locale).map.website;
    root.append(a);
  }
  return root;
}

/** „Name, Art, km 3,2“; without a name just the kind, without along_km no km. */
function poiLabel(q: TrailPoi, locale: Locale): string {
  const kind = poiKindLabel(q.kind, locale);
  const parts = q.name ? [q.name, kind] : [kind];
  if (q.along_km !== null) parts.push(`km ${num(q.along_km, locale, { min: 1 })}`);
  return parts.join(", ");
}

function poiPopup(q: TrailPoi, locale: Locale): HTMLElement {
  const root = document.createElement("div");
  root.className = "map-popup";
  const kind = poiKindLabel(q.kind, locale);
  const title = document.createElement("strong");
  title.textContent = q.name ?? kind;
  const meta = document.createElement("div");
  meta.textContent = q.along_km === null ? kind : `${kind} · ${messagesFor(locale).map.alongTrail(num(q.along_km, locale, { min: 1 }))}`;
  root.append(title, meta);
  return root;
}
