import Link from "next/link";
import { notFound } from "next/navigation";
import Block from "../../../components/Block";
import ChatShell from "../../../components/ChatShell";
import GroupList from "../../../components/GroupList";
import LodgingList from "../../../components/LodgingList";
import Notice from "../../../components/Notice";
import PageFrame from "../../../components/PageFrame";
import PhotoSwitcher from "../../../components/PhotoSwitcher";
import PoiList from "../../../components/PoiList";
import StageCards from "../../../components/StageCards";
import TourDescription, { hasDescription } from "../../../components/TourDescription";
import TourMerken from "../../../components/TourMerken";
import TrailMap from "../../../components/TrailMap";
import {
  GROUP_RADIUS_KM,
  getGroups,
  getLodgings,
  getTrail,
  getTrailPois,
  getTrailTags,
  groupsNearLine,
  type LodgingOnTrail,
  type TrailDetail,
  type TrailPoi,
} from "../../../lib/data";
import { hm, hmDown, km, walkingTime } from "../../../lib/format";
import { mapTrail } from "../../../lib/map";
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
  // Only the exact values count; anything else (missing, other strings, arrays) goes home.
  const chat = fromChat((await searchParams)?.von);
  const back = chat ? { href: "/", label: "← Zurück zu den Vorschlägen" } : { href: "/", label: "← Startseite" };
  let trail: TrailDetail | null;
  try {
    trail = await getTrail(trailId);
  } catch (e) {
    console.error(`getTrail(${trailId}) failed:`, e);
    return (
      <PageFrame back={back}>
        <Notice title="Daten konnten nicht geladen werden.">
          <p>Die Datenbank ist nicht erreichbar oder nicht konfiguriert. Bitte später erneut versuchen.</p>
        </Notice>
      </PageFrame>
    );
  }
  if (!trail) notFound();

  const [lodgings, pois, tags, groupRows] = await Promise.all([
    orNull<LodgingOnTrail[]>(`getLodgings(${trailId})`, () => getLodgings(trailId)),
    orNull<TrailPoi[]>(`getTrailPois(${trailId})`, () => getTrailPois(trailId)),
    orNull(`getTrailTags(${trailId})`, () => getTrailTags(trailId)),
    orNull("getGroups", () => getGroups()),
  ]);
  // „Gruppen in der Nähe“ and tags: failure or no geometry just leaves them out.
  const groups = groupRows && trail.geom ? groupsNearLine(groupRows, trail.geom.coordinates, new Date()) : [];

  const longDistance = trail.kind === "long_distance";
  const time = longDistance ? null : walkingTime(trail);
  const facts: [string, string][] = [
    ["Länge", km(trail.length_km)],
    ["Aufstieg", hm(trail.ascent_m)],
    ["Abstieg", hmDown(trail.descent_m)],
    ...(time ? ([["Gehzeit", time]] as [string, string][]) : []),
    ...(longDistance ? ([["Etappen", String(trail.stages.length)]] as [string, string][]) : []),
  ];

  const description = {
    sentence: longDistance
      ? null
      : describeTour({ roundtrip: (tags ?? []).includes("feature:rundweg"), length_km: trail.length_km, ascent_m: trail.ascent_m, time, pois: pois ?? [] }),
    tags: tagLabels(tags ?? []),
    surface: surfaceLine(trail.surface_shares ?? null),
    profile: trail.profile ?? null,
  };
  const showDescription = !longDistance && hasDescription(description);
  const showLodgings = lodgings === null || lodgings.length > 0;
  const showPois = pois === null || pois.length > 0;
  const showPhotos = trail.photos.length > 0;

  return (
    <PageFrame back={back} wide>
      <section className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="text-sm text-papier/80">{longDistance ? "Fernweg" : "Tagestour"}</p>
          <h1 className="font-serif text-3xl leading-tight sm:text-5xl">{trail.name}</h1>
          <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2">
            {facts.map(([label, value]) => (
              <div key={label} className="flex flex-col">
                <dt className="text-xs text-papier/75">{label}</dt>
                <dd className="font-serif text-xl tabular-nums sm:text-2xl">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!longDistance && <TourMerken trailId={trailId} />}
          <Link
            href={`/unterwegs?trail=${encodeURIComponent(trailId)}`}
            className="rounded-full border border-white/30 px-4 py-2 text-sm text-papier hover:bg-white/10 focus-visible:outline-2 focus-visible:outline-papier"
          >
            Unterwegs
          </Link>
        </div>
      </section>

      <div className="max-w-xl">
        <ChatShell
          intro={
            longDistance
              ? `Der ${trail.name} hat ${trail.stages.length} Etappen. Frag z. B. „3 Tage ab Hausach, etwa 15 km pro Tag“.`
              : `${trail.name}${trail.length_km === null ? "" : `: ${km(trail.length_km)}`}. Frag z. B. nach einer ähnlichen Tour oder einer kürzeren Variante.`
          }
          variant="drawer"
        />
      </div>

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
        <section aria-label="Etappen">
          <StageCards trail={trail} />
        </section>
      )}

      {(showDescription || showLodgings) && (
        <div className={`grid gap-4 ${showDescription && showLodgings ? "md:grid-cols-[2fr_1fr]" : ""}`}>
          {showDescription && (
            <Block title="Beschreibung">
              <TourDescription {...description} trailId={trailId} />
            </Block>
          )}
          {showLodgings && (
            <Block title="Übernachten in der Nähe">
              {lodgings === null ? <p className="text-sm">Unterkünfte konnten nicht geladen werden.</p> : <LodgingList lodgings={lodgings} />}
            </Block>
          )}
        </div>
      )}

      {(showPhotos || groups.length > 0 || showPois) && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {showPhotos && (
            <Block title="Fotos">
              <PhotoSwitcher photos={trail.photos} trailId={trailId} />
            </Block>
          )}
          {groups.length > 0 && (
            <Block title="Gruppen in der Nähe">
              <GroupList
                groups={groups}
                note={`Stand: ${new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }).format(new Date(`${groups.map((g) => g.checked_at).sort()[0]}T00:00:00Z`))} · bis ${GROUP_RADIUS_KM} km vom Weg`}
              />
            </Block>
          )}
          {showPois && (
            <Block title="Einkehr & Aussicht">
              {pois === null ? <p className="text-sm">Einkehr und Aussicht konnten nicht geladen werden.</p> : <PoiList pois={pois} />}
            </Block>
          )}
        </div>
      )}

      <footer className="text-[11px] text-papier/75">
        Quellen:{" "}
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
        {" · "}Höhen: Copernicus DEM GLO-30 © DLR e.V./Airbus, bereitgestellt von EU/ESA
        {" · "}Gehzeit nach DIN 33466 (Richtwert, ohne Pausen)
        {pois && pois.length > 0 && " · Einkehr und Aussicht: © OpenStreetMap-Mitwirkende (ODbL)"}
      </footer>
    </PageFrame>
  );
}
