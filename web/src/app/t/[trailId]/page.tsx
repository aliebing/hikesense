import { notFound } from "next/navigation";
import ChatShell from "../../../components/ChatShell";
import Notice from "../../../components/Notice";
import Panorama from "../../../components/Panorama";
import PhotoSwitcher from "../../../components/PhotoSwitcher";
import StageCards, { Facts } from "../../../components/StageCards";
import { getTrail, type TrailDetail } from "../../../lib/data";
import { hm, hmDown, km, walkingTime } from "../../../lib/format";

export const dynamic = "force-dynamic";

export default async function TrailPage({ params }: { params: Promise<{ trailId: string }> }) {
  const { trailId } = await params;
  let trail: TrailDetail | null;
  try {
    trail = await getTrail(trailId);
  } catch (e) {
    console.error(`getTrail(${trailId}) failed:`, e);
    return (
      <Panorama back>
        <PhotoSwitcher photos={[]} />
        <Notice title="Daten konnten nicht geladen werden.">
          <p>Die Datenbank ist nicht erreichbar oder nicht konfiguriert. Bitte später erneut versuchen.</p>
        </Notice>
      </Panorama>
    );
  }
  if (!trail) notFound();

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
    <Panorama back>
      <section>
        <h1 className="font-serif text-3xl leading-tight drop-shadow-md sm:text-5xl">{trail.name}</h1>
        <Facts items={meta} className="mt-1 text-sm text-papier/90 drop-shadow" />
      </section>

      <div className="grid gap-4 md:grid-cols-[minmax(0,24rem)_1fr]">
        <ChatShell
          intro={
            longDistance
              ? `Der ${trail.name} hat ${trail.stages.length} Etappen. Bald kannst du hier fragen, z. B. „3 Tage ab Hausach, etwa 15 km pro Tag“.`
              : `${trail.name}${trail.length_km === null ? "" : `: ${km(trail.length_km)}`}. Bald kannst du hier fragen, ob die Tour zu dir und zum Wetter passt.`
          }
        />
        {/* Slot for the trail map (Task 11): trail.geom / stage.geom are loaded as GeoJSON. */}
        <div data-slot="map" />
      </div>

      <div className="flex-1" />

      <div className="flex justify-end">
        <PhotoSwitcher photos={trail.photos} />
      </div>

      <section aria-label={longDistance ? "Etappen" : "Tour"}>
        <StageCards trail={trail} />
      </section>

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
        {" · "}Gehzeit nach DIN 33466 (Richtwert, ohne Pausen)
      </footer>
    </Panorama>
  );
}
