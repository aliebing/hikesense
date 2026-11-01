import Link from "next/link";
import { notFound } from "next/navigation";
import ChatShell from "../../../components/ChatShell";
import Notice from "../../../components/Notice";
import PageFrame from "../../../components/PageFrame";
import PhotoSwitcher from "../../../components/PhotoSwitcher";
import StageCards, { Facts } from "../../../components/StageCards";
import TrailMap from "../../../components/TrailMap";
import GroupList from "../../../components/GroupList";
import { GROUP_RADIUS_KM, getGroups, getLodgings, getTrail, groupsNearLine, type LodgingOnTrail, type TrailDetail } from "../../../lib/data";
import { hm, hmDown, km, walkingTime } from "../../../lib/format";
import { mapTrail } from "../../../lib/map";

export const dynamic = "force-dynamic";

export default async function TrailPage({
  params,
  searchParams,
}: {
  params: Promise<{ trailId: string }>;
  searchParams?: Promise<{ von?: string | string[] }>;
}) {
  const { trailId } = await params;
  // Only the exact value counts; anything else (missing, other strings, arrays) goes home.
  const von = (await searchParams)?.von;
  const back =
    von === "vorschlaege"
      ? { href: "/vorschlaege", label: "← Zu den Vorschlägen" }
      : { href: "/", label: "← Zur Startseite" };
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

  // Lodgings only feed the map; without them the map still shows the trail
  // and its legend says they could not be loaded (null, never „0“).
  let lodgings: LodgingOnTrail[] | null = null;
  try {
    lodgings = await getLodgings(trailId);
  } catch (e) {
    console.error(`getLodgings(${trailId}) failed:`, e);
  }

  // „Gruppen in der Nähe“: failure or no geometry just leaves the section out.
  let groups: ReturnType<typeof groupsNearLine> = [];
  try {
    if (trail.geom) groups = groupsNearLine(await getGroups(), trail.geom.coordinates, new Date());
  } catch (e) {
    console.error("getGroups failed:", e);
  }

  const longDistance = trail.kind === "long_distance";
  const meta = [
    longDistance ? `Fernweg · ${trail.stages.length} Etappen` : "Tagestour",
    km(trail.length_km),
    hm(trail.ascent_m),
    hmDown(trail.descent_m),
  ];
  const time = longDistance ? null : walkingTime(trail);
  if (time) meta.push(time);

  return (
    <PageFrame back={back}>
      <section>
        <h1 className="font-serif text-3xl leading-tight sm:text-5xl">{trail.name}</h1>
        <Facts items={meta} className="mt-1 text-sm text-papier/90" />
      </section>

      <div className="grid gap-4 md:grid-cols-[minmax(0,24rem)_1fr]">
        <ChatShell
          intro={
            longDistance
              ? `Der ${trail.name} hat ${trail.stages.length} Etappen. Bald kannst du hier fragen, z. B. „3 Tage ab Hausach, etwa 15 km pro Tag“.`
              : `${trail.name}${trail.length_km === null ? "" : `: ${km(trail.length_km)}`}. Bald kannst du hier fragen, ob die Tour zu dir und zum Wetter passt.`
          }
          variant="drawer"
        />
        <div data-slot="map" className="grid">
          <TrailMap
            trailId={trailId}
            fromSuggestions={von === "vorschlaege"}
            trail={mapTrail(trail)}
            lodgings={lodgings}
            lengthKm={trail.length_km}
          />
          <Link
            href={`/unterwegs?trail=${encodeURIComponent(trailId)}`}
            className="mt-2 self-start justify-self-start rounded-full border border-white/25 bg-wald-flaeche px-4 py-2 text-sm text-papier hover:bg-wald focus-visible:outline-2 focus-visible:outline-papier"
          >
            Unterwegs
          </Link>
        </div>
      </div>

      <div className="flex-1" />

      <div className="flex justify-end">
        <PhotoSwitcher photos={trail.photos} trailId={trailId} />
      </div>

      <section aria-label={longDistance ? "Etappen" : "Tour"}>
        <StageCards trail={trail} />
      </section>

      {groups.length > 0 && (
        <section aria-label="Gruppen in der Nähe" className="max-w-2xl">
          <h2 className="mb-1 font-serif text-xl">Gruppen in der Nähe</h2>
          <GroupList
            groups={groups}
            note={`Stand: ${new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC" }).format(new Date(`${groups.map((g) => g.checked_at).sort()[0]}T00:00:00Z`))} · bis ${GROUP_RADIUS_KM} km vom Weg`}
          />
        </section>
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
      </footer>
    </PageFrame>
  );
}
