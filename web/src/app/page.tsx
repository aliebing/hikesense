import HomeStage from "../components/HomeStage";
import Notice from "../components/Notice";
import PageFrame from "../components/PageFrame";
import PhotoSwitcher from "../components/PhotoSwitcher";
import { getTrails, pickSpread, type Photo, type TrailSummary } from "../lib/data";
import { MissingConfigError } from "../lib/supabase";

export const dynamic = "force-dynamic";

const BACKDROP_SIZE = 12;

export default async function Home() {
  let trails: TrailSummary[];
  try {
    trails = await getTrails();
  } catch (e) {
    console.error("getTrails failed:", e);
    return (
      <PageFrame>
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
        <HomeStage />
      </PageFrame>
    );
  }

  if (trails.length === 0) {
    return (
      <PageFrame>
        <Notice title="Noch keine Wege in der Datenbank.">
          <p>
            Die Datenbank ist erreichbar, aber leer. Daten importieren mit <code>make import</code>.
          </p>
        </Notice>
        <HomeStage />
      </PageFrame>
    );
  }

  const longDistance = trails.filter((t) => t.kind === "long_distance");
  const backgrounds = [...longDistance, ...pickSpread(trails, BACKDROP_SIZE)]
    .map((t) => t.cover)
    .filter((p, i, all): p is Photo => !!p && all.findIndex((q) => q?.url === p.url) === i);

  return (
    <PageFrame longDistance={longDistance.map(({ id, name }) => ({ id, name }))}>
      <HomeStage />
      <div className="flex justify-end">
        <PhotoSwitcher photos={backgrounds} />
      </div>
      <footer className="text-[11px] text-papier/75">
        Wegdaten: © OpenStreetMap-Mitwirkende (ODbL) · Höhen: Copernicus DEM GLO-30 © DLR e.V./Airbus, bereitgestellt
        von EU/ESA · Gehzeit nach DIN 33466 (Richtwert, ohne Pausen) · Fotos: Wikimedia Commons, Urheber und Lizenz am
        Bild.
      </footer>
    </PageFrame>
  );
}
