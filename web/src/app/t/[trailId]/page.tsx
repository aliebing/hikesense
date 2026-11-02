import Link from "next/link";
import { notFound } from "next/navigation";
import Attribution from "../../../components/Attribution";
import Backdrop from "../../../components/Backdrop";
import Block from "../../../components/Block";
import GroupList from "../../../components/GroupList";
import LodgingList from "../../../components/LodgingList";
import Notice from "../../../components/Notice";
import PageFrame from "../../../components/PageFrame";
import PhotoSwitcher from "../../../components/PhotoSwitcher";
import PoiList from "../../../components/PoiList";
import StageCards from "../../../components/StageCards";
import TourDescription from "../../../components/TourDescription";
import { hasDescription } from "../../../lib/tourDescription";
import TourMerken from "../../../components/TourMerken";
import TrailMap from "../../../components/TrailMap";
import {
  GROUP_RADIUS_KM,
  getGroups,
  getLandscapePool,
  getLodgings,
  getTrail,
  getTrailPois,
  getTrailTags,
  groupsNearLine,
  type LodgingOnTrail,
  type TrailDetail,
  type TrailPoi,
} from "../../../lib/data";
import { messagesFor } from "../../../i18n/locale";
import { getServerLocale } from "../../../i18n/server";
import { dateIn, hm, hmDown, km, walkingTime } from "../../../lib/format";
import { mapTrail } from "../../../lib/map";
import { pickBackdrop } from "../../../lib/backdrop";
import { describeTour, surfaceLine, tagLabels } from "../../../lib/tour";
import { fromChat } from "../../../lib/von";

export const dynamic = "force-dynamic";

/** null when loading failed (the block says so); [] when there is nothing (the block falls away). */
async function orNull<T>(what: string, load: () => Promise<T>): Promise<T | null> {
  try {
    return await load();
  } catch (e) {
    console.error(`${what} failed:`, e);
    return null;
  }
}

