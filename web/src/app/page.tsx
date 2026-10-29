import ChatShell from "../components/ChatShell";
import Notice from "../components/Notice";
import Panorama from "../components/Panorama";
import PhotoSwitcher from "../components/PhotoSwitcher";
import { CardRow, TrailCard } from "../components/StageCards";
import { getTrails, photoPool, pickSpread, type Photo, type TrailSummary } from "../lib/data";
import { MissingConfigError } from "../lib/supabase";

export const dynamic = "force-dynamic";

const DAY_HIKE_SELECTION = 12;

export default async function Home() {
  let trails: TrailSummary[];
  try {
    trails = await getTrails();
  } catch (e) {
    console.error("getTrails failed:", e);
    return (
      <Panorama>
        <PhotoSwitcher photos={[]} />
        <Notice title="Daten konnten nicht geladen werden.">
          {e instanceof MissingConfigError ? (
            <p>{e.message}</p>
          ) : (
            <p>
              Die Datenbank ist nicht erreichbar. Läuft Supabase? Starten mit <code>npx supabase start</code> bzw.{" "}
              <code>make up</code>.
            </p>
          )}
        </Notice>
      </Panorama>
    );
  }

  if (trails.length === 0) {
    return (
      <Panorama>
        <PhotoSwitcher photos={[]} />
        <Notice title="Noch keine Wege in der Datenbank.">
          <p>
            Die Datenbank ist erreichbar, aber leer. Daten importieren mit <code>make import</code>.
          </p>
        </Notice>
      </Panorama>
    );
  }

  const longDistance = trails.filter((t) => t.kind === "long_distance");
  const withPhoto = photoPool(trails).length;
  const selection = pickSpread(trails, DAY_HIKE_SELECTION);
  const backgrounds = [...longDistance, ...selection]
    .map((t) => t.cover)
    .filter((p, i, all): p is Photo => !!p && all.findIndex((q) => q?.url === p.url) === i);

  return (
    <Panorama>
      <section className="max-w-2xl pt-6 sm:pt-12">
        <h1 className="font-serif text-4xl leading-tight drop-shadow-md sm:text-6xl">Wandern im Schwarzwald</h1>
        <p className="mt-3 max-w-lg text-base text-papier/90 drop-shadow sm:text-lg">
          Westweg-Etappen und Tagestouren mit echten Strecken, Höhenmetern und Gehzeiten – bald im Gespräch geplant.
        </p>
      </section>

      <ChatShell intro="Hallo! Hier planst du bald deine Wanderung im Gespräch – zum Beispiel „3 Tage Westweg ab Hausach, etwa 15 km pro Tag“. Bis dahin: Wähle unten einen Weg." />

      <div className="flex-1" />

      <div className="flex justify-end">
        <PhotoSwitcher photos={backgrounds} />
      </div>

      <section aria-labelledby="fernwege" className="flex flex-col gap-2">
        <h2 id="fernwege" className="font-serif text-xl drop-shadow">Fernwege</h2>
        <CardRow label="Fernwege">
          {longDistance.map((t) => (
            <li key={t.id}>
              <TrailCard trail={t} />
            </li>
          ))}
        </CardRow>
      </section>

      <section aria-labelledby="tagestouren" className="flex flex-col gap-2">
        <h2 id="tagestouren" className="font-serif text-xl drop-shadow">
          Tagestouren – eine Auswahl
        </h2>
        <p className="text-xs text-papier/80">
          {selection.length} von {withPhoto} Tagestouren mit Foto, von Nord nach Süd verteilt.
        </p>
        <CardRow label="Tagestouren">
          {selection.map((t) => (
            <li key={t.id}>
              <TrailCard trail={t} />
            </li>
          ))}
        </CardRow>
      </section>

      <footer className="text-[11px] text-papier/75">
        Wegdaten: © OpenStreetMap-Mitwirkende (ODbL) · Höhen: Copernicus DEM GLO-30 © DLR e.V./Airbus, bereitgestellt
        von EU/ESA · Gehzeit nach DIN 33466 (Richtwert, ohne Pausen) · Fotos: Wikimedia Commons, Urheber und Lizenz am
        Bild.
      </footer>
    </Panorama>
  );
}
