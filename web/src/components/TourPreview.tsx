"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useLocale, useT } from "../i18n";
import type { Labels, TourCard } from "../lib/chat";
import { coverOf } from "../lib/chatState";
import { getLodgings, getTrail, getTrailPois, getTrailTags, type LodgingOnTrail, type TrailPoi } from "../lib/data";
import { duration, num, walkingTime } from "../lib/format";
import { mapTrail, type MapTrail } from "../lib/map";
import { describeTour } from "../lib/tour";
import Attribution from "./Attribution";
import MerkenButton from "./MerkenButton";
import TrailMap from "./TrailMap";
import { VerdictChips } from "./WishChips";

type Loaded = { trail: MapTrail; lengthKm: number | null; lodgings: LodgingOnTrail[] | null; pois: TrailPoi[]; sentence: string | null } | "error" | null;

/** Exactly one tour found: the tour with description and map right on the home page, one click from its page. */
/** `fallback`: the search had to relax a wish; then the tour is the nearest match, never „passt“. */
export default function TourPreview({ card, runWithoutPace, fallback = false }: { card: TourCard; runWithoutPace: boolean; labels: Labels; fallback?: boolean }) {
  const { locale } = useLocale();
  const t = useT().tour;
  const [loaded, setLoaded] = useState<Loaded>(null);

  useEffect(() => {
    let live = true;
    setLoaded(null);
    (async () => {
      const t = await getTrail(card.trail_id);
      if (!t) return "error" as const;
      const [lodgings, pois, tags] = await Promise.all([
        getLodgings(card.trail_id).catch(() => null),
        getTrailPois(card.trail_id).catch(() => [] as TrailPoi[]),
        getTrailTags(card.trail_id).catch(() => [] as string[]),
      ]);
      const sentence = describeTour({ roundtrip: tags.includes("feature:rundweg"), length_km: t.length_km, ascent_m: t.ascent_m, time: walkingTime(t, locale), pois }, locale);
      return { trail: mapTrail(t), lengthKm: t.length_km, lodgings, pois, sentence };
    })()
      .catch((e) => {
        console.error(`preview ${card.trail_id} failed:`, e);
        return "error" as const;
      })
      .then((r) => live && setLoaded(r));
    return () => {
      live = false;
    };
  }, [card.trail_id, locale]);

  const photo = coverOf(card);
  const facts = [
    card.length_km === null ? null : `${num(card.length_km, locale, { min: 1 })} km`,
    card.ascent_m === null ? null : `↑ ${num(card.ascent_m, locale, { max: 0 })} m`,
    card.duration_h !== null ? duration(card.duration_h, locale) : runWithoutPace ? t.stateYourPace : null,
    card.distance_km === null ? t.inTheArea : t.kmToStart(num(card.distance_km, locale, { min: 1 })),
  ].filter((f): f is string => !!f);
  const href = `/t/${card.trail_id}?von=chat`;

  return (
    <article className="flex flex-col gap-4 rounded-2xl bg-papier p-4 text-wald-dunkel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-wald-dunkel/70">{fallback ? t.previewFallback : t.previewFits}</p>
          <h2 className="font-serif text-2xl sm:text-3xl">{card.name}</h2>
          <p className="tabular-nums">{facts.join(" · ")}</p>
        </div>
        <div className="flex items-center gap-2">
          <MerkenButton kind="day_hike" title={card.name} payload={card} />
          <Link href={href} className="rounded-full bg-wald px-5 py-2 text-sm font-medium text-papier hover:bg-wald-dunkel">
            {t.toTour}
          </Link>
        </div>
      </div>
      <VerdictChips results={card.results} />
      {card.deviation_text && <p className="text-sm text-red-800">{card.deviation_text}</p>}
      <div className={`grid gap-4 ${photo ? "lg:grid-cols-[2fr_1fr]" : ""}`}>
        <div className="flex min-w-0 flex-col gap-3">
          {loaded === null && <p role="status" className="text-sm">{t.mapLoading}</p>}
          {loaded === "error" && <p className="text-sm">{t.mapFailed}</p>}
          {loaded && loaded !== "error" && (
            <>
              {loaded.sentence && <p className="text-base leading-relaxed">{loaded.sentence}</p>}
              <TrailMap trailId={card.trail_id} fromChat trail={loaded.trail} lodgings={loaded.lodgings} lengthKm={loaded.lengthKm} pois={loaded.pois} embedded />
            </>
          )}
        </div>
        {/* the map comes first; the photo joins it beside only when there is room */}
        {photo && (
          <figure className="hidden flex-col gap-1 lg:flex">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={photo.thumb_url} alt="" className="aspect-[4/3] w-full rounded-xl object-cover" />
            <Attribution photo={photo} className="text-wald-dunkel/70" />
          </figure>
        )}
      </div>
    </article>
  );
}