export default async function TrailPage({
  params,
  searchParams,
}: {
  params: Promise<{ trailId: string }>;
  searchParams?: Promise<{ von?: string | string[] }>;
}) {
  const { trailId } = await params;
  const locale = await getServerLocale();
  const t = messagesFor(locale).tour;
  // Only the exact values count; anything else (missing, other strings, arrays) goes home.
  const chat = fromChat((await searchParams)?.von);
  const back = chat ? { href: "/", label: t.backChat } : { href: "/", label: t.backHome };
  let trail: TrailDetail | null;
  try {
    trail = await getTrail(trailId);
  } catch (e) {
    console.error(`getTrail(${trailId}) failed:`, e);
    return (
      <PageFrame back={back}>
        <Notice title={t.loadErrorTitle}>
          <p>{t.loadErrorBody}</p>
        </Notice>
      </PageFrame>
    );
  }
  if (!trail) notFound();

  const [lodgings, pois, tags, groupRows, pool] = await Promise.all([
    orNull<LodgingOnTrail[]>(`getLodgings(${trailId})`, () => getLodgings(trailId)),
    orNull<TrailPoi[]>(`getTrailPois(${trailId})`, () => getTrailPois(trailId)),
    orNull(`getTrailTags(${trailId})`, () => getTrailTags(trailId)),
    orNull("getGroups", () => getGroups()),
    orNull("getLandscapePool", () => getLandscapePool()),
  ]);
  // „Gruppen in der Nähe“ and tags: failure or no geometry just leaves them out.
  const groups = groupRows && trail.geom ? groupsNearLine(groupRows, trail.geom.coordinates, new Date()) : [];

  const longDistance = trail.kind === "long_distance";
  const time = longDistance ? null : walkingTime(trail, locale);
  const facts: [string, string][] = [
    [t.factLength, km(trail.length_km, locale)],
    [t.factAscent, hm(trail.ascent_m, locale)],
    [t.factDescent, hmDown(trail.descent_m, locale)],
    ...(time ? ([[t.factTime, time]] as [string, string][]) : []),
    ...(longDistance ? ([[t.factStages, String(trail.stages.length)]] as [string, string][]) : []),
  ];

  const description = {
    sentence: longDistance
      ? null
      : describeTour({ roundtrip: (tags ?? []).includes("feature:rundweg"), length_km: trail.length_km, ascent_m: trail.ascent_m, time, pois: pois ?? [] }, locale),
    tags: tagLabels(tags ?? [], locale),
    surface: surfaceLine(trail.surface_shares ?? null, locale),
    profile: trail.profile ?? null,
  };
  const showDescription = !longDistance && hasDescription(description);
  const showLodgings = lodgings === null || lodgings.length > 0;
  const showPois = pois === null || pois.length > 0;
  const showPhotos = trail.photos.length > 0;

  // a landscape behind the page: the tour's own if it has one, else a steady pick from the pool
  const backdrop = pickBackdrop([...(trail.cover ? [trail.cover] : []), ...trail.photos], pool ?? [], trailId);

  return (
    <PageFrame wide>
      <Backdrop photo={backdrop} />
      <Link
        href={back.href}
        className="self-start rounded-full bg-papier px-5 py-2 text-sm font-semibold text-wald-dunkel shadow-lg hover:bg-white focus-visible:outline-2 focus-visible:outline-papier"
      >
        {back.label}
      </Link>
      {/* three full-width rows, each on its own green field: kind, name, facts (with the actions on the right) */}
      <section className="flex flex-col gap-1.5">
        <p className="schrift-feld w-full px-4 py-1 text-sm font-medium text-papier">{longDistance ? t.longDistance : t.dayHike}</p>
        <h1 className="schrift-feld w-full px-4 py-1.5 font-serif text-2xl leading-tight font-semibold sm:text-3xl">{trail.name}</h1>
        <div className="schrift-feld flex w-full flex-wrap items-center justify-between gap-3 px-4 py-2">
          <dl className="flex flex-wrap gap-x-5 gap-y-1">
            {facts.map(([label, value]) => (
              <div key={label} className="flex flex-col">
                <dt className="text-xs font-medium text-papier">{label}</dt>
                <dd className="font-serif text-lg font-semibold tabular-nums">{value}</dd>
              </div>
            ))}
          </dl>
          <div className="flex flex-wrap items-center gap-2">
            {!longDistance && <TourMerken trailId={trailId} />}
            <Link
              href={`/unterwegs?trail=${encodeURIComponent(trailId)}`}
              className="rounded-full border border-white/60 bg-wald-dunkel/90 px-4 py-2 text-sm font-medium text-papier hover:bg-wald focus-visible:outline-2 focus-visible:outline-papier"
            >
              {t.onTheTrail}
            </Link>
          </div>
        </div>
      </section>

      <TrailMap
        trailId={trailId}
        fromChat={chat}
        trail={mapTrail(trail)}
        lodgings={lodgings}
        lengthKm={trail.length_km}
        pois={pois ?? []}
        embedded
      />

      {longDistance && (
        <section aria-label={t.stagesLabel}>
          <StageCards trail={trail} />
        </section>
      )}

      {(showDescription || showLodgings) && (
        <div className={`grid gap-4 ${showDescription && showLodgings ? "md:grid-cols-[2fr_1fr]" : ""}`}>
          {showDescription && (
            <Block title={t.description}>
              <TourDescription {...description} trailId={trailId} />
            </Block>
          )}
          {showLodgings && (
            <Block title={t.lodgingTitle}>
              {lodgings === null ? <p className="text-sm">{t.lodgingsFailed}</p> : <LodgingList lodgings={lodgings} place={trail.name} />}
            </Block>
          )}
        </div>
      )}

      {(showPhotos || groups.length > 0 || showPois) && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {showPhotos && (
            <Block title={t.photos}>
              <PhotoSwitcher photos={trail.photos} trailId={trailId} />
            </Block>
          )}
          {groups.length > 0 && (
            <Block title={t.groupsTitle}>
              <GroupList
                groups={groups}
                note={t.groupsNote(dateIn(new Date(`${groups.map((g) => g.checked_at).sort()[0]}T00:00:00Z`), locale, { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }), GROUP_RADIUS_KM)}
              />
            </Block>
          )}
          {showPois && (
            <Block title={t.poiTitle}>
              {pois === null ? <p className="text-sm">{t.poiFailed}</p> : <PoiList pois={pois} />}
            </Block>
          )}
        </div>
      )}

      <footer className="schrift-feld text-[11px] text-papier">
        {t.sources}{" "}
        {trail.sources.map((s, i) => (
          <span key={s.id}>
            {i > 0 && " · "}
            {s.url ? (
              <a href={s.url} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2">
                {s.name}
              </a>
            ) : (
              s.name
            )}
            {s.license && ` (${s.license})`}
          </span>
        ))}
        {" · "}{t.footerElevation}
        {" · "}{t.footerTime}
        {pois && pois.length > 0 && ` · ${t.footerOsm}`}
        {backdrop && (
          <div className="mt-1 flex flex-wrap items-baseline gap-1">
            {t.backdrop} <Attribution photo={backdrop} />
          </div>
        )}
      </footer>
    </PageFrame>
  );
}
